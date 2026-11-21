from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.market.models.watchlist import Watchlist, WatchlistInstrument


class WatchlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_owner(self, owner_id: str) -> list[Watchlist]:
        statement = (
            select(Watchlist)
            .where(Watchlist.owner_id == owner_id)
            .order_by(Watchlist.created_at, Watchlist.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def create(self, owner_id: str, name: str) -> Watchlist:
        watchlist = Watchlist(owner_id=owner_id, name=name.strip())
        self._session.add(watchlist)
        await self._session.commit()
        await self._session.refresh(watchlist)
        return watchlist

    async def delete(self, owner_id: str, watchlist_id: UUID) -> bool:
        statement = select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == owner_id,
        )
        watchlist = await self._session.scalar(statement)
        if watchlist is None:
            return False
        await self._session.delete(watchlist)
        await self._session.commit()
        return True

    async def add_instrument(
        self,
        owner_id: str,
        watchlist_id: UUID,
        symbol: str,
    ) -> Watchlist | None:
        statement = select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == owner_id,
        )
        watchlist = await self._session.scalar(statement)
        if watchlist is None:
            return None
        normalized = symbol.upper()
        if not any(item.symbol == normalized for item in watchlist.instruments):
            watchlist.instruments.append(WatchlistInstrument(symbol=normalized))
            await self._session.commit()
            await self._session.refresh(watchlist)
        return watchlist

    async def remove_instrument(
        self,
        owner_id: str,
        watchlist_id: UUID,
        symbol: str,
    ) -> Watchlist | None:
        statement = select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == owner_id,
        )
        watchlist = await self._session.scalar(statement)
        if watchlist is None:
            return None
        normalized = symbol.upper()
        found = next((item for item in watchlist.instruments if item.symbol == normalized), None)
        if found is not None:
            watchlist.instruments.remove(found)
            await self._session.commit()
            await self._session.refresh(watchlist)
        return watchlist
