"""Ingest: the event bus between the feed and the pipeline.

In-memory by default. With REGISTA_BUS=eventhubs the feed is also published
to Azure Event Hubs, the production shape where any number of downstream
consumers (Fabric Real-Time Intelligence, archival, partner broadcasters)
subscribe to the same stream.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Protocol

log = logging.getLogger("regista.bus")


class Bus(Protocol):
    name: str
    published: int

    async def publish(self, kind: str, payload: dict[str, Any]) -> None: ...

    async def close(self) -> None: ...


class InMemoryBus:
    name = "in-memory"

    def __init__(self) -> None:
        self.published = 0

    async def publish(self, kind: str, payload: dict[str, Any]) -> None:
        self.published += 1

    async def close(self) -> None:
        return None


class EventHubsBus:
    """Mirrors the match feed to Azure Event Hubs (batched, fire-and-forget, never blocks the broadcast)."""

    name = "azure-event-hubs"

    def __init__(self) -> None:
        from azure.eventhub.aio import EventHubProducerClient

        conn = os.getenv("EVENTHUB_CONNECTION_STRING")
        hub = os.getenv("EVENTHUB_NAME", "match-events")
        if conn:
            self.client = EventHubProducerClient.from_connection_string(conn, eventhub_name=hub)
        else:
            from azure.identity.aio import DefaultAzureCredential

            self.client = EventHubProducerClient(os.environ["EVENTHUB_NAMESPACE"], hub, DefaultAzureCredential())
        self.queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=5000)
        self.published = 0
        self.task = asyncio.create_task(self._pump())

    async def publish(self, kind: str, payload: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait((kind, payload))
        except asyncio.QueueFull:
            log.warning("event hub queue full; dropping %s", kind)

    async def _pump(self) -> None:
        from azure.eventhub import EventData

        while True:
            items = [await self.queue.get()]
            while not self.queue.empty() and len(items) < 200:
                items.append(self.queue.get_nowait())
            try:
                batch = await self.client.create_batch()
                for kind, payload in items:
                    ed = EventData(json.dumps(payload, default=str))
                    ed.properties = {"kind": kind}
                    batch.add(ed)
                await self.client.send_batch(batch)
                self.published += len(items)
            except Exception as exc:  # noqa: BLE001
                log.warning("event hubs publish failed: %s", exc)

    async def close(self) -> None:
        self.task.cancel()
        await self.client.close()


def make_bus() -> Bus:
    if os.getenv("REGISTA_BUS", "memory").lower() == "eventhubs":
        try:
            return EventHubsBus()
        except Exception as exc:  # noqa: BLE001
            log.warning("Event Hubs unavailable (%s); using in-memory bus", exc)
    return InMemoryBus()
