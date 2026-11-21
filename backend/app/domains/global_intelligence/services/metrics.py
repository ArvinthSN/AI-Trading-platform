import asyncio
import logging
import math
from datetime import datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.global_intelligence.data_sources.coingecko import CoinGeckoGlobalSource
from app.domains.global_intelligence.data_sources.fear_greed import FearAndGreedSource
from app.domains.global_intelligence.schemas.global_data import (
    Availability,
    GlobalMetric,
    GlobalMetricsResponse,
)
from app.domains.market.router.provider_router import ProviderRouter

logger = logging.getLogger(__name__)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _nested_number(data: dict[str, Any], group: str, name: str) -> float | None:
    nested = data.get(group)
    if not isinstance(nested, dict):
        return None
    return _number(nested.get(name))


def _unavailable(reason: str) -> GlobalMetric:
    return GlobalMetric(value=None, status=Availability.UNAVAILABLE, reason=reason)


async def fetch_global_metrics(
    client: httpx.AsyncClient,
    settings: Settings,
) -> GlobalMetricsResponse:
    coingecko = CoinGeckoGlobalSource(client, settings)
    fear_greed = FearAndGreedSource(client, settings)
    market_router = ProviderRouter(client, settings)
    results = await asyncio.gather(
        coingecko.global_data(),
        fear_greed.latest(),
        market_router.get_tickers(),
        return_exceptions=True,
    )
    global_result, sentiment_result, ticker_result = results

    unavailable_reason = "Provider data is unavailable."
    global_data: dict[str, Any] | None = None
    global_updated: datetime | None = None
    if isinstance(global_result, tuple):
        raw_data, global_updated = global_result
        if isinstance(raw_data, dict):
            global_data = raw_data
    elif isinstance(global_result, ProviderUnavailable):
        logger.warning("global_metrics_provider_unavailable provider=%s", global_result.provider)
    elif isinstance(global_result, BaseException):
        logger.error("global_metrics_provider_error error=%s", type(global_result).__name__)

    sentiment_value: int | None = None
    sentiment_updated: datetime | None = None
    if isinstance(sentiment_result, tuple):
        sentiment_value, sentiment_updated = sentiment_result
    elif isinstance(sentiment_result, ProviderUnavailable):
        logger.warning("global_sentiment_unavailable provider=%s", sentiment_result.provider)
    elif isinstance(sentiment_result, BaseException):
        logger.error("global_sentiment_error error=%s", type(sentiment_result).__name__)

    btc_price: float | None = None
    btc_updated: datetime | None = None
    btc_source: str | None = None
    if isinstance(ticker_result, list):
        btc_ticker = next(
            (
                ticker
                for ticker in ticker_result
                if ticker.symbol.replace("-", "").replace("/", "")
                in {"BTCUSDT", "BTCUSD", "XBTUSD"}
            ),
            None,
        )
        if btc_ticker is not None:
            btc_price = btc_ticker.price
            btc_updated = btc_ticker.updated_at
            btc_source = btc_ticker.source
    elif isinstance(ticker_result, ProviderUnavailable):
        logger.warning("global_btc_price_unavailable provider=%s", ticker_result.provider)
    elif isinstance(ticker_result, BaseException):
        logger.error("global_btc_price_error error=%s", type(ticker_result).__name__)

    dominance = _nested_number(global_data or {}, "market_cap_percentage", "btc")
    total_market_cap = _nested_number(global_data or {}, "total_market_cap", "usd")
    volume = _nested_number(global_data or {}, "total_volume", "usd")
    market_change = _number((global_data or {}).get("market_cap_change_percentage_24h_usd"))
    trend_value = (
        ("bullish" if market_change > 0 else "bearish" if market_change < 0 else "neutral")
        if market_change is not None
        else None
    )

    return GlobalMetricsResponse(
        btc_price=(
            GlobalMetric(
                value=btc_price,
                unit="USD",
                source=btc_source,
                updated_at=btc_updated,
                status=Availability.AVAILABLE,
            )
            if btc_price is not None
            else _unavailable("Kraken/Coinbase BTC ticker is unavailable.")
        ),
        btc_dominance=(
            GlobalMetric(
                value=dominance,
                unit="percent",
                source="CoinGecko Global",
                updated_at=global_updated,
                status=Availability.AVAILABLE,
            )
            if dominance is not None
            else _unavailable(unavailable_reason)
        ),
        total_market_cap=(
            GlobalMetric(
                value=total_market_cap,
                unit="USD",
                change_24h=market_change,
                source="CoinGecko Global",
                updated_at=global_updated,
                status=Availability.AVAILABLE,
            )
            if total_market_cap is not None
            else _unavailable(unavailable_reason)
        ),
        volume_24h=(
            GlobalMetric(
                value=volume,
                unit="USD",
                source="CoinGecko Global",
                updated_at=global_updated,
                status=Availability.AVAILABLE,
            )
            if volume is not None
            else _unavailable(unavailable_reason)
        ),
        fear_and_greed=(
            GlobalMetric(
                value=sentiment_value,
                unit="index (0–100)",
                source="Alternative.me Fear & Greed",
                updated_at=sentiment_updated,
                status=Availability.AVAILABLE,
            )
            if sentiment_value is not None
            else _unavailable("Alternative.me sentiment index is unavailable.")
        ),
        market_trend=(
            GlobalMetric(
                value=trend_value,
                change_24h=market_change,
                unit="direction",
                source="CoinGecko Global 24-hour market cap change",
                updated_at=global_updated,
                status=Availability.AVAILABLE,
            )
            if trend_value is not None
            else _unavailable("A verified 24-hour global market change is unavailable.")
        ),
    )


def default_regions() -> list[dict[str, object]]:
    return [
        {
            "id": "americas",
            "name": "Americas",
            "center_latitude": 14.0,
            "center_longitude": -92.0,
            "data_status": Availability.UNAVAILABLE,
            "source": None,
            "updated_at": None,
            "developments": [],
        },
        {
            "id": "europe",
            "name": "Europe",
            "center_latitude": 51.0,
            "center_longitude": 14.0,
            "data_status": Availability.UNAVAILABLE,
            "source": None,
            "updated_at": None,
            "developments": [],
        },
        {
            "id": "asia-pacific",
            "name": "Asia-Pacific",
            "center_latitude": 28.0,
            "center_longitude": 116.0,
            "data_status": Availability.UNAVAILABLE,
            "source": None,
            "updated_at": None,
            "developments": [],
        },
        {
            "id": "middle-east-africa",
            "name": "Middle East & Africa",
            "center_latitude": 12.0,
            "center_longitude": 38.0,
            "data_status": Availability.UNAVAILABLE,
            "source": None,
            "updated_at": None,
            "developments": [],
        },
    ]
