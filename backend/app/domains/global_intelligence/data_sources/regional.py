import logging
from datetime import UTC, datetime

import httpx

from app.core.errors import ProviderUnavailable
from app.domains.global_intelligence.schemas.global_data import (
    Availability,
    GeographicRegion,
    RegionListResponse,
)
from app.domains.global_intelligence.services.metrics import default_regions

logger = logging.getLogger(__name__)


class RegionalIntelligenceSource:
    def __init__(self, client: httpx.AsyncClient, endpoint: str | None) -> None:
        self._client = client
        self._endpoint = endpoint

    async def regions(self) -> RegionListResponse:
        if not self._endpoint:
            return RegionListResponse(
                regions=[GeographicRegion.model_validate(region) for region in default_regions()]
            )
        try:
            response = await self._client.get(self._endpoint)
        except httpx.HTTPError as error:
            logger.warning("regional_provider_failed error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "Regional intelligence", "Regional provider could not be reached."
            ) from error
        if response.status_code == 429:
            from app.core.errors import ProviderRateLimited

            raise ProviderRateLimited(
                "Regional intelligence",
                response.headers.get("Retry-After"),
            )
        if response.is_error:
            raise ProviderUnavailable(
                "Regional intelligence",
                f"Regional provider returned HTTP {response.status_code}.",
            )
        try:
            payload = response.json()
            updated_at = datetime.fromisoformat(str(payload["updated_at"]).replace("Z", "+00:00"))
            if updated_at.tzinfo is None or not isinstance(payload.get("source"), str):
                raise ValueError("source and timezone-aware timestamp are required")
            items = payload["regions"]
            if not isinstance(items, list):
                raise TypeError("regions must be a list")
            regions = [
                GeographicRegion(
                    **item,
                    data_status=Availability.AVAILABLE,
                    source=payload["source"],
                    updated_at=updated_at.astimezone(UTC),
                )
                for item in items
            ]
            return RegionListResponse(regions=regions)
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderUnavailable(
                "Regional intelligence",
                "Regional provider returned invalid or un-timestamped data.",
            ) from error
