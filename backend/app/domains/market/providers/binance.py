import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ProviderRateLimited, ProviderUnavailable
from app.domains.market.data_sources.binance import BinanceMarketDataSource
from app.domains.market.providers.base import MarketProvider
from app.domains.market.router.health import ProviderHealthState
from app.domains.market.schemas.market import Candle, Instrument, Ticker

logger = logging.getLogger(__name__)


class BinanceSpotProvider(MarketProvider):
    """Public Binance Spot market data adapter; it never submits exchange orders."""

    name = "binance"

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: Settings,
        health: ProviderHealthState,
    ) -> None:
        self._client = client
        self._base_url = settings.binance_api_base_url.rstrip("/")
        self._timeout = settings.binance_request_timeout_seconds
        self._source = BinanceMarketDataSource(client, settings)
        self._health = health

    async def _request(self, path: str, params: dict[str, Any]) -> Any:
        started = perf_counter()
        try:
            response = await self._client.get(
                f"{self._base_url}{path}", params=params, timeout=self._timeout
            )
        except httpx.HTTPError as error:
            self._health.record_error()
            raise ProviderUnavailable("Binance", "Public market data is unreachable.") from error
        if response.status_code in {418, 429}:
            self._health.record_error()
            self._health.rate_limited = True
            raise ProviderRateLimited("Binance", response.headers.get("Retry-After"))
        if response.is_error:
            self._health.record_error()
            raise ProviderUnavailable("Binance", f"Binance returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as error:
            self._health.record_error()
            raise ProviderUnavailable("Binance", "Binance returned invalid JSON.") from error
        self._health.record_success((perf_counter() - started) * 1000)
        return payload

    async def get_instruments(self) -> list[Instrument]:
        try:
            records = await self._source.instruments()
        except ProviderUnavailable:
            self._health.record_error()
            raise
        self._health.record_success(0)
        return records

    async def get_tickers(self) -> list[Ticker]:
        try:
            records = await self._source.tickers()
        except ProviderUnavailable:
            self._health.record_error()
            raise
        self._health.record_success(0)
        return records

    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        try:
            records = await self._source.candles(symbol, interval, min(max(limit, 1), 1000))
        except ProviderUnavailable:
            self._health.record_error()
            raise
        self._health.record_success(0)
        return records

    async def get_orderbook(self, symbol: str, depth: int = 25) -> dict[str, Any]:
        payload = await self._request(
            "/api/v3/depth",
            {"symbol": symbol.upper(), "limit": min(max(depth, 5), 5000)},
        )
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("bids"), list)
            or not isinstance(payload.get("asks"), list)
        ):
            self._health.record_error()
            raise ProviderUnavailable("Binance", "Order book response has an unexpected shape.")
        return {
            "symbol": symbol.upper(),
            "bids": payload["bids"],
            "asks": payload["asks"],
            "provider": "binance",
            "exchange": "Binance Spot",
            "updated_at": datetime.now(UTC),
        }

    async def get_trades(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        payload = await self._request(
            "/api/v3/trades",
            {"symbol": symbol.upper(), "limit": min(max(limit, 1), 1000)},
        )
        if not isinstance(payload, list):
            raise ProviderUnavailable("Binance", "Trade response has an unexpected shape.")
        trades: list[dict[str, Any]] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                trades.append({
                    "symbol": symbol.upper(),
                    "price": float(row["price"]),
                    "volume": float(row["qty"]),
                    "exchange_timestamp": datetime.fromtimestamp(int(row["time"]) / 1000, tz=UTC),
                    "side": "sell" if row.get("isBuyerMaker") else "buy",
                    "provider": "binance",
                })
            except (KeyError, TypeError, ValueError, OverflowError):
                logger.warning("binance_trade_invalid symbol=%s", symbol)
        return trades
