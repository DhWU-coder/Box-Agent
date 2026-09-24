"""Host-neutral delivery of ordered run events."""
from __future__ import annotations

import asyncio
from typing import Any

from .api import EventEnvelope


class RunEventChannel:
    END = object()

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._sequence = 0

    async def publish(self, run_id: str, payload: Any) -> None:
        self._sequence += 1
        await self._queue.put(EventEnvelope(
            run_id=run_id, event_id=f"{run_id}:{self._sequence}",
            sequence=self._sequence, payload=payload,
        ))

    async def get(self) -> Any:
        return await self._queue.get()

    def close(self) -> None:
        self._queue.put_nowait(self.END)
