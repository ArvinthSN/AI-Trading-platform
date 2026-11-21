from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.domains.agents import models as agent_models  # noqa: E402,F401
from app.domains.market.models import watchlist as watchlist_models  # noqa: E402,F401
