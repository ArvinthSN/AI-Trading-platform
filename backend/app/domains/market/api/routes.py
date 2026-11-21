from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.data_sources.rss import RssNewsSource
from app.core.database import get_database_session
from app.core.errors import ProviderUnavailable
from app.core.http import get_http_client
from app.core.research import OpenAIResearchProvider, ResearchEvidence
from app.domains.market.data_sources.binance_stream import BinanceTickerStream
from app.domains.market.data_sources.coinbase_ticker_stream import CoinbaseTickerStream
from app.domains.market.data_sources.kraken_candle_stream import KrakenCandleStream
from app.domains.market.data_sources.kraken_ticker_stream import KrakenTickerStream
from app.domains.market.indicators.service import calculate_indicators
from app.domains.market.repositories.watchlists import WatchlistRepository
from app.domains.market.router.provider_router import ProviderRouter
from app.domains.market.schemas.market import (
    CandleResponse,
    IndicatorParameters,
    IndicatorResponse,
    Instrument,
    MarketBreadth,
    MarketMovers,
    MarketNewsItem,
    MarketNewsResponse,
    MarketResearchRequest,
    MarketResearchResponse,
    Ticker,
    WatchlistCreate,
    WatchlistItemAdd,
    WatchlistResponse,
)
from app.domains.market.schemas.providers import ProviderDiagnostic, ProviderHealth
from app.domains.market.services.candle_cache import candle_is_fresh
from app.domains.market.services.market import build_market_views

router = APIRouter()
INTERVALS = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
DbSession = Annotated[AsyncSession, Depends(get_database_session)]
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}


def _provider_router(request) -> ProviderRouter:
    return request.app.state.market_router


def _watchlist_schema(model) -> WatchlistResponse:
    return WatchlistResponse(
        id=str(model.id),
        name=model.name,
        created_at=model.created_at,
        instruments=[{"symbol": item.symbol} for item in model.instruments],
    )


