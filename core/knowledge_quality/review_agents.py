"""
KQ-610 — Knowledge Review Agents.

Agents responsible for auditing knowledge quality:
validate research, resolve contradictions, recommend merges,
identify outdated information.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.knowledge_quality.review_agents")


class ReviewType(str, Enum):
    VALIDATE = "validate"
    RESOLVE_CONTRADICTION = "resolve_contradiction"
    RECOMMEND_MERGE = "recommend_merge"
    CHECK_OUTDATED = "check_outdated"


@dataclass
class ReviewTask:
    task_id: str = field(default_factory=lambda: f"rv_{uuid.uuid4().hex[:8]}")
    review_type: ReviewType = ReviewType.VALIDATE
    node_ids: list[str] = field(default_factory=list)
    assigned_to: str = ""
    status: str = "pending"  # pending, assigned, completed
    result: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "type": self.review_type.value,
            "nodes": self.node_ids,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "result": self.result,
        }


class ReviewAgentManager:
    """Manages knowledge review tasks and assignments."""

    def __init__(self):
        self._tasks: dict[str, ReviewTask] = {}
        self._reviewers: list[str] = []
        self._round_robin: int = 0

    def register_reviewer(self, agent_name: str) -> None:
        if agent_name not in self._reviewers:
            self._reviewers.append(agent_name)

    def create_review(self, review_type: ReviewType, node_ids: list[str]) -> ReviewTask:
        task = ReviewTask(review_type=review_type, node_ids=node_ids)

        # Auto-assign using round-robin
        if self._reviewers:
            task.assigned_to = self._reviewers[self._round_robin % len(self._reviewers)]
            task.status = "assigned"
            self._round_robin += 1

        self._tasks[task.task_id] = task
        logger.info(
            "review_created type=%s nodes=%s assigned=%s",
            review_type.value,
            node_ids,
            task.assigned_to,
        )
        return task

    def complete_review(self, task_id: str, result: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = "completed"
            task.result = result
            task.completed_at = time.time()

    def get_pending(self, agent_name: str = "") -> list[ReviewTask]:
        tasks = [t for t in self._tasks.values() if t.status in ("pending", "assigned")]
        if agent_name:
            tasks = [t for t in tasks if t.assigned_to == agent_name]
        return tasks

    def get_all(self, limit: int = 30) -> list[dict]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def get_stats(self) -> dict:
        by_status: dict[str, int] = {}
        for t in self._tasks.values():
            by_status[t.status] = by_status.get(t.status, 0) + 1
        return {
            "total_tasks": len(self._tasks),
            "reviewers": len(self._reviewers),
            "by_status": by_status,
        }
