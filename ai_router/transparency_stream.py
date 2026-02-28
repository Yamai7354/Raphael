import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, Optional, Set


class TransparencyStream:
    """In-memory pub/sub stream for dashboard transparency events."""

    def __init__(self, history_size: int = 200, subscriber_queue_size: int = 200):
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_size)
        self._subscribers: Set[asyncio.Queue] = set()
        self._subscriber_queue_size = subscriber_queue_size
        self._lock = asyncio.Lock()

    async def publish(self, event: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_event(event)
        async with self._lock:
            self._history.append(normalized)
            dead_subscribers = []
            for queue in self._subscribers:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(normalized)
                except Exception:
                    dead_subscribers.append(queue)
            for queue in dead_subscribers:
                self._subscribers.discard(queue)
        return normalized

    async def subscribe(self, replay_last: int = 30) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._subscriber_queue_size)
        async with self._lock:
            self._subscribers.add(queue)
            if replay_last > 0:
                for event in list(self._history)[-replay_last:]:
                    if queue.full():
                        break
                    queue.put_nowait(event)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": event.get("type", "decision"),
        "ts": event.get("ts", datetime.utcnow().isoformat() + "Z"),
        "correlation_id": event.get("correlation_id"),
        "task_id": event.get("task_id"),
        "node_id": event.get("node_id"),
        "message": event.get("message", ""),
        "details": event.get("details", {}),
    }


def format_sse(event: Dict[str, Any]) -> str:
    payload = json.dumps(event, ensure_ascii=False)
    return f"event: {event.get('type', 'message')}\ndata: {payload}\n\n"


transparency_stream = TransparencyStream()
