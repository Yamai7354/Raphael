import logging
import json
from typing import Optional, Dict, Any

from src.raphael.understanding.schemas import Task
from src.raphael.core.schemas import SystemEvent
from .database import db_manager

logger = logging.getLogger("raphael.memory.episodic_memory")


class EpisodicMemory:
    """
    Service for persisting tasks and events to long-term storage (SQLite).
    Allows retrieval of past tasks and events for context.
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
                INSERT INTO tasks (id, intent, status, priority, created_at, payload)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    intent = EXCLUDED.intent,
                    status = EXCLUDED.status,
                    priority = EXCLUDED.priority,
                    payload = EXCLUDED.payload
            """
            payload_json = task.model_dump_json()

            await db_manager.execute_query(
                query,
                task.task_id,
                task.original_intent,
                task.status.value,
                task.priority,
                task.created_at,
                payload_json,
            )
            logger.debug(f"Stored task {task.task_id} in memory.")
        except Exception as e:
            logger.error(f"Failed to store task {task.task_id}: {e}")

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a task by ID as a dictionary payload."""
        try:
            row = await db_manager.fetch_one("SELECT payload FROM tasks WHERE id = $1", task_id)
            if row and row["payload"]:
                return json.loads(row["payload"])
        except Exception as e:
            logger.error(f"Failed to retrieve task {task_id}: {e}")
        return None

    async def log_event(self, event: SystemEvent):
        """Log a system event."""
        try:
            query = """
                INSERT INTO events (id, event_type, payload, source_module, timestamp, correlation_id)
                VALUES ($1, $2, $3, $4, $5, $6)
            """
            payload_json = json.dumps(event.payload)

            await db_manager.execute_query(
                query,
                event.event_id,
                event.event_type.value,
                payload_json,
                event.source_layer.module_name,
                event.timestamp,
                event.correlation_id,
            )
            logger.debug(f"Logged event {event.event_id} in memory.")
        except Exception as e:
            logger.error(f"Failed to log event {event.event_id}: {e}")


# Singleton
episodic_memory = EpisodicMemory()
