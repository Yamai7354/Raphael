"""
Advanced Scheduler for AI Router.

Priority, load, and dependency-aware scheduling.
Supports parallel execution and failure containment.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

logger = logging.getLogger("ai_router.scheduler")


# =============================================================================
# TASK PRIORITY
# =============================================================================


class Priority(int, Enum):
    """Task priority levels."""

    LOW = 0
    NORMAL = 50
    HIGH = 75
    CRITICAL = 100


# =============================================================================
# ORCHESTRATION POLICIES
# =============================================================================


@dataclass
class OrchestrationPolicy:
    """Global orchestration policies."""

    # Concurrency limits
    max_concurrent_tasks: int = 10
    max_concurrent_per_role: Dict[str, int] = field(default_factory=dict)
    default_concurrent_per_role: int = 3

    # Priority
    enable_preemption: bool = False
    preemption_threshold: Priority = Priority.CRITICAL

    # Fairness
    fairness_window_sec: float = 60.0
    max_tasks_per_role_in_window: int = 50

    # Timeouts
    default_subtask_timeout_sec: float = 120.0
    max_queue_wait_sec: float = 300.0

    def get_role_limit(self, role: str) -> int:
        """Get concurrency limit for a role."""
        return self.max_concurrent_per_role.get(role, self.default_concurrent_per_role)

    def to_dict(self) -> Dict:
        return {
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_concurrent_per_role": self.max_concurrent_per_role,
            "default_concurrent_per_role": self.default_concurrent_per_role,
            "enable_preemption": self.enable_preemption,
            "preemption_threshold": self.preemption_threshold.name,
            "default_subtask_timeout_sec": self.default_subtask_timeout_sec,
        }


# =============================================================================
# SCHEDULED ITEM
# =============================================================================


@dataclass
class ScheduledItem:
    """An item in the scheduling queue."""

    task_id: str
    subtask_id: str
    role: str
    priority: Priority = Priority.NORMAL
    queued_at: datetime = field(default_factory=datetime.now)

    # Execution state
    can_run_parallel: bool = False
    depends_on: List[str] = field(default_factory=list)
    assigned_node: Optional[str] = None

    # Status
    started_at: Optional[datetime] = None
    is_running: bool = False
    is_paused: bool = False
    pause_reason: Optional[str] = None

    def wait_time_sec(self) -> float:
        """Get time spent waiting."""
        return (datetime.now() - self.queued_at).total_seconds()

    def priority_score(self) -> float:
        """Calculate priority score (higher = more urgent)."""
        base = float(self.priority)
        wait_bonus = min(self.wait_time_sec() / 60.0, 20.0)  # Cap at 20 points
        return base + wait_bonus

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "subtask_id": self.subtask_id,
            "role": self.role,
            "priority": self.priority.name,
            "can_run_parallel": self.can_run_parallel,
            "depends_on": self.depends_on,
            "assigned_node": self.assigned_node,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "wait_time_sec": round(self.wait_time_sec(), 2),
            "priority_score": round(self.priority_score(), 2),
        }


# =============================================================================
# ADVANCED SCHEDULER
# =============================================================================


class AdvancedScheduler:
    """
    Priority, load, and dependency-aware scheduler.
    """

    def __init__(self, policy: Optional[OrchestrationPolicy] = None):
        self.policy = policy or OrchestrationPolicy()

        # Queues
        self._pending: Dict[str, ScheduledItem] = {}  # subtask_id -> item
        self._running: Dict[str, ScheduledItem] = {}
        self._paused: Dict[str, ScheduledItem] = {}

        # Tracking
        self._completed: Set[str] = set()
        self._failed: Set[str] = set()
        self._current_per_role: Dict[str, int] = {}

        self._lock = asyncio.Lock()

    async def schedule(
        self,
        task_id: str,
        subtask_id: str,
        role: str,
        priority: Priority = Priority.NORMAL,
        can_run_parallel: bool = False,
        depends_on: Optional[List[str]] = None,
    ) -> ScheduledItem:
        """Add item to scheduling queue."""
        async with self._lock:
            item = ScheduledItem(
                task_id=task_id,
                subtask_id=subtask_id,
                role=role,
                priority=priority,
                can_run_parallel=can_run_parallel,
                depends_on=depends_on or [],
            )

            self._pending[subtask_id] = item

            logger.info(
                "item_scheduled task=%s subtask=%s role=%s priority=%s",
                task_id,
                subtask_id,
                role,
                priority.name,
            )

            return item

    async def get_next_runnable(
        self,
        available_nodes: List[str],
    ) -> Optional[ScheduledItem]:
        """
        Get next item that can run.
        Considers dependencies, priority, and limits.
        """
        async with self._lock:
            # Check global limit
            if len(self._running) >= self.policy.max_concurrent_tasks:
                return None

            # Find candidates
            candidates = []
            for item in self._pending.values():
                # Check dependencies
                if not self._dependencies_satisfied(item):
                    continue

                # Check role limit
                current = self._current_per_role.get(item.role, 0)
                if current >= self.policy.get_role_limit(item.role):
                    continue

                # Check parallelism
                if not item.can_run_parallel:
                    # Check if any same-task items running
                    same_task_running = any(
                        r.task_id == item.task_id for r in self._running.values()
                    )
                    if same_task_running:
                        continue

                candidates.append(item)

            if not candidates:
                return None

            # Sort by priority score (highest first)
            candidates.sort(key=lambda x: x.priority_score(), reverse=True)

            # Return highest priority
            selected = candidates[0]
            return selected

    def select_best_node(
        self,
        item: ScheduledItem,
        candidates: List[str],
    ) -> str:
        """
        Select best node for an item from candidates.
        Uses adaptive scoring if available (Ticket 3).
        """
        from .adaptive_learning import adaptive_learning
        import random

        # Get scores for all candidates
        scores = []
        for node_id in candidates:
            score_obj = adaptive_learning.get_score(node_id, item.role)
            # Default score 0.5 if no history
            score_val = score_obj.score if score_obj else 0.5
            scores.append((node_id, score_val))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        # Weighted selection logic (simple epsilon-greedy for exploration)
        # 80% chance to pick top scorer, 20% random for exploration
        # Only if we have enough candidates
        if len(candidates) > 1 and random.random() < 0.2:
            return random.choice(candidates)

        return scores[0][0]

    async def start_item(
        self,
        subtask_id: str,
        node_id: str,
    ) -> bool:
        """Mark item as started on a node."""
        async with self._lock:
            item = self._pending.pop(subtask_id, None)
            if not item:
                return False

            item.is_running = True
            item.started_at = datetime.now()
            item.assigned_node = node_id

            self._running[subtask_id] = item
            self._current_per_role[item.role] = (
                self._current_per_role.get(item.role, 0) + 1
            )

            logger.info(
                "item_started subtask=%s node=%s role=%s",
                subtask_id,
                node_id,
                item.role,
            )

            return True

    async def complete_item(
        self,
        subtask_id: str,
        success: bool = True,
    ) -> Optional[ScheduledItem]:
        """Mark item as completed."""
        async with self._lock:
            item = self._running.pop(subtask_id, None)
            if not item:
                return None

            item.is_running = False

            self._current_per_role[item.role] = max(
                0, self._current_per_role.get(item.role, 1) - 1
            )

            if success:
                self._completed.add(subtask_id)
            else:
                self._failed.add(subtask_id)

            logger.info("item_completed subtask=%s success=%s", subtask_id, success)

            # TRIGGER PREFETCH (Ticket 9.2)
            # We fire this asynchronously so it doesn't block completion
            if success:
                from .prefetch_manager import prefetch_manager

                asyncio.create_task(
                    prefetch_manager.process_task_completion(
                        task_id=item.task_id, subtask_id=item.subtask_id, role=item.role
                    )
                )

            return item

    async def pause_item(
        self,
        subtask_id: str,
        reason: str,
    ) -> bool:
        """Pause a running or pending item."""
        async with self._lock:
            # Check running
            item = self._running.pop(subtask_id, None)
            if item:
                self._current_per_role[item.role] = max(
                    0, self._current_per_role.get(item.role, 1) - 1
                )
            else:
                item = self._pending.pop(subtask_id, None)

            if not item:
                return False

            item.is_running = False
            item.is_paused = True
            item.pause_reason = reason

            self._paused[subtask_id] = item

            logger.info("item_paused subtask=%s reason=%s", subtask_id, reason)

            return True

    async def resume_item(self, subtask_id: str) -> bool:
        """Resume a paused item."""
        async with self._lock:
            item = self._paused.pop(subtask_id, None)
            if not item:
                return False

            item.is_paused = False
            item.pause_reason = None

            self._pending[subtask_id] = item

            logger.info("item_resumed subtask=%s", subtask_id)
            return True

    async def pause_dependents(self, failed_subtask_id: str) -> List[str]:
        """Pause all items that depend on a failed subtask."""
        paused = []
        async with self._lock:
            for subtask_id, item in list(self._pending.items()):
                if failed_subtask_id in item.depends_on:
                    item.is_paused = True
                    item.pause_reason = f"dependency_failed:{failed_subtask_id}"
                    self._paused[subtask_id] = self._pending.pop(subtask_id)
                    paused.append(subtask_id)

        if paused:
            logger.info(
                "dependents_paused failed=%s paused=%d", failed_subtask_id, len(paused)
            )

        return paused

    def _dependencies_satisfied(self, item: ScheduledItem) -> bool:
        """Check if all dependencies are completed."""
        for dep in item.depends_on:
            if dep not in self._completed:
                return False
        return True

    def get_queue_stats(self) -> Dict:
        """Get scheduler statistics."""
        return {
            "pending": len(self._pending),
            "running": len(self._running),
            "paused": len(self._paused),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "per_role": dict(self._current_per_role),
        }

    def get_running_items(self) -> List[Dict]:
        """Get currently running items."""
        return [item.to_dict() for item in self._running.values()]

    def get_pending_items(self) -> List[Dict]:
        """Get pending items sorted by priority."""
        items = sorted(
            self._pending.values(), key=lambda x: x.priority_score(), reverse=True
        )
        return [item.to_dict() for item in items]


# Global singleton
advanced_scheduler = AdvancedScheduler()
