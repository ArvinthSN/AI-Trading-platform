from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Watchlist(Base):
    __tablename__ = "market_watchlists"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_market_watchlist_owner_name"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    instruments: Mapped[list["WatchlistInstrument"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WatchlistInstrument.symbol",
    )


class WatchlistInstrument(Base):
    __tablename__ = "market_watchlist_instruments"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol", name="uq_market_watchlist_symbol"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    watchlist_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_watchlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    watchlist: Mapped[Watchlist] = relationship(back_populates="instruments")
