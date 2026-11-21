import logging
from datetime import UTC, datetime
from enum import StrEnum

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.core.data_sources.rss import RssNewsSource
from app.core.errors import ProviderRateLimited, ProviderUnavailable
from app.core.http import get_http_client
from app.core.research import OpenAIResearchProvider, ResearchEvidence
from app.domains.global_intelligence.data_sources.regional import (
    RegionalIntelligenceSource,
)
from app.domains.global_intelligence.data_sources.trading_economics import (
    TradingEconomicsCalendarSource,
)
from app.domains.global_intelligence.schemas.global_data import (
    Availability,
    EconomicCalendarResponse,
    GlobalEventResponse,
    GlobalMetricsResponse,
    GlobalNewsItem,
    GlobalResearchRequest,
    GlobalResearchResult,
    NewsResponse,
    RegionListResponse,
    VerifiedGlobalEvent,
)
from app.domains.global_intelligence.services.metrics import (
    fetch_global_metrics,
)
from app.domains.global_intelligence.services.research import (
    metric_evidence,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class NewsCategory(StrEnum):
    LIVE_FEED = "live_feed"
    NEWS = "news"
    ON_CHAIN = "on_chain"
    REGULATORY = "regulatory"


def _settings() -> Settings:
    return get_settings()


@router.get("/metrics", response_model=GlobalMetricsResponse)
async def get_metrics(
    client: httpx.AsyncClient = Depends(get_http_client),
) -> GlobalMetricsResponse:
    return await fetch_global_metrics(client, _settings())


@router.get("/regions", response_model=RegionListResponse)
async def get_regions(
    client: httpx.AsyncClient = Depends(get_http_client),
) -> RegionListResponse:
    return await RegionalIntelligenceSource(
        client,
        _settings().global_regions_api_url,
    ).regions()


@router.get("/news", response_model=NewsResponse)
async def get_news(
    category: NewsCategory = Query(default=NewsCategory.NEWS),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> NewsResponse:
    settings = _settings()
    feed_url = (
        settings.news_rss_url
        if category in {NewsCategory.LIVE_FEED, NewsCategory.NEWS}
        else settings.regulatory_rss_url
        if category == NewsCategory.REGULATORY
        else None
    )
    if not feed_url:
        message = (
            "No verified on-chain news provider is configured."
            if category == NewsCategory.ON_CHAIN
            else f"No verified {category.value.replace('_', ' ')} provider is configured."
        )
        return NewsResponse(
            category=category.value,
            status=Availability.UNAVAILABLE,
            updated_at=None,
            source=None,
            items=[],
            reason=message,
        )
    source, updated_at, items = await RssNewsSource(client).fetch(feed_url, category.value)
    return NewsResponse(
        category=category.value,
        status=Availability.AVAILABLE,
        source=source,
        updated_at=updated_at,
        items=[
            GlobalNewsItem(
                id=item.id,
                headline=item.headline,
                source=item.source,
                published_at=item.published_at,
                original_url=item.original_url,
                category=category.value,
            )
            for item in items
        ],
    )


async def _global_events(
    client: httpx.AsyncClient,
    endpoint: str | None,
    provider_name: str,
) -> GlobalEventResponse:
    if not endpoint:
        return GlobalEventResponse(
            status=Availability.UNAVAILABLE,
            reason=f"{provider_name} provider is not configured.",
            events=[],
        )
    try:
        response = await client.get(endpoint)
    except httpx.HTTPError as error:
        raise ProviderUnavailable(
            provider_name, "Verified event provider could not be reached."
        ) from error
    if response.status_code == 429:
        raise ProviderRateLimited(provider_name, response.headers.get("Retry-After"))
    if response.is_error:
        raise ProviderUnavailable(provider_name, f"Provider returned HTTP {response.status_code}.")
    try:
        payload = response.json()
        source_name = payload["source"]
        rows = payload["events"]
        if not isinstance(source_name, str) or not isinstance(rows, list):
            raise TypeError("event response shape is invalid")
        events = [VerifiedGlobalEvent.model_validate(row) for row in rows]
        updated_at = datetime.fromisoformat(str(payload["updated_at"]).replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            raise ValueError("provider timestamp must include a timezone")
    except (ValueError, KeyError, TypeError) as error:
        raise ProviderUnavailable(
            provider_name, "Provider returned invalid or un-timestamped events."
        ) from error
    return GlobalEventResponse(
        status=Availability.AVAILABLE,
        source=source_name,
        updated_at=updated_at.astimezone(UTC),
        events=events,
    )


@router.get("/events", response_model=GlobalEventResponse)
async def get_events(
    client: httpx.AsyncClient = Depends(get_http_client),
) -> GlobalEventResponse:
    settings = _settings()
    return await _global_events(
        client,
        settings.global_events_api_url,
        "Global events",
    )


@router.get("/geopolitical-monitor", response_model=GlobalEventResponse)
async def get_geopolitical_monitor(
    client: httpx.AsyncClient = Depends(get_http_client),
) -> GlobalEventResponse:
    settings = _settings()
    return await _global_events(
        client,
        settings.geopolitical_events_api_url,
        "Geopolitical events",
    )


@router.get("/economic-calendar", response_model=EconomicCalendarResponse)
async def get_economic_calendar(
    client: httpx.AsyncClient = Depends(get_http_client),
) -> EconomicCalendarResponse:
    settings = _settings()
    if not settings.trading_economics_api_key:
        return EconomicCalendarResponse(
            status=Availability.UNAVAILABLE,
            reason="Trading Economics credentials are not configured.",
            events=[],
        )
    source, updated_at, events = await TradingEconomicsCalendarSource(
        client,
        settings,
    ).events()
    return EconomicCalendarResponse(
        status=Availability.AVAILABLE,
        source=source,
        updated_at=updated_at,
        events=events,
    )


@router.post("/research", response_model=GlobalResearchResult)
async def post_research(
    payload: GlobalResearchRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> GlobalResearchResult:
    metrics = await fetch_global_metrics(client, _settings())
    evidence: list[ResearchEvidence] = metric_evidence(metrics.model_dump(mode="json"))
    if payload.region_id:
        region_response = await RegionalIntelligenceSource(
            client,
            _settings().global_regions_api_url,
        ).regions()
        regions = {item.id for item in region_response.regions} | {"global"}
        if payload.region_id not in regions:
            raise HTTPException(status_code=404, detail="Region not found.")
        if payload.region_id != "global":
            evidence = []
    settings = _settings()
    if settings.news_rss_url:
        try:
            _, _, articles = await RssNewsSource(client).fetch(
                settings.news_rss_url,
                "global-research-news",
                limit=10,
            )
            evidence.extend(
                ResearchEvidence(
                    id=f"news-{article.id}",
                    source=article.source,
                    observed_at=article.published_at,
                    url=article.original_url,
                    content=article.headline,
                )
                for article in articles
            )
        except ProviderUnavailable as error:
            logger.warning("research_news_unavailable provider=%s", error.provider)
    if not evidence:
        return GlobalResearchResult(
            direction="abstain",
            summary="Insufficient verified source data; analysis abstained.",
            uncertainty="High: no current evidence is available for this scope.",
            evidence=[],
            generated_at=datetime.now(UTC),
            source="NEXTRADE evidence-gated research",
        )
    provider = OpenAIResearchProvider(settings)
    return await provider.analyze(payload.question, evidence)
