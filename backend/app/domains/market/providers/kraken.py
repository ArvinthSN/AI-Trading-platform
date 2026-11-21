import logging
import math
import re
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ProviderRateLimited, ProviderUnavailable
from app.domains.market.providers.base import MarketProvider
from app.domains.market.router.health import ProviderHealthState
from app.domains.market.schemas.market import Candle, Instrument, Ticker

logger = logging.getLogger(__name__)


class KrakenProvider(MarketProvider):
    name = "kraken"

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: Settings,
        health: ProviderHealthState,
    ) -> None:
        self._client = client
        self._base_url = settings.kraken_rest_base_url.rstrip("/")
        self._timeout = settings.binance_request_timeout_seconds
        self._health = health

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        started = perf_counter()
        try:
            response = await self._client.get(
                f"{self._base_url}{path}",
                params=params,
                timeout=self._timeout,
            )
        except httpx.HTTPError as error:
            self._health.record_error()
            raise ProviderUnavailable(
                "Kraken",
                "Kraken market data could not be reached.",
            ) from error
        if response.status_code == 429:
            self._health.record_error()
            self._health.rate_limited = True
            raise ProviderRateLimited("Kraken", response.headers.get("Retry-After"))
        if response.is_error:
            self._health.record_error()
            raise ProviderUnavailable(
                "Kraken",
                f"Kraken returned HTTP {response.status_code}.",
            )
        try:
            payload = response.json()
        except ValueError as error:
            self._health.record_error()
            raise ProviderUnavailable("Kraken", "Kraken returned invalid JSON.") from error
        if not isinstance(payload, dict):
            self._health.record_error()
            raise ProviderUnavailable("Kraken", "Kraken returned an unexpected response.")
        if payload.get("error"):
            self._health.record_error()
            raise ProviderUnavailable("Kraken", "Kraken rejected the public market request.")
        latency = (perf_counter() - started) * 1000
        self._health.record_success(latency)
        return payload

    async def get_instruments(self) -> list[Instrument]:
        payload = await self._get("/0/public/AssetPairs")
        result = payload.get("result", {})
        instruments: list[Instrument] = []
        if not isinstance(result, dict):
            return instruments
        for key, item in result.items():
            if not isinstance(item, dict):
                continue
            if item.get("status") != "online":
                continue
            base = str(item.get("base", "")).removeprefix("X")
            quote = str(item.get("quote", "")).removeprefix("Z")
            pair = str(item.get("wsname") or key)
            if "/" in pair:
                pair = pair.replace("/", "")
            if quote not in {"USD", "EUR", "USDT"}:
                continue
            if pair.endswith("XBTUSD"):
                normalized = "BTCUSD"
            else:
                normalized = f"{base}{quote}".replace("XBT", "BTC")
            instruments.append(
                Instrument(
                    symbol=normalized,
                    base_asset=base,
                    quote_asset=quote,
                    status="TRADING",
                    source="Kraken",
                )
            )
        unique = {instrument.symbol: instrument for instrument in instruments}
        return list(unique.values())

    def _pair_candidates(self, symbol: str) -> list[str]:
        normalized = symbol.upper().replace("-", "").replace("/", "")
        if normalized in {"BTCUSD", "XBTUSD"}:
            return ["XBTUSD", "XXBTZUSD"]
        if normalized.endswith("USD"):
            base = normalized[:-3]
            return [f"{base}USD"]
        if normalized.endswith("USDT"):
            base = normalized[:-4]
            return [f"{base}USDT"]
        return [normalized]

    async def get_tickers(self) -> list[Ticker]:
        payload = await self._get("/0/public/Ticker")
        result = payload.get("result", {})
        if not isinstance(result, dict):
            return []
        now = datetime.now(UTC)
        tickers: list[Ticker] = []
        for pair_name, item in result.items():
            if not isinstance(item, dict):
                continue
            try:
                price_values = item.get("c")
                if not isinstance(price_values, list) or not price_values:
                    continue
                price = float(price_values[0])
                volume = float((item.get("v") or [0, 0])[1])
                opening = float(item.get("o") or 0)
                percentage = (price - opening) / opening * 100 if opening != 0 else 0.0
                if not all(math.isfinite(value) for value in (price, volume, percentage)):
                    continue
                symbol = pair_name
                if "XBT" in symbol or "XXBT" in symbol:
                    symbol = symbol.replace("XXBT", "BTC").replace("XBT", "BTC")
                if "ZUSD" in symbol:
                    symbol = symbol.replace("ZUSD", "USD")
                if not re.fullmatch(r"[A-Z0-9]{5,30}", symbol):
                    continue
                tickers.append(
                    Ticker(
                        symbol=symbol,
                        price=price,
                        change_24h=percentage,
                        volume_24h=volume,
                        updated_at=now,
                        source="Kraken",
                    )
                )
            except (KeyError, TypeError, ValueError, IndexError):
                logger.warning("kraken_ticker_invalid pair=%s", pair_name)
        return tickers

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[Candle]:
        interval_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
            "1w": 10080,
        }.get(interval)
        if interval_minutes is None:
            raise ValueError("Unsupported Kraken candle interval.")
        pair = self._pair_candidates(symbol)[0]
        payload = await self._get(
            "/0/public/OHLC",
            {"pair": pair, "interval": interval_minutes},
        )
        result = payload.get("result", {})
        if not isinstance(result, dict):
            return []
        series = next((value for key, value in result.items() if key != "last"), None)
        if not isinstance(series, list):
            return []
        candles: dict[int, Candle] = {}
        for row in series[-limit:]:
            if not isinstance(row, list) or len(row) < 8:
                continue
            try:
                open_time = int(float(row[0]))
                candle = Candle(
                    time=datetime.fromtimestamp(open_time, tz=UTC),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[6]),
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
                logger.warning("kraken_candle_invalid symbol=%s", symbol)
        return [candles[key] for key in sorted(candles)]

    async def get_orderbook(self, symbol: str, depth: int = 25) -> dict[str, Any]:
        pair = self._pair_candidates(symbol)[0]
        payload = await self._get(
            "/0/public/Depth",
            {"pair": pair, "count": min(max(depth, 1), 500)},
        )
        result = payload.get("result", {})
        if not isinstance(result, dict):
            return {"symbol": symbol, "bids": [], "asks": [], "provider": "kraken"}
        book = next(iter(result.values()), {})
        if not isinstance(book, dict):
            return {"symbol": symbol, "bids": [], "asks": [], "provider": "kraken"}
        return {
            "symbol": symbol,
            "bids": book.get("bids", []),
            "asks": book.get("asks", []),
            "provider": "kraken",
            "exchange": "Kraken",
            "updated_at": datetime.now(UTC),
        }

    async def get_trades(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        pair = self._pair_candidates(symbol)[0]
        payload = await self._get(
            "/0/public/Trades",
            {"pair": pair, "count": min(max(limit, 1), 1000)},
        )
        result = payload.get("result", {})
        if not isinstance(result, dict):
            return []
        series = next((value for key, value in result.items() if key != "last"), [])
        if not isinstance(series, list):
            return []
        trades: list[dict[str, Any]] = []
        for row in series[-limit:]:
            if not isinstance(row, list) or len(row) < 6:
                continue
            try:
                trades.append({
                    "symbol": symbol,
                    "price": float(row[0]),
                    "volume": float(row[1]),
                    "exchange_timestamp": datetime.fromtimestamp(float(row[2]), tz=UTC),
                    "side": "sell" if str(row[3]).lower() == "s" else "buy",
                    "provider": "kraken",
                })
            except (TypeError, ValueError, OverflowError):
                continue
        return trades
