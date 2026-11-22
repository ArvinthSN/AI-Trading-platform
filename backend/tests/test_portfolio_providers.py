import hashlib
import hmac
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.portfolio.providers.binance import BinancePortfolioProvider
from app.domains.portfolio.providers.paper_engine import PaperPortfolioProvider


@pytest.mark.asyncio
async def test_binance_account_request_is_signed_and_read_only() -> None:
    settings = Settings(
        binance_api_key="read-only-key",
        binance_api_secret="test-secret",
        binance_api_base_url="https://binance.test",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v3/account"
        assert request.headers["X-MBX-APIKEY"] == "read-only-key"
        params = parse_qs(urlparse(str(request.url)).query)
        signature = params.pop("signature")[0]
        query = "&".join(f"{key}={value[0]}" for key, value in params.items())
        expected = hmac.new(
            b"test-secret", query.encode(), hashlib.sha256
        ).hexdigest()
        assert hmac.compare_digest(signature, expected)
        assert params["omitZeroBalances"] == ["true"]
        return httpx.Response(
            200,
            json={"balances": [{"asset": "USDT", "free": "25", "locked": "0"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinancePortfolioProvider(client, settings)
        account = await provider.account()

    assert account["balances"][0]["asset"] == "USDT"


@pytest.mark.asyncio
async def test_binance_account_fails_closed_without_credentials() -> None:
    async with httpx.AsyncClient() as client:
        provider = BinancePortfolioProvider(client, Settings())
        with pytest.raises(ProviderUnavailable, match="credentials are not configured"):
            await provider.account()


@pytest.mark.asyncio
async def test_paper_portfolio_requests_are_scoped_to_authenticated_user() -> None:
    settings = Settings(
        paper_trading_engine_url="https://paper.test",
        paper_trading_engine_token="engine-token",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/paper/portfolio/summary"
        assert request.url.params["user_id"] == "user-123"
        assert request.headers["Authorization"] == "Bearer engine-token"
        return httpx.Response(200, json={"current_value": 1000})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PaperPortfolioProvider(client, settings)
        result = await provider.get("summary", "user-123")

    assert result == {"current_value": 1000}


@pytest.mark.asyncio
async def test_paper_portfolio_fails_closed_when_engine_is_not_configured() -> None:
    async with httpx.AsyncClient() as client:
        provider = PaperPortfolioProvider(client, Settings())
        with pytest.raises(ProviderUnavailable, match="not configured"):
            await provider.get("summary", "user-123")


@pytest.mark.asyncio
async def test_binance_account_rejects_negative_or_non_numeric_balances() -> None:
    settings = Settings(
        binance_api_key="read-only-key",
        binance_api_secret="test-secret",
        binance_api_base_url="https://binance.test",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"balances": [{"asset": "BTC", "free": "-1", "locked": "0"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinancePortfolioProvider(client, settings)
        with pytest.raises(ProviderUnavailable, match="invalid balance amount"):
            await provider.account()


@pytest.mark.asyncio
async def test_binance_trade_history_rejects_invalid_trade_values() -> None:
    settings = Settings(
        binance_api_key="read-only-key",
        binance_api_secret="test-secret",
        binance_api_base_url="https://binance.test",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{
                "id": 1,
                "time": 1763750000000,
                "qty": "0.1",
                "price": "NaN",
                "isBuyer": True,
            }],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinancePortfolioProvider(client, settings)
        with pytest.raises(ProviderUnavailable, match="invalid trade values"):
            await provider.trades("BTCUSDT")


@pytest.mark.asyncio
async def test_paper_engine_requires_both_url_and_service_token() -> None:
    settings = Settings(paper_trading_engine_url="https://paper.test")
    async with httpx.AsyncClient() as client:
        provider = PaperPortfolioProvider(client, settings)
        assert provider.configured is False
        with pytest.raises(ProviderUnavailable, match="not configured"):
            await provider.get("summary", "user-123")


@pytest.mark.asyncio
async def test_binance_authentication_failure_is_reported_as_unavailable() -> None:
    settings = Settings(
        binance_api_key="read-only-key",
        binance_api_secret="test-secret",
        binance_api_base_url="https://binance.test",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": -2015, "msg": "Invalid API-key"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinancePortfolioProvider(client, settings)
        with pytest.raises(ProviderUnavailable, match="request failed"):
            await provider.account()


@pytest.mark.asyncio
async def test_binance_rejects_malformed_account_payload() -> None:
    settings = Settings(
        binance_api_key="read-only-key",
        binance_api_secret="test-secret",
        binance_api_base_url="https://binance.test",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"accountType": "SPOT"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BinancePortfolioProvider(client, settings)
        with pytest.raises(ProviderUnavailable, match="invalid account payload"):
            await provider.account()


@pytest.mark.asyncio
async def test_paper_provider_rejects_unknown_resource_before_network_request() -> None:
    settings = Settings(
        paper_trading_engine_url="https://paper.test",
        paper_trading_engine_token="engine-token",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Unsupported resource must not make a request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PaperPortfolioProvider(client, settings)
        with pytest.raises(ProviderUnavailable, match="Unsupported"):
            await provider.get("../orders", "user-123")


@pytest.mark.asyncio
async def test_paper_provider_rejects_missing_authenticated_user() -> None:
    settings = Settings(
        paper_trading_engine_url="https://paper.test",
        paper_trading_engine_token="engine-token",
    )
    async with httpx.AsyncClient() as client:
        provider = PaperPortfolioProvider(client, settings)
        with pytest.raises(ProviderUnavailable, match="user identifier"):
            await provider.get("summary", " ")
