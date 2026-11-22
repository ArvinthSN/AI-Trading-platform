from datetime import UTC, datetime

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import ProviderRateLimited
from app.domains.market.providers.binance import BinanceSpotProvider
from app.domains.market.router.health import ProviderHealthState


@pytest.mark.asyncio
async def test_binance_ticker_payload_is_normalized_and_timestamped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/ticker/24hr"
        return httpx.Response(
            200,
            json=[
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "67500.25",
                    "priceChangePercent": "1.25",
                    "quoteVolume": "123456.7",
                    "closeTime": 1763750000000,
                }
            ],
        )

    health = ProviderHealthState(name="Binance Spot")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinanceSpotProvider(client, Settings(), health)
        tickers = await provider.get_tickers()

    assert len(tickers) == 1
    assert tickers[0].symbol == "BTCUSDT"
    assert tickers[0].price == 67500.25
    assert tickers[0].change_24h == 1.25
    assert tickers[0].source == "Binance Spot"
    assert tickers[0].updated_at.tzinfo == UTC
    assert health.snapshot().connected is True


@pytest.mark.asyncio
async def test_binance_rejects_rate_limited_requests_without_fabricating_data() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "3"}, json={"code": -1003})

    health = ProviderHealthState(name="Binance Spot")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinanceSpotProvider(client, Settings(), health)
        with pytest.raises(ProviderRateLimited):
            await provider.get_tickers()

    snapshot = health.snapshot()
    assert snapshot.connected is False
    assert snapshot.rate_limited is True
    assert snapshot.request_error_count == 1


@pytest.mark.asyncio
async def test_binance_candles_are_sorted_and_invalid_rows_are_discarded() -> None:
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    rows = [
        [now_ms - 120000, "10", "12", "9", "11", "2", now_ms - 60001, "20", 10, "1", "2", "0"],
        [now_ms - 60000, "11", "13", "10", "12", "3", now_ms + 59999, "30", 12, "2", "3", "0"],
        [now_ms - 30000, "11", "8", "10", "12", "3", now_ms + 29999, "30", 12, "2", "3", "0"],
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=rows)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinanceSpotProvider(client, Settings(), ProviderHealthState("Binance Spot"))
        candles = await provider.get_candles("BTCUSDT", "1m", 100)

    assert len(candles) == 2
    assert candles[0].time < candles[1].time
    assert candles[0].is_closed is True
    assert candles[1].is_closed is False

@pytest.mark.asyncio
async def test_provider_router_uses_binance_before_kraken() -> None:
    from app.domains.market.router.provider_router import ProviderRouter

    settings = Settings()
    async with httpx.AsyncClient() as async_client:
        router = ProviderRouter(async_client, settings)
        assert [provider.name for provider in router.ordered_providers()] == [
            "binance",
            "kraken",
            "coinbase",
        ]
