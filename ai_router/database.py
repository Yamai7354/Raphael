import sqlite3
import logging
import asyncio
from typing import Optional, Any, Dict, List

logger = logging.getLogger("ai_router.database")

import os

# Persistent DB path relative to the project root
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, "raphael.db")


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    async def connect(self):
        """Establish connection to the SQLite database."""
        if not self._connection:
            # We use check_same_thread=False because we will run queries in executor
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite database at {self.db_path}")
            await self._migrate()

    async def close(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Closed SQLite database connection")

    async def _migrate(self):
        """Create necessary tables if they don't exist."""
        if not self._connection:
            return

        def _run_migration():
            cursor = self._connection.cursor()
            # Tasks Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    status TEXT,
                    priority TEXT,
                    created_at TIMESTAMP,
                    context TEXT,
                    result TEXT
                )
            """)

            # Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    topic TEXT,
                    payload TEXT,
                    source TEXT,
                    timestamp TIMESTAMP,
                    correlation_id TEXT
                )
            """)

            # Knowledge Graph (Triples) Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS triples (
                    subject TEXT,
                    predicate TEXT,
                    object TEXT,
                    confidence REAL DEFAULT 1.0,
                    source TEXT,
                    timestamp TIMESTAMP,
                    PRIMARY KEY (subject, predicate, object)
                )
            """)

            # Experiments Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    status TEXT, -- active, completed, draft
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    variants TEXT -- JSON list of variant configs
                )
            """)

            # Experiment Assignments Table (Trials)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiment_assignments (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT,
                    variant_id TEXT,
                    task_id TEXT,
                    timestamp TIMESTAMP,
                    metrics TEXT, -- JSON snapshot of performance if needed
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            self._connection.commit()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_migration)
        logger.info("Database schemas verified/migrated.")

    async def execute_query(self, query: str, parameters: tuple = ()) -> None:
        """Execute a query (INSERT, UPDATE, DELETE) and commit."""
        if not self._connection:
            raise ConnectionError("Database not connected")

        def _run_execute():
            cursor = self._connection.cursor()
            cursor.execute(query, parameters)
            self._connection.commit()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_execute)

    async def fetch_one(
        self, query: str, parameters: tuple = ()
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        if not self._connection:
            raise ConnectionError("Database not connected")

        def _run_fetch():
            cursor = self._connection.cursor()
            cursor.execute(query, parameters)
            row = cursor.fetchone()
            return dict(row) if row else None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run_fetch)

    async def fetch_all(
        self, query: str, parameters: tuple = ()
    ) -> List[Dict[str, Any]]:
        """Fetch multiple rows."""
        if not self._connection:
            raise ConnectionError("Database not connected")

        def _run_fetch_all():
            cursor = self._connection.cursor()
            cursor.execute(query, parameters)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run_fetch_all)


# Singleton
db_manager = DatabaseManager()
