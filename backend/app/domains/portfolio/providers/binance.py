import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.core.errors import ProviderUnavailable


class BinancePortfolioProvider:
    """Read-only Binance Spot account adapter. It never submits orders."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._base_url = settings.binance_api_base_url.rstrip("/")
        self._api_key = settings.binance_api_key
        self._api_secret = settings.binance_api_secret
        self._recv_window = settings.binance_recv_window_ms

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._api_secret)

    async def _signed_get(self, path: str, params: dict[str, str] | None = None):
        if not self.configured:
            raise ProviderUnavailable(
                "Binance account",
                "Read-only Binance API credentials are not configured on the server.",
            )
        query = {
            **(params or {}),
            "recvWindow": str(self._recv_window),
            "timestamp": str(int(time.time() * 1000)),
        }
        query_string = urlencode(query)
        signature = hmac.new(
            self._api_secret.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()
        try:
            response = await self._client.get(
                f"{self._base_url}{path}?{query_string}&signature={signature}",
                headers={"X-MBX-APIKEY": self._api_key},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderUnavailable(
                "Binance account", "Binance account request failed."
            ) from error

    async def account(self) -> dict:
        payload = await self._signed_get("/api/v3/account", {"omitZeroBalances": "true"})
        if not isinstance(payload, dict) or not isinstance(payload.get("balances"), list):
            raise ProviderUnavailable(
                "Binance account", "Binance returned an invalid account payload."
            )
        return payload

    async def trades(self, symbol: str, limit: int = 500) -> list[dict]:
        payload = await self._signed_get(
            "/api/v3/myTrades",
            {"symbol": symbol.upper(), "limit": str(min(max(limit, 1), 1000))},
        )
        if not isinstance(payload, list):
            raise ProviderUnavailable("Binance account", "Binance returned invalid trade history.")
        return payload
