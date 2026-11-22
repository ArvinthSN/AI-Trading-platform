import httpx

from app.core.config import Settings
from app.core.errors import ProviderUnavailable


class PaperPortfolioProvider:
    """Read-only adapter for the configured NEXTRADE paper engine."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._url = settings.paper_trading_engine_url
        self._token = settings.paper_trading_engine_token

    @property
    def configured(self) -> bool:
        return bool(self._url and self._token)

    async def get(
        self,
        resource: str,
        user_id: str,
        params: dict[str, str] | None = None,
    ):
        if not self.configured:
            raise ProviderUnavailable(
                "Paper Trading Engine",
                "Paper Trading Engine is not configured.",
            )
        try:
            response = await self._client.get(
                f"{self._url.rstrip('/')}/api/v1/paper/portfolio/{resource}",
                params={**(params or {}), "user_id": user_id},
                headers={"Authorization": f"Bearer {self._token}"} if self._token else {},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderUnavailable(
                "Paper Trading Engine",
                f"Paper portfolio {resource} request failed.",
            ) from error
