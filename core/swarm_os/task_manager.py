"""
SOS-502 — Swarm Scheduler & Task Manager.

Centralized task allocation across agents based on roles,
reputation, availability, hardware capabilities, and load.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.swarm_os.task_manager")


class TaskPriority(int, Enum):
    CRITICAL = 1
    HIGH = 3
    MEDIUM = 5
    LOW = 7
    BACKGROUND = 9


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SwarmTask:
    """A task in the swarm task queue."""

    task_id: str = field(default_factory=lambda: f"st_{uuid.uuid4().hex[:8]}")
    title: str = ""
    task_type: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str = ""
    required_role: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    requires_gpu: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: float = 0
    completed_at: float = 0
    result: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "type": self.task_type,
            "priority": self.priority.value,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
        }


class SwarmTaskManager:
    """Centralized task scheduling and management."""

    def __init__(self):
        self._tasks: dict[str, SwarmTask] = {}
        self._queue: list[str] = []  # task_ids ordered by priority

    def submit(
        self,
        title: str,
        task_type: str = "general",
        priority: TaskPriority = TaskPriority.MEDIUM,
        required_role: str = "",
        requires_gpu: bool = False,
        required_capabilities: list[str] | None = None,
    ) -> SwarmTask:
        task = SwarmTask(
            title=title,
            task_type=task_type,
            priority=priority,
            required_role=required_role,
            requires_gpu=requires_gpu,
            required_capabilities=required_capabilities or [],
        )
        self._tasks[task.task_id] = task
        self._queue.append(task.task_id)
        self._sort_queue()
        logger.info(
            "task_submitted id=%s title=%s priority=%d", task.task_id, title, priority.value
        )
        return task

    def assign(self, task_id: str, agent_name: str) -> SwarmTask | None:
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.PENDING:
            return None
        task.status = TaskStatus.ASSIGNED
        task.assigned_to = agent_name
        if task_id in self._queue:
            self._queue.remove(task_id)
        return task

    def start(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.ASSIGNED:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()

    def complete(self, task_id: str, result: dict | None = None) -> None:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result or {}

    def fail(self, task_id: str, reason: str = "") -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            task.result = {"failure_reason": reason}

    def get_next(self, agent_role: str = "", has_gpu: bool = False) -> SwarmTask | None:
        """Get the highest priority pending task matching agent capabilities."""
        for tid in self._queue:
            task = self._tasks.get(tid)
            if not task or task.status != TaskStatus.PENDING:
                continue
            if task.required_role and agent_role and task.required_role != agent_role:
                continue
            if task.requires_gpu and not has_gpu:
                continue
            return task
        return None

    def get_pending(self) -> list[SwarmTask]:
        return [
            self._tasks[tid]
            for tid in self._queue
            if tid in self._tasks and self._tasks[tid].status == TaskStatus.PENDING
        ]

    def get_running(self) -> list[SwarmTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def _sort_queue(self) -> None:
        self._queue.sort(
            key=lambda tid: self._tasks[tid].priority.value if tid in self._tasks else 99
        )

    def get_all(self, limit: int = 50) -> list[dict]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def get_stats(self) -> dict:
        by_status: dict[str, int] = {}
        for t in self._tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        return {"total": len(self._tasks), "queued": len(self._queue), "by_status": by_status}
