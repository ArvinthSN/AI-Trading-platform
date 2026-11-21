import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class AgentEventHub:
    """In-process stream fanout; persistent events remain in PostgreSQL."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    async def publish(self, owner_id: str, message: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers[owner_id]):
            await queue.put(message)

    @asynccontextmanager
    async def subscribe(self, owner_id: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[owner_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[owner_id].discard(queue)
            if not self._subscribers[owner_id]:
                self._subscribers.pop(owner_id, None)
