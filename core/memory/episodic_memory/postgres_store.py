import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID

import asyncpg
from pgvector.asyncpg import register_vector

from .base import EpisodicMemory
from ...understanding.schemas import Task
from core.understanding.schemas import Task as ModelTask
from data.schemas import SystemEvent
from ..contracts.memory_contract import MemoryContract, MemoryPayload, MemoryType, MemoryMetadata

logger = logging.getLogger("raphael.memory.postgres_store")


class PostgresEpisodicStore(EpisodicMemory, MemoryContract):
    """
    PostgreSQL-backed episodic memory with pgvector for semantic search.
    Implements both the EpisodicMemory ABC and MemoryContract.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Establish connection pool and ensure schema/extensions exist."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.db_url)
            logger.info("Connected to PostgreSQL Episodic Store.")
            await self._ensure_schema()

    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed PostgreSQL Episodic Store connection.")

    async def _ensure_schema(self):
        """Create the vector extension and required tables if they don't exist."""
        async with self.pool.acquire() as conn:
            # Install pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Register pgvector types with asyncpg
            await register_vector(conn)

            # Create tasks table (EpisodicMemory contract)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_tasks (
                    id UUID PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    agent_id TEXT,
                    task_type TEXT,
                    success_score REAL,
                    raw_data_ref JSONB,
                    embedding vector(1024)
                )
            """)

            # Create events table (EpisodicMemory contract)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_events (
                    id UUID PRIMARY KEY,
                    event_type TEXT,
                    payload JSONB,
                    source_module TEXT,
                    timestamp TIMESTAMP WITH TIME ZONE,
                    correlation_id UUID,
                    embedding vector(1024)
                )
            """)

            # Create generic memory payloads table (MemoryContract)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_payloads (
                    id UUID PRIMARY KEY,
                    content JSONB,
                    source_agent TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    importance REAL DEFAULT 0.0,
                    embedding vector(1024)
                )
            """)

    # -------------------------------------------------------------------------
    # EpisodicMemory ABC Implementation
    # -------------------------------------------------------------------------

    async def store_task(self, task: Task | ModelTask):
        """Persist a task to episodic memory."""
        if not self.pool:
            await self.connect()

        try:
            query = """
                INSERT INTO episodic_tasks (id, timestamp, agent_id, task_type, success_score, raw_data_ref)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    agent_id = EXCLUDED.agent_id,
                    task_type = EXCLUDED.task_type,
                    success_score = EXCLUDED.success_score,
                    raw_data_ref = EXCLUDED.raw_data_ref
            """

            # Handle different task model versions
            task_id = getattr(task, "task_id", getattr(task, "id", None))
            intent = getattr(task, "original_intent", getattr(task, "title", "unknown"))
            status = getattr(task, "status", "unknown")
            if hasattr(status, "value"):
                status = status.value
            created_at = getattr(task, "created_at", datetime.utcnow())
            agent_id = getattr(task, "assigned_to", "unknown_agent")

            success_score = 0.0
            if status == "completed":
                success_score = 1.0
            elif status == "failed":
                success_score = -1.0

            payload_json = json.dumps(getattr(task, "model_dump", lambda: task.__dict__)())

            async with self.pool.acquire() as conn:
                await conn.execute(
                    query, task_id, created_at, agent_id, intent, success_score, payload_json
                )
                logger.debug(f"Stored task {task_id} in postgres.")
        except Exception as e:
            logger.error(f"Failed to store task: {e}")

    async def get_task(self, task_id: UUID | str) -> Optional[Dict[str, Any]]:
        """Retrieve a task by ID as a dictionary payload."""
        if not self.pool:
            await self.connect()

        try:
            if isinstance(task_id, str):
                task_id = UUID(task_id)

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT raw_data_ref FROM episodic_tasks WHERE id = $1", task_id
                )
                if row and row["raw_data_ref"]:
                    return json.loads(row["raw_data_ref"])
        except Exception as e:
            logger.error(f"Failed to retrieve task {task_id}: {e}")
        return None

    async def query_tasks(self, filters: Dict[str, Any]) -> List[Any]:
        # Simple implementation for ABC compliance
        if not self.pool:
            await self.connect()
        # TODO: Implement complex filtering based on JSONB payload
        return []

    async def add_log(self, task_id: UUID, message: str, metadata: Optional[Dict[str, Any]] = None):
        if not self.pool:
            await self.connect()
        # Not strictly required for the router but honors the ABC
        pass

    async def log_event(self, event: SystemEvent):
        """Log a system event."""
        if not self.pool:
            await self.connect()

        try:
            query = """
                INSERT INTO episodic_events (id, event_type, payload, source_module, timestamp, correlation_id)
                VALUES ($1, $2, $3, $4, $5, $6)
            """
            payload_json = json.dumps(event.payload)

            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    event.event_id,
                    event.event_type.value,
                    payload_json,
                    event.source_layer.module_name,
                    event.timestamp,
                    event.correlation_id,
                )
                logger.debug(f"Logged event {event.event_id} in postgres.")
        except Exception as e:
            logger.error(f"Failed to log event {event.event_id}: {e}")

    # -------------------------------------------------------------------------
    # MemoryContract Implementation
    # -------------------------------------------------------------------------

    async def store(self, payload: MemoryPayload):
        """Cross-project storage contract (MEM-1)."""
        if not self.pool:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                content_json = (
                    json.dumps(payload.content)
                    if isinstance(payload.content, dict)
                    else json.dumps({"text": payload.content})
                )

                await conn.execute(
                    """
                    INSERT INTO episodic_payloads (id, content, source_agent, importance, expires_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    payload.id,
                    content_json,
                    payload.metadata.source_agent,
                    payload.metadata.importance,
                    payload.metadata.expires_at,
                )
        except Exception as e:
            logger.error(f"Postgres store failed: {e}")

    async def retrieve(self, query: str, filters: Dict[str, Any]) -> List[MemoryPayload]:
        """Cross-project retrieval contract (MEM-1)."""
        if not self.pool:
            await self.connect()

        # Basic text matching fallback if no vector
        results = []
        try:
            async with self.pool.acquire() as conn:
                # Naive text match on JSONB using wildcards
                search_term = f"%{query}%"
                rows = await conn.fetch(
                    "SELECT * FROM episodic_payloads WHERE content::text ILIKE $1 LIMIT $2",
                    search_term,
                    filters.get("limit", 10),
                )

                for row in rows:
                    content = json.loads(row["content"])
                    results.append(
                        MemoryPayload(
                            id=row["id"],
                            memory_type=MemoryType.EPISODIC,
                            content=content,
                            metadata=MemoryMetadata(
                                source_agent=row["source_agent"],
                                importance=row["importance"],
                                expires_at=row["expires_at"],
                            ),
                        )
                    )
        except Exception as e:
            logger.error(f"Postgres retrieve failed: {e}")

        return results

    async def forget(self, policy: Dict[str, Any]):
        """Sanitization and pruning contract (MEM-1)."""
        if not self.pool:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                if "older_than" in policy:
                    await conn.execute(
                        "DELETE FROM episodic_tasks WHERE timestamp < $1", policy["older_than"]
                    )
                    await conn.execute(
                        "DELETE FROM episodic_events WHERE timestamp < $1", policy["older_than"]
                    )
                    await conn.execute(
                        "DELETE FROM episodic_payloads WHERE created_at < $1", policy["older_than"]
                    )
        except Exception as e:
            logger.error(f"Postgres forget failed: {e}")
