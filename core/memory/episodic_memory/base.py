from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID
from core.understanding.schemas import Task


class EpisodicMemory(ABC):
    """Abstract interface for episodic memory (task history and logs)."""

    @abstractmethod
    async def store_task(self, task: Task):
        """Persist a task to episodic memory."""
        pass

    @abstractmethod
    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """Retrieve a specific task by ID."""
        pass

    @abstractmethod
    async def query_tasks(self, filters: Dict[str, Any]) -> List[Task]:
        """Query tasks by filters (status, tags, etc.)."""
        pass

    @abstractmethod
    async def add_log(self, task_id: UUID, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a log entry associated with a specific task."""
        pass
