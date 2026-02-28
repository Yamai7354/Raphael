import json
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime
from uuid import UUID, uuid4
import redis.asyncio as redis
from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)

logger = logging.getLogger("working_memory")


class RedisCache(MemoryContract):
    """Working Memory layer for transient cross-agent context stored in Redis (MEM-2)."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 1):
        self.host = host
        self.port = port
        self.db = db
        self._redis: Optional[redis.Redis] = None

    async def connect(self):
        if not self._redis:
            self._redis = redis.Redis(
                host=self.host, port=self.port, db=self.db, decode_responses=True
            )
            logger.info(f"Connected to Redis Working Memory at {self.host}:{self.port}")

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set a value in transient memory with a TTL (default 1 hour)."""
        if not self._redis:
            await self.connect()

        serialized = json.dumps(value)
        await self._redis.set(key, serialized, ex=ttl)

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from transient memory."""
        if not self._redis:
            await self.connect()

        data = await self._redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def store(self, payload: MemoryPayload):
        """Cross-project storage contract (MEM-1)."""
        ttl = (
            payload.metadata.expires_at.timestamp() - datetime.utcnow().timestamp()
            if payload.metadata.expires_at
            else 3600
        )
        await self.set(str(payload.id), payload.content, ttl=int(ttl))

    async def retrieve(
        self, query: str, filters: Dict[str, Any]
    ) -> List[MemoryPayload]:
        """Cross-project retrieval contract (MEM-1)."""
        # Simple key lookup for now
        key = filters.get("key") or query
        data = await self.get(key)
        if data:
            return [
                MemoryPayload(
                    id=uuid4() if "key" in filters else UUID(key),
                    memory_type=MemoryType.WORKING,
                    content=data,
                    metadata=MemoryMetadata(source_agent="redis_cache"),
                )
            ]
        return []

    async def forget(self, policy: Dict[str, Any]):
        """Sanitization and pruning contract (MEM-1)."""
        if "key" in policy:
            await self.delete(policy["key"])
