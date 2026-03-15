"""
TaskManager — Manages the lifecycle of tasks entering the swarm.

Responsibilities:
  - Accept new tasks (from queue, API, or direct call)
  - Track task state transitions: pending → running → completed/failed
  - Emit events for the Director loop to observe
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger("director.task_manager")


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SwarmTask:
    """A unit of work entering the swarm."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    priority: int = 5  # 1 = highest, 10 = lowest
    state: TaskState = TaskState.PENDING
    habitat_release: str | None = None  # Helm release name once deployed
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class TaskManager:
    """Manages task lifecycle and provides an async task queue."""

    def __init__(self):
        self._tasks: dict[str, SwarmTask] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._listeners: list[Callable] = []

    async def submit(self, task: SwarmTask) -> SwarmTask:
        """Submit a new task to the swarm."""
        self._tasks[task.id] = task
        # Priority queue: lower number = higher priority
        await self._queue.put((task.priority, task.created_at, task.id))
        logger.info(f"Task submitted: {task.id} (priority={task.priority})")
        await self._notify("task_submitted", task)
        return task

    async def next_task(self) -> SwarmTask | None:
        """Get the next highest-priority pending task."""
        try:
            _, _, task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            task = self._tasks.get(task_id)
            if task and task.state == TaskState.PENDING:
                return task
            return None
        except TimeoutError:
            return None

    def transition(self, task_id: str, new_state: TaskState, **kwargs):
        """Transition a task to a new state."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        old_state = task.state
        task.state = new_state

        if new_state == TaskState.RUNNING:
            task.habitat_release = kwargs.get("habitat_release")
        elif new_state == TaskState.COMPLETED:
            task.completed_at = datetime.now(timezone.utc).isoformat()
        elif new_state == TaskState.FAILED:
            task.error = kwargs.get("error", "Unknown error")
            task.completed_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"Task {task_id}: {old_state.value} → {new_state.value}")

    def get_task(self, task_id: str) -> SwarmTask | None:
        return self._tasks.get(task_id)

    def get_pending_tasks(self) -> list[SwarmTask]:
        return [t for t in self._tasks.values() if t.state == TaskState.PENDING]

    def get_running_tasks(self) -> list[SwarmTask]:
        return [t for t in self._tasks.values() if t.state == TaskState.RUNNING]

    def on_event(self, callback: Callable):
        """Register a listener for task events."""
        self._listeners.append(callback)

    async def _notify(self, event: str, task: SwarmTask):
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, task)
                else:
                    listener(event, task)
            except Exception as e:
                logger.warning(f"Listener error: {e}")
