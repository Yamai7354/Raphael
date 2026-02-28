import asyncio
import logging
from typing import Callable, Coroutine, Dict, List, Set, Any
from src.raphael.core.schemas import SystemEvent, EventType

logger = logging.getLogger(__name__)


class SystemEventBus:
    """
    Central Asynchronous Pub/Sub Message Bus for Raphael.
    Routes `SystemEvent` objects between the 13 foundational layers.
    """

    def __init__(self):
        # Event type to list of callback functions (subscribers)
        self._subscribers: Dict[
            EventType, List[Callable[[SystemEvent], Coroutine[Any, Any, None]]]
        ] = {event_type: [] for event_type in EventType}
        # The main asynchronous queue processing all events
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: bool = False
        self._worker_task: asyncio.Task | None = None

    def subscribe(
        self, event_type: EventType, callback: Callable[[SystemEvent], Coroutine[Any, Any, None]]
    ):
        """
        Register an async callback to listen for specific EventTypes.
        Example: Layer 3 parser subscribes to EventType.OBSERVATION.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed callback {callback.__name__} to {event_type.value}")

    async def publish(self, event: SystemEvent):
        """
        Send an event to the bus. Evaluated by Priority Queue (lower int = higher priority).
        Since standard PriorityQueue orders by tuple, we use (priority, timestamp, event)
        to prevent blocking and ensure strict routing.
        """
        # Queue item format: (Priority, Timestamp string, Event Object)
        queue_item = (event.priority, event.timestamp.isoformat(), event)
        await self._queue.put(queue_item)
        logger.debug(f"Published event {event.event_id} of type {event.event_type.value}")

    async def start(self):
        """Start the background consumer loop pulling from the queue."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._consume())
        logger.info("System Event Bus started.")

    async def stop(self):
        """Gracefully shutdown the event bus processor."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("System Event Bus stopped.")

    async def _consume(self):
        """Background loop executing subscriber callbacks."""
        while self._running:
            try:
                # Fetch next highest priority event
                priority, timestamp_str, event = await self._queue.get()

                # Fetch all registered subscribers
                subscribers = self._subscribers.get(event.event_type, [])

                if subscribers:
                    # Execute all subscribers concurrently for speed
                    tasks = [asyncio.create_task(callback(event)) for callback in subscribers]
                    await asyncio.gather(*tasks, return_exceptions=True)

                # Mark as processed
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event queue: {e}")
