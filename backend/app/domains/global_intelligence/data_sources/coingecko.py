import logging
from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.core.errors import ProviderRateLimited, ProviderUnavailable

logger = logging.getLogger(__name__)


class CoinGeckoGlobalSource:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def global_data(self) -> tuple[dict[str, object], datetime]:
        headers = {}
        if (
            self._settings.coingecko_api_key
            and str(self._settings.coingecko_api_key).startswith("CG-")
        ):
            headers["x-cg-demo-api-key"] = self._settings.coingecko_api_key
        url = f"{self._settings.coingecko_api_base_url.rstrip('/')}/global"
        try:
            response = await self._client.get(url, headers=headers)
        except httpx.HTTPError as error:
            logger.warning("coingecko_request_failed error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "CoinGecko", "Global market data could not be reached."
            ) from error
        if response.status_code == 429:
            raise ProviderRateLimited("CoinGecko", response.headers.get("Retry-After"))
        if response.is_error:
            raise ProviderUnavailable(
                "CoinGecko", f"Global market provider returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
            data = payload["data"]
            if not isinstance(data, dict):
                raise TypeError("data must be an object")
            return data, datetime.now(UTC)
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderUnavailable(
                "CoinGecko", "Global market provider returned invalid data."
            ) from error
