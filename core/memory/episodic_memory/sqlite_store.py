import sqlite3
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from .base import EpisodicMemory
from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)
from core.understanding.schemas import Task, TaskStatus
from core.swarm_os.task_manager import TaskPriority

logger = logging.getLogger("sqlite_episodic")


class SQLiteEpisodicStore(MemoryContract, EpisodicMemory):
    """SQLite implementation of Episodic Memory (MEM-3)."""

    def __init__(self, db_path: str = "data/episodic.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT,
                    priority TEXT,
                    assigned_to TEXT,
                    input_data TEXT,
                    output_data TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    timestamp TIMESTAMP,
                    message TEXT,
                    metadata TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                )
            """)
            conn.commit()
        logger.info(f"Initialized SQLite episodic store at {self.db_path}")

    async def store_task(self, task: Task):
        with sqlite3.connect(self.db_path) as conn:
            task_dict = task.model_dump()
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, title, description, status, priority, assigned_to,
                    input_data, output_data, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(task.id),
                    task.title,
                    task.description,
                    task_dict.get("status"),
                    task_dict.get("priority"),
                    task.assigned_to,
                    json.dumps(task_dict.get("input_data", {})),
                    json.dumps(task_dict.get("output_data", {})),
                    json.dumps(task_dict.get("metadata", {})),
                    task_dict.get("created_at"),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (str(task_id),))
            row = cursor.fetchone()
            if not row:
                return None

            return Task(
                id=UUID(row["id"]),
                title=row["title"],
                description=row["description"],
                status=TaskStatus(row["status"]),
                priority=TaskPriority(row["priority"]),
                assigned_to=row["assigned_to"],
                input_data=json.loads(row["input_data"]),
                output_data=json.loads(row["output_data"]),
                metadata=json.loads(row["metadata"]),
            )

    async def query_tasks(self, filters: Dict[str, Any]) -> List[Task]:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        for k, v in filters.items():
            query += f" AND {k} = ?"
            params.append(str(v))

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [
                Task(
                    id=UUID(row["id"]),
                    title=row["title"],
                    description=row["description"],
                    status=TaskStatus(row["status"]),
                    priority=TaskPriority(row["priority"]),
                    assigned_to=row["assigned_to"],
                    input_data=json.loads(row["input_data"]),
                    output_data=json.loads(row["output_data"]),
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]

    async def add_log(self, task_id: UUID, message: str, metadata: Optional[Dict[str, Any]] = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO task_logs (task_id, timestamp, message, metadata)
                VALUES (?, ?, ?, ?)
            """,
                (
                    str(task_id),
                    datetime.utcnow().isoformat(),
                    message,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

    async def get_logs(self, task_id: UUID) -> List[Dict[str, Any]]:
        """Retrieve logs for a specific task."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM task_logs WHERE task_id = ? ORDER BY timestamp ASC",
                (str(task_id),),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    async def store(self, payload: MemoryPayload):
        """Cross-project storage contract (MEM-1)."""
        # For episodic store, we might treat generic content as a log if it's not a Task
        if isinstance(payload.content, Task):
            await self.store_task(payload.content)
        else:
            # Fallback: store as log or metadata?
            # For now, let's assume content can be dict etc.
            task_id = payload.metadata.correlation_id or str(payload.id)
            await self.add_log(
                UUID(task_id) if isinstance(task_id, str) and "-" in task_id else payload.id,
                str(payload.content),
                payload.metadata.model_dump(),
            )

    async def retrieve(self, query: str, filters: Dict[str, Any]) -> List[MemoryPayload]:
        """Cross-project retrieval contract (MEM-1)."""
        tasks = await self.query_tasks(filters)
        results = []
        for task in tasks:
            results.append(
                MemoryPayload(
                    memory_type=MemoryType.EPISODIC,
                    content=task,
                    metadata=MemoryMetadata(
                        source_agent="sqlite_store",
                        correlation_id=str(task.id),
                        tags=task.metadata.get("tags", []) if task.metadata else [],
                    ),
                )
            )
        return results

    async def forget(self, policy: Dict[str, Any]):
        """Sanitization and pruning contract (MEM-1)."""
        # Simple implementation: delete by task_id if provided
        if "task_id" in policy:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM task_logs WHERE task_id = ?", (str(policy["task_id"]),))
                conn.execute("DELETE FROM tasks WHERE id = ?", (str(policy["task_id"]),))
                conn.commit()
