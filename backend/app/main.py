import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import make_url

from app.api import api_router
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import ProviderRateLimited, ProviderUnavailable
from app.core.logging import configure_logging
from app.domains.agents.services.events import AgentEventHub
from app.domains.agents.services.orchestrator import AgentOrchestrator
from app.domains.market.api.routes import stream_market
from app.domains.market.router.provider_router import ProviderRouter

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    timeout = httpx.Timeout(settings.binance_request_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http_client = client
        app.state.market_router = ProviderRouter(client, settings)
        app.state.agent_event_hub = AgentEventHub()
        app.state.agent_simulator = None
        app.state.agent_tuner = None
        if not settings.database_url:
            app.state.agent_orchestrator = None
            yield
        else:
            checkpoint_url = make_url(settings.database_url).set(
                drivername="postgresql"
            ).render_as_string(hide_password=False)
            async with AsyncPostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
                await checkpointer.setup()
                orchestrator = AgentOrchestrator(
                    app.state.market_router,
                    client,
                    settings,
                    get_session_factory(),
                    checkpointer,
                    app.state.agent_event_hub,
                )
                app.state.agent_orchestrator = orchestrator
                await orchestrator.recover()
                yield


app = FastAPI(title="NEXTRADE Intelligence API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router, prefix="/api/v1")
app.add_api_websocket_route("/api/market/stream", stream_market)


@app.exception_handler(ProviderRateLimited)
async def provider_rate_limited_handler(
    request: Request,
    error: ProviderRateLimited,
) -> JSONResponse:
    logger.warning("provider_rate_limited provider=%s path=%s", error.provider, request.url.path)
    headers = {"Retry-After": error.retry_after} if error.retry_after else None
    return JSONResponse(
        status_code=503,
        content={"detail": f"{error.provider} rate limit reached; retry later."},
        headers=headers,
    )


@app.exception_handler(ProviderUnavailable)
async def provider_unavailable_handler(
    request: Request,
    error: ProviderUnavailable,
) -> JSONResponse:
    logger.warning("provider_unavailable provider=%s path=%s", error.provider, request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": f"{error.provider}: {error}"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