@router.get("/tickers", response_model=list[Ticker])
async def list_tickers(
    request: Request,
    quote_asset: str = Query(default="USDT", pattern=r"^[A-Z0-9]{2,12}$"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[Ticker]:
    tickers = await _provider_router(request).get_tickers()
    eligible_tickers = [
        ticker
        for ticker in tickers
        if ticker.symbol.endswith(quote_asset)
    ]
    return sorted(
        eligible_tickers,
        key=lambda ticker: ticker.volume_24h,
        reverse=True,
    )[:limit]


@router.get("/instruments", response_model=list[Instrument])
async def list_instruments(
    request: Request,
    quote_asset: str = Query(default="USDT", pattern=r"^[A-Z0-9]{2,12}$"),
) -> list[Instrument]:
    instruments = await _provider_router(request).get_instruments()
    return [
        instrument
        for instrument in instruments
        if instrument.quote_asset == quote_asset
    ]


@router.get("/candles", response_model=CandleResponse)
async def list_candles(
    request: Request,
    symbol: str = Query(pattern=r"^[A-Za-z0-9]{5,30}$"),
    interval: str = Query(default="1h"),
    limit: int = Query(default=500, ge=1, le=1000),
    provider: str | None = Query(default=None, pattern=r"^(binance|kraken|coinbase)$"),
) -> CandleResponse:
    if interval not in INTERVALS:
        raise HTTPException(status_code=422, detail="Unsupported candle interval.")
    candles, provider_name = await _provider_router(request).get_candles(
        symbol,
        interval,
        limit,
        provider,
    )
    if not candles:
        raise HTTPException(status_code=404, detail="No validated candles were returned.")
    return CandleResponse(
        symbol=symbol.upper(),
        interval=interval,
        candles=candles,
        source=provider_name,
        updated_at=datetime.now(UTC),
        last_candle_time=candles[-1].time,
        is_stale=not candle_is_fresh(candles[-1], INTERVAL_SECONDS[interval]),
    )


@router.get("/indicators", response_model=IndicatorResponse)
async def get_indicators(
    request: Request,
    parameters: Annotated[IndicatorParameters, Query()],
    symbol: str = Query(pattern=r"^[A-Za-z0-9]{5,30}$"),
    interval: str = Query(default="1h"),
    limit: int = Query(default=500, ge=1, le=1000),
) -> IndicatorResponse:
    if interval not in INTERVALS:
        raise HTTPException(status_code=422, detail="Unsupported candle interval.")
    candles, provider_name = await _provider_router(request).get_candles(
        symbol,
        interval,
        limit,
    )
    if not candles:
        raise HTTPException(status_code=404, detail="No validated candles were returned.")
    indicators = calculate_indicators(
        [candle.time for candle in candles],
        [candle.open for candle in candles],
        [candle.high for candle in candles],
        [candle.low for candle in candles],
        [candle.close for candle in candles],
        [candle.volume for candle in candles],
        parameters,
    )
    return IndicatorResponse(
        symbol=symbol.upper(),
        interval=interval,
        parameters=parameters,
        indicators=indicators,
        source=f"{provider_name} + NEXTRADE deterministic indicators",
        updated_at=datetime.now(UTC),
    )


async def _market_views(request: Request, quote_asset: str, limit: int):
    router = _provider_router(request)
    instruments = await router.get_instruments()
    tickers = await router.get_tickers()
    eligible = {
        item.symbol
        for item in instruments
        if item.quote_asset == quote_asset
    }
    return build_market_views(tickers, eligible, limit=limit)


@router.get("/breadth", response_model=MarketBreadth)
async def get_breadth(
    request: Request,
    quote_asset: str = Query(default="USDT", pattern=r"^[A-Z0-9]{2,12}$"),
    limit: int = Query(default=10, ge=1, le=100),
) -> MarketBreadth:
    breadth, _ = await _market_views(request, quote_asset, limit)
    return breadth


@router.get("/movers", response_model=MarketMovers)
async def get_movers(
    request: Request,
    quote_asset: str = Query(default="USDT", pattern=r"^[A-Z0-9]{2,12}$"),
    limit: int = Query(default=10, ge=1, le=100),
) -> MarketMovers:
    _, movers = await _market_views(request, quote_asset, limit)
    return movers


@router.get("/tickers/{symbol}", response_model=Ticker)
async def get_ticker(
    symbol: str,
    request: Request,
) -> Ticker:
    tickers = await _provider_router(request).get_tickers()
    normalized = symbol.upper().replace("-", "").replace("/", "")
    ticker = next(
        (
            item
            for item in tickers
            if item.symbol.replace("-", "").replace("/", "") == normalized
        ),
        None,
    )
    if ticker is None:
        raise HTTPException(status_code=404, detail="Compatible ticker not found.")
    return ticker


@router.get("/orderbook/{symbol}")
async def get_orderbook(
    symbol: str,
    request: Request,
    depth: int = Query(default=25, ge=1, le=500),
    provider: str | None = Query(default=None, pattern=r"^(kraken|coinbase)$"),
) -> dict:
    return await _provider_router(request).get_orderbook(symbol, depth, provider)


@router.get("/trades/{symbol}")
async def get_trades(
    symbol: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    provider: str | None = Query(default=None, pattern=r"^(kraken|coinbase)$"),
) -> list[dict]:
    return await _provider_router(request).get_trades(symbol, limit, provider)


@router.get("/providers", response_model=list[ProviderDiagnostic])
async def get_providers(request: Request) -> list[ProviderDiagnostic]:
    return _provider_router(request).diagnostics()


@router.get("/providers/health", response_model=list[ProviderHealth])
async def get_provider_health(request: Request) -> list[ProviderHealth]:
    return _provider_router(request).health_snapshots()


@router.get("/exchange-comparison/{symbol}")
async def get_exchange_comparison(
    symbol: str,
    request: Request,
) -> dict:
    router = _provider_router(request)
    comparisons: dict[str, dict] = {}
    for provider_name in ("kraken", "coinbase"):
        provider = router.providers.get(provider_name)
        if provider is None:
            continue
        try:
            tickers = await provider.get_tickers()
            normalized = symbol.upper().replace("-", "").replace("/", "")
            ticker = next(
                (
                    item
                    for item in tickers
                    if item.symbol.replace("-", "").replace("/", "") == normalized
                ),
                None,
            )
            if ticker is not None:
                comparisons[provider_name] = {
                    "price": ticker.price,
                    "volume_24h": ticker.volume_24h,
                    "change_24h": ticker.change_24h,
                    "source": ticker.source,
                    "updated_at": ticker.updated_at,
                }
        except ProviderUnavailable:
            continue
    if len(comparisons) < 2:
        return {
            "symbol": symbol,
            "status": "partial",
            "providers": comparisons,
            "absolute_difference": None,
            "percentage_difference": None,
            "reason": "One or both exchange providers are unavailable.",
        }
    prices = [
        float(comparisons[name]["price"])
        for name in ("kraken", "coinbase")
    ]
    difference = abs(prices[0] - prices[1])
    percentage = (
        difference / min(prices) * 100
        if min(prices) != 0
        else None
    )
    return {
        "symbol": symbol,
        "status": "available",
        "providers": comparisons,
        "absolute_difference": difference,
        "percentage_difference": percentage,
    }


@router.get("/news", response_model=MarketNewsResponse)
async def get_market_news(client=Depends(get_http_client)) -> MarketNewsResponse:
    feed_url = get_settings().news_rss_url
    if not feed_url:
        return MarketNewsResponse(
            status="unavailable",
            reason="No verified market-news RSS provider is configured.",
            items=[],
        )
    source, updated_at, articles = await RssNewsSource(client).fetch(feed_url, "market-news")
    return MarketNewsResponse(
        status="available",
        source=source,
        updated_at=updated_at,
        items=[
            MarketNewsItem(
                id=item.id,
                headline=item.headline,
                source=item.source,
                published_at=item.published_at,
                original_url=item.original_url,
            )
            for item in articles
        ],
    )


@router.post("/research", response_model=MarketResearchResponse)
async def post_market_research(
    payload: MarketResearchRequest,
    request: Request,
) -> MarketResearchResponse:
    if payload.interval not in INTERVALS:
        raise HTTPException(status_code=422, detail="Unsupported candle interval.")
    candles, provider_name = await _provider_router(request).get_candles(
        payload.symbol,
        payload.interval,
        500,
    )
    if not candles:
        raise HTTPException(status_code=404, detail="No validated market candles are available.")
    evidence = [
        ResearchEvidence(
            id=f"candle-{payload.symbol.upper()}-{index}",
            source=f"{provider_name} historical candles",
            observed_at=candle.time,
            content=(
                f"OHLCV {candle.open}, {candle.high}, {candle.low}, {candle.close}, "
                f"{candle.volume}; interval={payload.interval}; closed={candle.is_closed}"
            ),
        )
        for index, candle in enumerate(candles[-5:])
    ]
    result = await OpenAIResearchProvider(get_settings()).analyze(
        payload.question,
        evidence,
    )
    return MarketResearchResponse(
        **result.model_dump(),
        symbol=payload.symbol.upper(),
        interval=payload.interval,
    )


@router.get("/watchlists", response_model=list[WatchlistResponse])
async def list_watchlists(
    user: CurrentUser,
    session: DbSession,
) -> list[WatchlistResponse]:
    records = await WatchlistRepository(session).list_for_owner(user.subject)
    return [_watchlist_schema(record) for record in records]


@router.post(
    "/watchlists",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_watchlist(
    payload: WatchlistCreate,
    user: CurrentUser,
    session: DbSession,
) -> WatchlistResponse:
    record = await WatchlistRepository(session).create(user.subject, payload.name)
    return _watchlist_schema(record)


@router.delete("/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    deleted = await WatchlistRepository(session).delete(user.subject, watchlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist not found.")


@router.post("/watchlists/{watchlist_id}/instruments", response_model=WatchlistResponse)
async def add_watchlist_instrument(
    watchlist_id: UUID,
    payload: WatchlistItemAdd,
    user: CurrentUser,
    session: DbSession,
) -> WatchlistResponse:
    record = await WatchlistRepository(session).add_instrument(
        user.subject,
        watchlist_id,
        payload.symbol,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")
    return _watchlist_schema(record)


@router.delete(
    "/watchlists/{watchlist_id}/instruments/{symbol}",
    response_model=WatchlistResponse,
)
async def remove_watchlist_instrument(
    watchlist_id: UUID,
    symbol: str,
    user: CurrentUser,
    session: DbSession,
) -> WatchlistResponse:
    record = await WatchlistRepository(session).remove_instrument(
        user.subject,
        watchlist_id,
        symbol,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")
    return _watchlist_schema(record)


@router.websocket("/stream")
async def stream_market(
    websocket: WebSocket,
    symbol: str | None = Query(default=None, pattern=r"^[A-Za-z0-9]{5,30}$"),
) -> None:
    normalized_symbol = symbol.upper() if symbol else None
    await websocket.accept()
    try:
        try:
            stream = KrakenTickerStream(get_settings())
            async for ticker in stream.stream(normalized_symbol):
                await websocket.send_json(
                    {"type": "market_update", "data": ticker.model_dump(mode="json")}
                )
        except ProviderUnavailable:
            stream = CoinbaseTickerStream(get_settings())
            async for ticker in stream.stream(normalized_symbol):
                await websocket.send_json(
                    {"type": "market_update", "data": ticker.model_dump(mode="json")}
                )
    except WebSocketDisconnect:
        return
    except ProviderUnavailable:
        await websocket.close(code=1013, reason="Market provider is unavailable.")


@router.websocket("/stream/candles")
async def stream_candles(
    websocket: WebSocket,
    symbol: str = Query(pattern=r"^[A-Za-z0-9]{5,30}$"),
    interval: str = Query(default="1h"),
) -> None:
    normalized_symbol = symbol.upper()
    if interval not in INTERVALS:
        await websocket.close(code=4400, reason="Unsupported candle interval.")
        return
    await websocket.accept()
    try:
        stream = KrakenCandleStream(get_settings())
        async for candle in stream.stream(normalized_symbol, interval):
            await websocket.send_json(
                {
                    "type": "candle_update",
                    "data": candle.model_dump(mode="json"),
                }
            )
    except WebSocketDisconnect:
        return
    except ProviderUnavailable:
        await websocket.close(code=1013, reason="Candle provider is unavailable.")
