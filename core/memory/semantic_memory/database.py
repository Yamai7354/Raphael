import logging
import asyncio
from typing import Optional, Any, Dict, List
import asyncpg
import os

logger = logging.getLogger("raphael.memory.database")


class PostgresManager:
    """Async PostgreSQL Manager for TimescaleDB-compatible storage."""

    def __init__(self):
        self.dsn = os.getenv(
            "POSTGRES_URI", "postgresql://postgres:postgres@localhost:5432/raphael_memory"
        )
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Establish connection pool to the PostgreSQL database."""
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=10)
                logger.info(f"Connected to PostgreSQL database at {self.dsn}")
                await self._migrate()
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed PostgreSQL database connection pool")

    async def _migrate(self):
        """Create necessary tables and TimescaleDB hypertables if they don't exist."""
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            # Tasks Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id UUID PRIMARY KEY,
                    intent TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    priority INTEGER DEFAULT 5,
                    created_at TIMESTAMPTZ NOT NULL,
                    payload JSONB NOT NULL
                )
            """)

            # Events Table (Time-Series)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id UUID NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    payload JSONB NOT NULL,
                    source_module VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    correlation_id UUID,
                    PRIMARY KEY (id, timestamp)
                )
            """)

            # Convert events to hypertable if TimescaleDB extension exists
            # (Silently fails if extension isn't installed, standard PG fallback)
            try:
                await conn.execute("""
                    SELECT create_hypertable('events', 'timestamp', if_not_exists => TRUE);
                """)
            except asyncpg.exceptions.UndefinedFunctionError:
                logger.debug(
                    "TimescaleDB extension not found; falling back to standard PostgreSQL table for 'events'."
                )

            logger.info("Database schemas verified/migrated.")

    async def execute_query(self, query: str, *parameters) -> None:
        """Execute a query (INSERT, UPDATE, DELETE) asynchronously."""
        if not self.pool:
            raise ConnectionError("Database not connected")

        async with self.pool.acquire() as conn:
            await conn.execute(query, *parameters)

    async def fetch_one(self, query: str, *parameters) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        if not self.pool:
            raise ConnectionError("Database not connected")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *parameters)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *parameters) -> List[Dict[str, Any]]:
        """Fetch multiple rows."""
        if not self.pool:
            raise ConnectionError("Database not connected")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *parameters)
            return [dict(row) for row in rows]


# Singleton
db_manager = PostgresManager()
