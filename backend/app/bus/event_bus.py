"""
Lightweight in-process async pub/sub event bus.

This is the federation backbone: every module (adapters -> ANPR
pipeline -> correlation engine -> API/websocket layer) communicates
by publishing/subscribing to named topics here, never by calling each
other's functions directly. That decoupling is what makes this a real
federation pattern rather than a monolith with extra folders.

For tonight's demo this is implemented with asyncio.Queue per
subscriber, which is explicitly acceptable per spec. In production at
statewide scale (26 departments, ~80k cameras) this same interface
would be backed by Redis Streams or Kafka -- see docs/02-architecture.md
and docs/03-integration-strategy.md. Swapping the backend means
reimplementing this class; nothing above it (publishers/subscribers)
would need to change, since they only depend on publish()/subscribe().
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, AsyncIterator, Callable

logger = logging.getLogger("sentinel.bus")


class Topics:
    FRAMES_INGESTED = "frames.ingested"
    DETECTIONS = "anpr.detections"
    ALERTS = "watchlist.alerts"
    CAMERA_STATUS = "camera.status"
    VEHICLE_SIGHTINGS = "vehicle.sightings"


class EventBus:
    def __init__(self, history_limit: int = 500):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._history: dict[str, list[Any]] = defaultdict(list)
        self._history_limit = history_limit
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, message: Any) -> None:
        async with self._lock:
            self._history[topic].append(message)
            if len(self._history[topic]) > self._history_limit:
                self._history[topic] = self._history[topic][-self._history_limit:]
            queues = list(self._subscribers.get(topic, []))
        logger.debug("publish topic=%s subscribers=%d", topic, len(queues))
        for q in queues:
            await q.put(message)

    def subscribe_now(self, topic: str) -> asyncio.Queue:
        """
        Synchronously register a subscriber queue and return it immediately.
        Use this (via subscribe()) when a consumer task must not miss
        events published between task creation and the first loop
        iteration -- async generators don't run their body until first
        iterated, which is too late for that race.
        """
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[topic].append(q)
        return q

    async def drain(self, topic: str, q: asyncio.Queue) -> AsyncIterator[Any]:
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            async with self._lock:
                if q in self._subscribers[topic]:
                    self._subscribers[topic].remove(q)

    async def subscribe(self, topic: str) -> AsyncIterator[Any]:
        q = self.subscribe_now(topic)
        async for msg in self.drain(topic, q):
            yield msg

    def recent(self, topic: str, limit: int = 50) -> list[Any]:
        items = self._history.get(topic, [])
        return items[-limit:]


# Single process-wide bus instance shared by the whole app.
bus = EventBus()
