import logging
import json
from typing import Optional, Dict, Any

from raphael.core.models.task import Task
from raphael.core.bus.event_bus import Event
from .database import db_manager

logger = logging.getLogger("ai_router.memory")


class EpisodicMemory:
    """
    Service for persisting tasks and events to long-term storage (SQLite).
    Allows retrieval of past tasks for context.
    """

    async def start(self):
        await db_manager.connect()
        logger.info("EpisodicMemory started.")

    async def stop(self):
        await db_manager.close()
        logger.info("EpisodicMemory stopped.")

    async def store_task(self, task: Task):
        """Persist a task to storage."""
        try:
            query = """
                INSERT OR REPLACE INTO tasks (id, title, status, priority, created_at, context, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            context_json = json.dumps(task.context) if task.context else "{}"
            result_json = json.dumps(task.output) if task.output else "{}"

            await db_manager.execute_query(
                query,
                (
                    str(task.id),
                    task.title,
                    getattr(task.status, "value", task.status),
                    getattr(task.priority, "value", task.priority),
                    task.created_at.isoformat(),
                    context_json,
                    result_json,
                ),
            )
            logger.debug(f"Stored task {task.id} in memory.")
        except Exception as e:
            logger.error(f"Failed to store task {task.id}: {e}")

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a task by ID."""
        try:
            row = await db_manager.fetch_one(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            )
            if row:
                return {
                    "id": row["id"],
                    "title": row["title"],
                    "status": row["status"],
                    "priority": row["priority"],
                    "created_at": row["created_at"],
                    "context": json.loads(row["context"]),
                    "result": json.loads(row["result"]),
                }
        except Exception as e:
            logger.error(f"Failed to retrieve task {task_id}: {e}")
        return None

    async def log_event(self, event: Event):
        """Log a system event."""
        try:
            query = """
                INSERT INTO events (id, topic, payload, source, timestamp, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            payload_json = json.dumps(event.payload)

            await db_manager.execute_query(
                query,
                (
                    event.id,
                    event.topic,
                    payload_json,
                    event.source,
                    event.timestamp.isoformat(),
                    event.correlation_id,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to log event {event.id}: {e}")


# Singleton
episodic_memory = EpisodicMemory()
