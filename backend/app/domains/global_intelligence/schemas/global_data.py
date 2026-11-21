from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.core.research import EvidenceResearchResult


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class GlobalMetric(BaseModel):
    value: float | int | str | None
    change_24h: float | None = None
    unit: str | None = None
    source: str | None = None
    updated_at: datetime | None = None
    status: Availability
    reason: str | None = None


class GlobalMetricsResponse(BaseModel):
    btc_price: GlobalMetric
    btc_dominance: GlobalMetric
    total_market_cap: GlobalMetric
    volume_24h: GlobalMetric
    fear_and_greed: GlobalMetric
    market_trend: GlobalMetric


class GeographicRegion(BaseModel):
    id: str
    name: str
    center_latitude: float
    center_longitude: float
    data_status: Availability
    source: str | None = None
    updated_at: datetime | None = None
    developments: list[str] = Field(default_factory=list)


class RegionListResponse(BaseModel):
    regions: list[GeographicRegion]


class GlobalNewsItem(BaseModel):
    id: str
    headline: str
    source: str
    published_at: datetime
    asset: str | None = None
    region: str | None = None
    original_url: HttpUrl
    category: str


class NewsResponse(BaseModel):
    category: str
    status: Availability
    source: str | None = None
    updated_at: datetime | None = None
    items: list[GlobalNewsItem]
    reason: str | None = None


class EconomicCalendarEvent(BaseModel):
    id: str
    occurred_at: datetime
    country: str
    event: str
    importance: Literal["low", "medium", "high", "unknown"]
    source: str
    original_url: HttpUrl | None = None


class EconomicCalendarResponse(BaseModel):
    status: Availability
    source: str | None = None
    updated_at: datetime | None = None
    events: list[EconomicCalendarEvent]
    reason: str | None = None


class VerifiedGlobalEvent(BaseModel):
    id: str
    description: str
    category: str
    region: str
    source: str
    published_at: datetime
    original_url: HttpUrl
    verified_facts: list[str]
    potential_market_implications: str | None = None
    interpretation_source: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "VerifiedGlobalEvent":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class GlobalEventResponse(BaseModel):
    status: Availability
    source: str | None = None
    updated_at: datetime | None = None
    events: list[VerifiedGlobalEvent]
    reason: str | None = None


class GlobalResearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    region_id: str | None = None


class GlobalResearchResult(EvidenceResearchResult):
    pass
