import logging
import json
from typing import Optional, Any
import redis.asyncio as redis
import os

logger = logging.getLogger("raphael.memory.working_memory")


class WorkingMemory:
    """
    High-speed, ephemeral storage layer backed by Redis.
    Used for active task contexts, agent scratchpads, and short-term data.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
    ):
        self.redis_url = os.getenv("REDIS_URL", f"redis://{host}:{port}/{db}")
        if password:
            self.redis_url = f"redis://:{password}@{host}:{port}/{db}"
        self.client: Optional[redis.Redis] = None

    async def start(self):
        """Initialize Redis connection."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            logger.info(f"WorkingMemory connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def stop(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("WorkingMemory disconnected.")

    async def put(self, key: str, value: Any, ttl: int = 3600):
        """
        Store a value with an expiration time (TTL) in seconds.
        Submits basic types directly, dumps complex types to JSON.
        """
        if not self.client:
            logger.warning("WorkingMemory not connected. Dropping put.")
            return

        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            await self.client.set(key, value, ex=ttl)
            logger.debug(f"Stored key: {key} (TTL={ttl})")
        except Exception as e:
            logger.error(f"Failed to put key {key}: {e}")

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key. Auto-decodes JSON if detected."""
        if not self.client:
            return None

        try:
            value = await self.client.get(key)
            if value is None:
                return None

            # fast/naive check for JSON
            if isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return value
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None

    async def delete(self, key: str):
        """Delete a key."""
        if not self.client:
            return

        try:
            await self.client.delete(key)
            logger.debug(f"Deleted key: {key}")
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")


# Singleton
# Using default env vars or localhost
working_memory = WorkingMemory()
