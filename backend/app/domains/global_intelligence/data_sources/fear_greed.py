import logging
from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.core.errors import ProviderRateLimited, ProviderUnavailable

logger = logging.getLogger(__name__)


class FearAndGreedSource:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._url = settings.fear_greed_api_url

    async def latest(self) -> tuple[int, datetime]:
        try:
            response = await self._client.get(self._url, params={"limit": 1})
        except httpx.HTTPError as error:
            logger.warning("fear_greed_request_failed error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "Alternative.me Fear & Greed", "Sentiment provider could not be reached."
            ) from error
        if response.status_code == 429:
            raise ProviderRateLimited(
                "Alternative.me Fear & Greed", response.headers.get("Retry-After")
            )
        if response.is_error:
            raise ProviderUnavailable(
                "Alternative.me Fear & Greed",
                f"Sentiment provider returned HTTP {response.status_code}.",
            )
        try:
            item = response.json()["data"][0]
            value = int(item["value"])
            observed = datetime.fromtimestamp(int(item["timestamp"]), tz=UTC)
            if not 0 <= value <= 100:
                raise ValueError("sentiment is outside the documented range")
            return value, observed
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise ProviderUnavailable(
                "Alternative.me Fear & Greed", "Sentiment provider returned invalid data."
            ) from error
