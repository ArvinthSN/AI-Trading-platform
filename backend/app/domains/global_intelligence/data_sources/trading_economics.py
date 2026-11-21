import logging
from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.core.errors import ProviderRateLimited, ProviderUnavailable
from app.domains.global_intelligence.schemas.global_data import EconomicCalendarEvent

logger = logging.getLogger(__name__)


class TradingEconomicsCalendarSource:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def events(self) -> tuple[str, datetime, list[EconomicCalendarEvent]]:
        api_key = self._settings.trading_economics_api_key
        if not api_key:
            raise ProviderUnavailable(
                "Trading Economics",
                "Economic calendar credentials are not configured.",
            )
        url = f"{self._settings.trading_economics_api_base_url.rstrip('/')}/calendar"
        try:
            response = await self._client.get(url, params={"c": api_key, "f": "json"})
        except httpx.HTTPError as error:
            logger.warning("economic_calendar_request_failed error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "Trading Economics", "Economic calendar could not be reached."
            ) from error
        if response.status_code == 429:
            raise ProviderRateLimited("Trading Economics", response.headers.get("Retry-After"))
        if response.is_error:
            raise ProviderUnavailable(
                "Trading Economics", f"Economic calendar returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
            if not isinstance(payload, list):
                raise TypeError("calendar response must be a list")
        except (ValueError, TypeError) as error:
            raise ProviderUnavailable(
                "Trading Economics", "Economic calendar returned invalid data."
            ) from error
        events: list[EconomicCalendarEvent] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                raw_date = row.get("Date")
                if not isinstance(raw_date, str):
                    continue
                occurred_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                if occurred_at.tzinfo is None:
                    logger.warning("economic_event_timezone_missing event=%s", row.get("Event"))
                    continue
                importance_raw = str(row.get("Importance", "")).lower()
                importance = (
                    "high"
                    if importance_raw in {"3", "high"}
                    else "medium"
                    if importance_raw in {"2", "medium"}
                    else "low"
                    if importance_raw in {"1", "low"}
                    else "unknown"
                )
                event_id = str(row.get("CalendarId") or row.get("Event") or "")
                country = str(row.get("Country") or "")
                event_name = str(row.get("Event") or "")
                source_name = str(row.get("Source") or "Trading Economics")
                if not event_id or not country or not event_name:
                    continue
                events.append(
                    EconomicCalendarEvent(
                        id=event_id,
                        occurred_at=occurred_at.astimezone(UTC),
                        country=country,
                        event=event_name,
                        importance=importance,
                        source=source_name,
                        original_url=row.get("URL"),
                    )
                )
            except (TypeError, ValueError):
                logger.warning("economic_event_invalid")
        return "Trading Economics", datetime.now(UTC), events
