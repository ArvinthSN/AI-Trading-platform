import logging
import math
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ProviderRateLimited, ProviderUnavailable
from app.domains.market.schemas.market import Candle, Instrument, Ticker

logger = logging.getLogger(__name__)
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{5,30}$")
INTERVALS = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}


class BinanceMarketDataSource:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._base_url = settings.binance_api_base_url.rstrip("/")
        self._timeout = settings.binance_request_timeout_seconds

    async def _get(self, path: str, params: dict[str, str | int] | None = None) -> Any:
        try:
            response = await self._client.get(
                f"{self._base_url}{path}",
                params=params,
                timeout=self._timeout,
            )
        except httpx.HTTPError as error:
            logger.warning("binance_request_failed path=%s error=%s", path, type(error).__name__)
            raise ProviderUnavailable("Binance", "Market data could not be reached.") from error
        if response.status_code in {418, 429}:
            raise ProviderRateLimited("Binance", response.headers.get("Retry-After"))
        if response.is_error:
            logger.warning("binance_http_error path=%s status=%s", path, response.status_code)
            raise ProviderUnavailable(
                "Binance", f"Market provider returned HTTP {response.status_code}."
            )
        try:
            return response.json()
        except ValueError as error:
            raise ProviderUnavailable(
                "Binance", "Market provider returned invalid JSON."
            ) from error

    async def instruments(self, quote_asset: str = "USDT") -> list[Instrument]:
        payload = await self._get("/api/v3/exchangeInfo", {"permissions": "SPOT"})
        symbols = payload.get("symbols", []) if isinstance(payload, dict) else []
        results: list[Instrument] = []
        for item in symbols:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "TRADING" or item.get("quoteAsset") != quote_asset:
                continue
            if not item.get("isSpotTradingAllowed", True):
                continue
            results.append(
                Instrument(
                    symbol=str(item["symbol"]),
                    base_asset=str(item["baseAsset"]),
                    quote_asset=str(item["quoteAsset"]),
                    status=str(item["status"]),
                )
            )
        return results

    async def tickers(self) -> list[Ticker]:
        payload = await self._get("/api/v3/ticker/24hr")
        if not isinstance(payload, list):
            raise ProviderUnavailable("Binance", "Ticker response has an unexpected shape.")
        results: list[Ticker] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                values = {
                    "price": float(item["lastPrice"]),
                    "change_24h": float(item["priceChangePercent"]),
                    "volume_24h": float(item["quoteVolume"]),
                }
                updated_at = datetime.fromtimestamp(int(item["closeTime"]) / 1000, tz=UTC)
                if not all(math.isfinite(value) for value in values.values()):
                    continue
                if values["price"] <= 0 or values["volume_24h"] < 0:
                    continue
                results.append(
                    Ticker(
                        symbol=str(item["symbol"]),
                        **values,
                        updated_at=updated_at,
                    )
                )
            except (KeyError, TypeError, ValueError):
                logger.warning("binance_ticker_invalid symbol=%s", item.get("symbol"))
        return results

    async def candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        normalized_symbol = symbol.upper()
        if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
            raise ValueError("Invalid market symbol.")
        if interval not in INTERVALS:
            raise ValueError("Unsupported candle interval.")
        payload = await self._get(
            "/api/v3/klines",
            {"symbol": normalized_symbol, "interval": interval, "limit": limit},
        )
        if not isinstance(payload, list):
            raise ProviderUnavailable("Binance", "Candle response has an unexpected shape.")
        by_open_time: dict[int, Candle] = {}
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        for item in payload:
            try:
                if not isinstance(item, list) or len(item) < 8:
                    continue
                open_time = int(item[0])
                candle = Candle(
                    time=datetime.fromtimestamp(open_time / 1000, tz=UTC),
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                    is_closed=int(item[6]) < now_ms,
                )
                prices = (candle.open, candle.high, candle.low, candle.close, candle.volume)
                if not all(math.isfinite(value) for value in prices):
                    continue
                if candle.volume < 0 or candle.high < max(candle.open, candle.close):
                    continue
                if candle.low > min(candle.open, candle.close) or candle.low > candle.high:
                    continue
                by_open_time[open_time] = candle
            except (IndexError, TypeError, ValueError, OverflowError):
                logger.warning("binance_candle_invalid symbol=%s", normalized_symbol)
        return [by_open_time[key] for key in sorted(by_open_time)]
