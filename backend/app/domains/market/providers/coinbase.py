import logging
import math
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.errors import ProviderRateLimited, ProviderUnavailable
from app.domains.market.providers.base import MarketProvider
from app.domains.market.router.health import ProviderHealthState
from app.domains.market.schemas.market import Candle, Instrument, Ticker

logger = logging.getLogger(__name__)


class CoinbaseExchangeProvider(MarketProvider):
    name = "coinbase"

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: Settings,
        health: ProviderHealthState,
    ) -> None:
        self._client = client
        self._base_url = settings.coinbase_rest_base_url.rstrip("/")
        self._health = health
        self._timeout = settings.binance_request_timeout_seconds

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        started = perf_counter()
        try:
            response = await self._client.get(
                f"{self._base_url}{path}",
                params=params,
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as error:
            self._health.record_error()
            raise ProviderUnavailable(
                "Coinbase Exchange",
                "Coinbase public market data could not be reached.",
            ) from error
        if response.status_code == 429:
            self._health.record_error()
            self._health.rate_limited = True
            raise ProviderRateLimited("Coinbase Exchange", response.headers.get("Retry-After"))
        if response.is_error:
            self._health.record_error()
            raise ProviderUnavailable(
                "Coinbase Exchange",
                f"Coinbase Exchange returned HTTP {response.status_code}.",
            )
        try:
            payload = response.json()
        except ValueError as error:
            self._health.record_error()
            raise ProviderUnavailable(
                "Coinbase Exchange",
                "Coinbase Exchange returned invalid JSON.",
            ) from error
        self._health.record_success((perf_counter() - started) * 1000)
        return payload

    def _product_id(self, symbol: str) -> str:
        normalized = symbol.upper().replace("/", "").replace("-", "")
        if normalized in {"XBTUSD", "BTCUSD"}:
            return "BTC-USD"
        if normalized.endswith("USDT"):
            return f"{normalized[:-4]}-USDT"
        if normalized.endswith("USD"):
            return f"{normalized[:-3]}-USD"
        return normalized

    async def get_instruments(self) -> list[Instrument]:
        payload = await self._get("/products")
        if not isinstance(payload, list):
            return []
        instruments: list[Instrument] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "online" or item.get("trading_disabled"):
                continue
            quote = str(item.get("quote_currency") or "")
            if quote not in {"USD", "USDT"}:
                continue
            product_id = str(item.get("id") or "")
            if "-" not in product_id:
                continue
            base, product_quote = product_id.split("-", 1)
            instruments.append(
                Instrument(
                    symbol=f"{base}{product_quote}",
                    base_asset=base,
                    quote_asset=product_quote,
                    status="TRADING",
                    source="Coinbase Exchange",
                )
            )
        return instruments

    async def get_tickers(self) -> list[Ticker]:
        instruments = await self.get_instruments()
        tickers: list[Ticker] = []
        preferred = {
            "BTCUSD",
            "ETHUSD",
            "SOLUSD",
            "XRPUSD",
            "ADAUSD",
            "DOGEUSD",
            "SHIBUSD",
            "LTCUSD",
            "AVAXUSD",
            "BCHUSD",
            "LINKUSD",
        }
        selected = [
            instrument
            for instrument in instruments
            if instrument.symbol in preferred
        ]
        for instrument in selected:
            product_id = self._product_id(instrument.symbol)
            encoded_product = quote(product_id, safe="")
            try:
                stats = await self._get(f"/products/{encoded_product}/stats")
                ticker = await self._get(f"/products/{encoded_product}/ticker")
                price = float(ticker["price"])
                bid = float(ticker.get("bid", 0))
                ask = float(ticker.get("ask", 0))
                volume = float(stats["volume"])
                opening = float(stats["open"])
                percentage = (price - opening) / opening * 100 if opening != 0 else 0.0
                if not all(math.isfinite(value) for value in (price, bid, ask, volume, opening)):
                    continue
                tickers.append(
                    Ticker(
                        symbol=instrument.symbol,
                        price=price,
                        change_24h=percentage,
                        volume_24h=volume,
                        updated_at=datetime.now(UTC),
                        source="Coinbase Exchange",
                    )
                )
            except (KeyError, TypeError, ValueError, ProviderUnavailable):
                continue
        return tickers

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[Candle]:
        granularity = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 21600,
            "1d": 86400,
        }.get(interval)
        if granularity is None:
            raise ValueError("Unsupported Coinbase candle interval.")
        product_id = self._product_id(symbol)
        encoded_product = quote(product_id, safe="")
        payload = await self._get(
            f"/products/{encoded_product}/candles",
            {"granularity": granularity, "limit": min(max(limit, 1), 300)},
        )
        if not isinstance(payload, list):
            return []
        candles: dict[int, Candle] = {}
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                continue
            try:
                open_time = int(row[0])
                candle = Candle(
                    time=datetime.fromtimestamp(open_time, tz=UTC),
                    low=float(row[1]),
                    high=float(row[2]),
                    open=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    is_closed=True,
                )
                values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
                if not all(math.isfinite(value) for value in values):
                    continue
                if candle.volume < 0 or candle.low > candle.high:
                    continue
                if (
                    candle.high < max(candle.open, candle.close)
                    or candle.low > min(candle.open, candle.close)
                ):
                    continue
                candles[open_time] = candle
            except (TypeError, ValueError, OverflowError):
                continue
        return [candles[key] for key in sorted(candles)]

    async def get_orderbook(self, symbol: str, depth: int = 25) -> dict[str, Any]:
        product_id = self._product_id(symbol)
        encoded_product = quote(product_id, safe="")
        payload = await self._get(
            f"/products/{encoded_product}/book",
            {"level": 2},
        )
        if not isinstance(payload, dict):
            return {"symbol": symbol, "bids": [], "asks": [], "provider": "coinbase"}
        return {
            "symbol": symbol,
            "bids": payload.get("bids", [])[:depth],
            "asks": payload.get("asks", [])[:depth],
            "provider": "coinbase",
            "exchange": "Coinbase Exchange",
            "updated_at": datetime.now(UTC),
        }

    async def get_trades(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        product_id = self._product_id(symbol)
        encoded_product = quote(product_id, safe="")
        payload = await self._get(
            f"/products/{encoded_product}/trades",
            {"limit": min(max(limit, 1), 1000)},
        )
        if not isinstance(payload, list):
            return []
        trades: list[dict[str, Any]] = []
        for item in payload[:limit]:
            if not isinstance(item, dict):
                continue
            try:
                timestamp = datetime.fromisoformat(str(item["time"]).replace("Z", "+00:00"))
                trades.append({
                    "symbol": symbol,
                    "price": float(item["price"]),
                    "volume": float(item["size"]),
                    "exchange_timestamp": timestamp.astimezone(UTC),
                    "side": str(item["side"]).lower(),
                    "provider": "coinbase",
                })
            except (KeyError, TypeError, ValueError):
                continue
        return trades
