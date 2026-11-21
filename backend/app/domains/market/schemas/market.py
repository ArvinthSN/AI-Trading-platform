from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.core.research import EvidenceResearchResult


class ProviderMetadata(BaseModel):
    source: str
    updated_at: datetime


class Ticker(BaseModel):
    symbol: str
    price: float
    change_24h: float
    volume_24h: float
    updated_at: datetime
    source: str = "Binance Spot"


class Instrument(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    source: str = "Binance Spot"


class Candle(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool

    model_config = ConfigDict(frozen=True)


class CandleResponse(ProviderMetadata):
    symbol: str
    interval: str
    candles: list[Candle]
    last_candle_time: datetime
    is_stale: bool


class IndicatorParameters(BaseModel):
    ema_periods: list[int] = Field(default=[20, 50, 200], min_length=1, max_length=5)
    sma_period: int = Field(default=20, ge=2, le=500)
    adx_period: int = Field(default=14, ge=2, le=200)
    rsi_period: int = Field(default=14, ge=2, le=200)
    macd_fast: int = Field(default=12, ge=2, le=100)
    macd_slow: int = Field(default=26, ge=3, le=200)
    macd_signal: int = Field(default=9, ge=2, le=100)
    stochastic_period: int = Field(default=14, ge=2, le=200)
    stochastic_smooth: int = Field(default=3, ge=1, le=50)
    atr_period: int = Field(default=14, ge=2, le=200)
    bollinger_period: int = Field(default=20, ge=2, le=200)
    bollinger_stddev: float = Field(default=2.0, gt=0, le=5)
    volume_sma_period: int = Field(default=20, ge=2, le=500)

    @model_validator(mode="after")
    def validate_macd_order(self) -> "IndicatorParameters":
        if self.macd_fast >= self.macd_slow:
            raise ValueError("macd_fast must be less than macd_slow")
        if len(set(self.ema_periods)) != len(self.ema_periods):
            raise ValueError("ema_periods must be unique")
        return self


class IndicatorSeries(BaseModel):
    times: list[datetime]
    ema: dict[int, list[float | None]]
    sma: list[float | None]
    adx: list[float | None]
    rsi: list[float | None]
    macd: list[float | None]
    macd_signal: list[float | None]
    macd_histogram: list[float | None]
    stochastic_k: list[float | None]
    stochastic_d: list[float | None]
    atr: list[float | None]
    bollinger_upper: list[float | None]
    bollinger_middle: list[float | None]
    bollinger_lower: list[float | None]
    volume_sma: list[float | None]
    volume_change_percent: list[float | None]


class IndicatorResponse(ProviderMetadata):
    symbol: str
    interval: str
    parameters: IndicatorParameters
    indicators: IndicatorSeries


class BreadthCount(BaseModel):
    count: int
    percent: float | None


class VolumeShare(BaseModel):
    symbol: str
    quote_volume: float
    share_percent: float | None


class MarketBreadth(ProviderMetadata):
    eligible_universe: str
    total_tracked: int
    gainers: BreadthCount
    losers: BreadthCount
    unchanged: BreadthCount
    volume_distribution: list[VolumeShare]
    market_strength: float | None


class MarketMovers(ProviderMetadata):
    gainers: list[Ticker]
    losers: list[Ticker]
    highest_volume: list[Ticker]


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WatchlistItemAdd(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,30}$")


class WatchlistItemResponse(BaseModel):
    symbol: str


class WatchlistResponse(BaseModel):
    id: str
    name: str
    instruments: list[WatchlistItemResponse]
    created_at: datetime


class MarketDirection(BaseModel):
    direction: Literal["bullish", "bearish", "neutral", "abstain"]
    summary: str
    uncertainty: str
    evidence_ids: list[str]
    generated_at: datetime


class MarketNewsItem(BaseModel):
    id: str
    headline: str
    source: str
    published_at: datetime
    asset: str | None = None
    original_url: HttpUrl


class MarketNewsResponse(BaseModel):
    status: Literal["available", "unavailable"]
    source: str | None = None
    updated_at: datetime | None = None
    items: list[MarketNewsItem]
    reason: str | None = None


class MarketResearchRequest(BaseModel):
    question: str = Field(
        default="Summarize the current technical market evidence.",
        min_length=5,
        max_length=500,
    )
    symbol: str = Field(pattern=r"^[A-Za-z0-9]{5,30}$")
    interval: str = "1h"


class MarketResearchResponse(EvidenceResearchResult):
    symbol: str
    interval: str
