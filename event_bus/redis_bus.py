import json
import logging
import asyncio
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import redis.asyncio as redis
from .event_bus import EventBus, Event

logger = logging.getLogger("redis_bus")


class RedisEventBus(EventBus):
    """Redis Streams implementation of the Event Bus."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        source_name: str = "raphael-core",
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.source_name = source_name
        self._redis: Optional[redis.Redis] = None
        self._subscriptions: List[asyncio.Task] = []
        self._running = False

    async def connect(self):
        if not self._redis:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            logger.info(f"Connected to Redis at {self.host}:{self.port}")

    async def publish(self, event: Event):
        if not self._redis:
            await self.connect()

        # Ensure source is set if missing
        if event.source == "unknown":
            event.source = self.source_name

        # Serialize
        data = {
            "id": event.id,
            "topic": event.topic,
            "payload": json.dumps(event.payload),
            "timestamp": event.timestamp.isoformat(),
            "correlation_id": event.correlation_id or "",
            "source": event.source,
        }

        # Redis Stream XADD
        await self._redis.xadd(event.topic, data)
        logger.debug(f"Published event {event.id} to {event.topic}")

    async def subscribe(self, topic: str, callback: Callable[[Event], Any]):
        # We don't need the shared connection for subscribing,
        # but we ensure we are connected mostly for publishing.
        if not self._redis:
            await self.connect()

        self._running = True
        logger.info(f"Subscribing to topic: {topic}")

        async def _listen():
            # Create a dedicated connection for this subscription to avoid blocking
            # other operations on the shared connection (like publish or other subscribes)
            sub_redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )

            # Start reading from new messages ($)
            last_id = "$"
            try:
                while self._running:
                    try:
                        # XREAD block=1000ms
                        streams = await sub_redis.xread(
                            {topic: last_id}, count=10, block=1000
                        )
                        if streams:
                            for _, messages in streams:
                                for msg_id, content in messages:
                                    last_id = msg_id
                                    try:
                                        # Deserialize
                                        payload_str = content.get("payload", "{}")
                                        event = Event(
                                            id=content.get("id", ""),
                                            topic=content.get("topic", topic),
                                            payload=json.loads(payload_str),
                                            timestamp=datetime.fromisoformat(
                                                content.get(
                                                    "timestamp",
                                                    datetime.utcnow().isoformat(),
                                                )
                                            ),
                                            correlation_id=content.get("correlation_id")
                                            or None,
                                            source=content.get("source", "unknown"),
                                        )

                                        if asyncio.iscoroutinefunction(callback):
                                            await callback(event)
                                        else:
                                            callback(event)
                                    except Exception as e:
                                        logger.error(
                                            f"Error processing message {msg_id}: {e}"
                                        )
                    except Exception as e:
                        if self._running:
                            logger.error(
                                f"Error in Redis subscription loop for {topic}: {e}"
                            )
                            await asyncio.sleep(1)
            finally:
                await sub_redis.close()

        task = asyncio.create_task(_listen())
        self._subscriptions.append(task)

    async def close(self):
        self._running = False
        for task in self._subscriptions:
            task.cancel()

        # Wait for tasks to cancel?
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
