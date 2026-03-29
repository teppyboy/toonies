import asyncio
from dataclasses import dataclass, field

from toonies_server.config import BROADCAST_QUEUE_SIZE


@dataclass
class AppState:
    # key: username (str)
    users: dict = field(default_factory=dict)
    # key: session_id (str UUID)
    sessions: dict = field(default_factory=dict)

    _subscribers: list = field(default_factory=list)
    # Lock for composite operations (check-then-insert) that must be atomic.
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=BROADCAST_QUEUE_SIZE)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def broadcast(self, msg: dict | str) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # slow subscriber; message dropped (same as Rust Lagged behaviour)
