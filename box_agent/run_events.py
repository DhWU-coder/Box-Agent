"""Host-neutral delivery of ordered run events."""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from .api import EventEnvelope


class RunEventChannel:
    END = object()

    def __init__(self) -> None:
        self._queue: deque[EventEnvelope] = deque()
        self._changed = asyncio.Event()
        self._closed = False
        self._sequence = 0

    async def publish(self, run_id: str, payload: Any) -> None:
        self._sequence += 1
        if self._closed:
            raise RuntimeError("run event channel is closed")
        self._queue.append(EventEnvelope(
            run_id=run_id, event_id=f"{run_id}:{self._sequence}",
            sequence=self._sequence, payload=payload,
        ))
        self._changed.set()

    async def get(self) -> Any:
        while not self._queue:
            if self._closed:
                return self.END
            self._changed.clear()
            await self._changed.wait()
        return self._queue.popleft()

    def close(self) -> None:
        self._closed = True
        self._changed.set()
