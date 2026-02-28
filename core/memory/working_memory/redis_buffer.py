import logging
import asyncio
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RedisWorkingMemory:
    """
    Working memory implementation using Redis for shared state across agent instances.
    Falls back to in-memory dictionary if Redis is unavailable.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self.client = None
        self._is_redis = False

    async def connect(self):
        if self.client is not None:
            return

        try:
            import redis.asyncio as redis

            self.client = redis.Redis(host=self.host, port=self.port, db=self.db)
            await self.client.ping()
            self._is_redis = True
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except (ImportError, Exception) as e:
            logger.warning(
                f"Redis unavailable ({e}), falling back to in-memory dictionary."
            )
            self.client = {}
            self._is_redis = False

    async def get(self, key: str) -> Any:
        if self.client is None:
            await self.connect()

        if not self._is_redis:
            return self.client.get(key)

        try:
            # Redis returns bytes, we might want to decode or cast
            val = await self.client.get(key)
            if val is not None:
                try:
                    return int(val)
                except ValueError:
                    return val.decode("utf-8")
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any):
        if self.client is None:
            await self.connect()

        if not self._is_redis:
            self.client[key] = value
            return

        try:
            await self.client.set(key, value)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
