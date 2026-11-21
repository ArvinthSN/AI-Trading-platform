from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Literal

from app.domains.market.schemas.providers import ProviderHealth


@dataclass
class ProviderHealthState:
    name: str
    active: bool = True
    connected: bool = False
    websocket_state: Literal["connected", "disconnected", "unsupported"] = "disconnected"
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    latency_ms: float | None = None
    request_error_count: int = 0
    rate_limited: bool = False
    routing_role: Literal["primary", "secondary", "global", "inactive"] = "inactive"
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_success(self, latency_ms: float) -> None:
        with self._lock:
            now = datetime.now(UTC)
            self.connected = True
            self.last_success_at = now
            self.latency_ms = latency_ms
            self.rate_limited = False

    def record_error(self) -> None:
        with self._lock:
            self.connected = False
            self.last_error_at = datetime.now(UTC)
            self.request_error_count += 1

    def record_websocket(self, state: Literal["connected", "disconnected"]) -> None:
        with self._lock:
            self.websocket_state = state
            self.connected = state == "connected"

    def snapshot(self) -> ProviderHealth:
        with self._lock:
            if self.last_success_at is None:
                freshness = "unavailable"
            else:
                age = (datetime.now(UTC) - self.last_success_at).total_seconds()
                freshness = "fresh" if age <= 60 else "stale"
            return ProviderHealth(
                name=self.name,
                active=self.active,
                connected=self.connected,
                websocket_state=self.websocket_state,
                last_success_at=self.last_success_at,
                last_error_at=self.last_error_at,
                latency_ms=self.latency_ms,
                request_error_count=self.request_error_count,
                rate_limited=self.rate_limited,
                freshness_status=freshness,
                routing_role=self.routing_role,
            )
