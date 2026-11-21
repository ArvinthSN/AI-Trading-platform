from fastapi import APIRouter

from app.domains.agents.api.routes import router as agents_router
from app.domains.global_intelligence.api.routes import router as global_router
from app.domains.market.api.routes import router as market_router

api_router = APIRouter()
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(market_router, prefix="/market", tags=["market"])
api_router.include_router(global_router, prefix="/global", tags=["global"])
