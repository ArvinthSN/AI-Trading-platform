from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ProviderHealth(BaseModel):
    name: str
    active: bool
    connected: bool
    websocket_state: Literal["connected", "disconnected", "unsupported"]
    last_success_at: datetime | None
    last_error_at: datetime | None
    latency_ms: float | None
    request_error_count: int
    rate_limited: bool
    freshness_status: Literal["fresh", "stale", "unavailable"]
    routing_role: Literal["primary", "secondary", "global", "inactive"]


class ProviderDiagnostic(BaseModel):
    name: str
    active: bool
    capabilities: list[str]
    public_market_data: bool
    authentication_required_for_public_data: bool
    configuration_status: Literal["configured", "public", "unavailable"]
