"""
SWARM-106 — Task Market / Bidding System.

Allows agents to compete for tasks based on skill, reputation, and task priority.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from .reputation import ReputationTracker

logger = logging.getLogger("swarm.evolution.task_market")


class TaskStatus(str, Enum):
    OPEN = "open"
    BIDDING = "bidding"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskListing:
    """A task posted to the market."""

    task_id: str
    title: str
    description: str
    priority: float = 5.0  # 1-10, higher = more important
    required_skills: list[str] = field(default_factory=list)
    domain: str = "general"
    status: TaskStatus = TaskStatus.OPEN
    assigned_to: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "priority": self.priority,
            "required_skills": self.required_skills,
            "domain": self.domain,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
        }


@dataclass
class TaskBid:
    """An agent's bid for a task."""

    agent_id: str
    task_id: str
    confidence: float = 0.5  # Agent's self-assessed confidence (0-1)
    matching_skills: list[str] = field(default_factory=list)
    reputation_score: float = 0.0
    bid_time: float = field(default_factory=time.time)

    @property
    def effective_score(self) -> float:
        """Weighted bid score: confidence * skill match * reputation bonus."""
        skill_bonus = len(self.matching_skills) * 0.1
        rep_bonus = self.reputation_score / 100.0
        return self.confidence * (1.0 + skill_bonus) * (1.0 + rep_bonus)


class TaskMarket:
    """
    Central task marketplace where agents bid for work.
    System auto-assigns based on bid scores.
    """

    def __init__(self, reputation: ReputationTracker | None = None):
        self.reputation = reputation or ReputationTracker()
        self._tasks: dict[str, TaskListing] = {}
        self._bids: dict[str, list[TaskBid]] = {}  # task_id -> bids

    def post_task(
        self,
        title: str,
        description: str = "",
        priority: float = 5.0,
        required_skills: list[str] | None = None,
        domain: str = "general",
    ) -> TaskListing:
        """Post a new task to the market."""
        task = TaskListing(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            priority=priority,
            required_skills=required_skills or [],
            domain=domain,
        )
        self._tasks[task.task_id] = task
        self._bids[task.task_id] = []
        logger.info("task_posted id=%s title=%s priority=%.1f", task.task_id, title, priority)
        return task

    def submit_bid(
        self,
        agent_id: str,
        task_id: str,
        confidence: float = 0.5,
        agent_skills: list[str] | None = None,
    ) -> TaskBid | None:
        """Agent submits a bid for a task."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.OPEN:
            return None

        agent_skills = agent_skills or []
        matching = [s for s in agent_skills if s in task.required_skills]
        rep = self.reputation.get_or_create(agent_id)

        bid = TaskBid(
            agent_id=agent_id,
            task_id=task_id,
            confidence=confidence,
            matching_skills=matching,
            reputation_score=rep.score,
        )
        self._bids[task_id].append(bid)
        task.status = TaskStatus.BIDDING
        logger.info(
            "bid_submitted agent=%s task=%s score=%.3f",
            agent_id,
            task_id,
            bid.effective_score,
        )
        return bid

    def assign_task(self, task_id: str) -> str | None:
        """
        Auto-assign a task to the highest-scoring bidder.
        Returns the winning agent_id or None.
        """
        task = self._tasks.get(task_id)
        bids = self._bids.get(task_id, [])
        if not task or not bids:
            return None

        # Sort by effective score, highest first
        bids.sort(key=lambda b: b.effective_score, reverse=True)
        winner = bids[0]

        task.assigned_to = winner.agent_id
        task.status = TaskStatus.ASSIGNED
        logger.info(
            "task_assigned task=%s agent=%s score=%.3f",
            task_id,
            winner.agent_id,
            winner.effective_score,
        )
        return winner.agent_id

    def complete_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED

    def fail_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED

    def get_open_tasks(self) -> list[dict]:
        return [
            t.to_dict()
            for t in self._tasks.values()
            if t.status in (TaskStatus.OPEN, TaskStatus.BIDDING)
        ]

    def get_all_tasks(self) -> list[dict]:
        return [t.to_dict() for t in self._tasks.values()]
