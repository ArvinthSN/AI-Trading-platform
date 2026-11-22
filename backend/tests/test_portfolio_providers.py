from urllib.parse import parse_qs, urlparse
import hashlib
import hmac

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
        return httpx.Response(200, json={"balances": [{"asset": "USDT", "free": "25", "locked": "0"}]})

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
