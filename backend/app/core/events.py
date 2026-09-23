import asyncio
import json
from typing import Callable, Set, Any
import logging

logger = logging.getLogger("multilink.events")

class EventBus:
    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def emit(self, event_type: str, data: Any) -> None:
        """
        Emit an event to all connected subscriber queues.
        """
        payload = {
            "type": event_type,
            "data": data
        }
        for q in list(self._subscribers):
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(payload)
            except Exception as e:
                logger.debug(f"Failed to deliver event to subscriber: {e}")

event_bus = EventBus()
