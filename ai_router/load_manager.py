"""
Load Manager for AI Router.

Provides:
- Node capacity tracking (max concurrent steps)
- Per-role FIFO queues
- Load-aware scheduling
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque
from enum import Enum

logger = logging.getLogger("ai_router.load_manager")


# =============================================================================
# NODE LOAD STATE
# =============================================================================


@dataclass
class NodeLoad:
    """Tracks load state for a single node."""

    node_id: str
    max_concurrent: int = 2  # Default max concurrent steps
    current_load: int = 0
    queued_count: int = 0

    # Metrics
    total_completed: int = 0
    total_failed: int = 0
    avg_latency_ms: float = 0.0
    last_used: Optional[datetime] = None

    def can_accept(self) -> bool:
        """Check if node can accept another step."""
        return self.current_load < self.max_concurrent

    def available_slots(self) -> int:
        """Get number of available slots."""
        return max(0, self.max_concurrent - self.current_load)

    def acquire(self) -> bool:
        """Try to acquire a slot. Returns True if successful."""
        if self.can_accept():
            self.current_load += 1
            self.last_used = datetime.now()
            logger.info(
                "node_slot_acquired node=%s load=%d/%d",
                self.node_id,
                self.current_load,
                self.max_concurrent,
            )
            return True
        return False

    def release(self, success: bool = True, latency_ms: float = 0.0) -> None:
        """Release a slot after step completion."""
        self.current_load = max(0, self.current_load - 1)
        if success:
            self.total_completed += 1
        else:
            self.total_failed += 1

        # Update rolling average latency
        if latency_ms > 0:
            if self.avg_latency_ms == 0:
                self.avg_latency_ms = latency_ms
            else:
                # Exponential moving average
                self.avg_latency_ms = 0.8 * self.avg_latency_ms + 0.2 * latency_ms

        logger.info(
            "node_slot_released node=%s load=%d/%d success=%s",
            self.node_id,
            self.current_load,
            self.max_concurrent,
            success,
        )

        # Policy Metrics Hook (Phase 12)
        try:
            from .policy_manager import policy_manager

            # Simple simulation of aggregate metrics from this single event
            policy_manager.metrics.record_snapshot(
                {
                    "avg_latency_ms": latency_ms,
                    "success_rate": 1.0 if success else 0.0,
                    # In real app we'd get actual global queue depth here
                    "queue_depth": 0,
                    "utilization": self.current_load / max(1, self.max_concurrent),
                }
            )
        except ImportError:
            pass  # Avoid circular imports during startup/testing

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "max_concurrent": self.max_concurrent,
            "current_load": self.current_load,
            "available_slots": self.available_slots(),
            "queued_count": self.queued_count,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


# =============================================================================
# QUEUED STEP
# =============================================================================


@dataclass
class QueuedStep:
    """A step waiting in queue for execution."""

    task_id: str
    subtask_id: str
    role: str
    priority: int = 0  # Higher = more urgent
    queued_at: datetime = field(default_factory=datetime.now)
    preferred_node: Optional[str] = None

    def wait_time_sec(self) -> float:
        """Get time spent waiting in queue."""
        return (datetime.now() - self.queued_at).total_seconds()


# =============================================================================
# ROLE QUEUE
# =============================================================================


class RoleQueue:
    """FIFO queue for a specific role."""

    def __init__(self, role: str, max_size: int = 100):
        self.role = role
        self.max_size = max_size
        self._queue: deque[QueuedStep] = deque()
        self._lock = asyncio.Lock()

    async def enqueue(self, step: QueuedStep) -> bool:
        """Add step to queue. Returns False if queue full."""
        async with self._lock:
            if len(self._queue) >= self.max_size:
                logger.warning(
                    "role_queue_full role=%s size=%d", self.role, len(self._queue)
                )
                return False

            self._queue.append(step)
            logger.info(
                "step_queued role=%s task=%s subtask=%s queue_size=%d",
                self.role,
                step.task_id,
                step.subtask_id,
                len(self._queue),
            )
            return True

    async def dequeue(self) -> Optional[QueuedStep]:
        """Get next step from queue."""
        async with self._lock:
            if self._queue:
                step = self._queue.popleft()
                logger.info(
                    "step_dequeued role=%s task=%s subtask=%s wait_sec=%.2f",
                    self.role,
                    step.task_id,
                    step.subtask_id,
                    step.wait_time_sec(),
                )
                return step
            return None

    async def peek(self) -> Optional[QueuedStep]:
        """Peek at next step without removing."""
        async with self._lock:
            return self._queue[0] if self._queue else None

    def size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "size": len(self._queue),
            "max_size": self.max_size,
            "oldest_wait_sec": self._queue[0].wait_time_sec() if self._queue else 0,
        }


# =============================================================================
# LOAD MANAGER
# =============================================================================


class LoadManager:
    """
    Central load management for the router.

    Tracks node capacity, manages role queues, and provides
    load-aware node selection.
    """

    def __init__(self):
        self._node_loads: Dict[str, NodeLoad] = {}
        self._role_queues: Dict[str, RoleQueue] = {}
        self._lock = asyncio.Lock()

    def register_node(self, node_id: str, max_concurrent: int = 2) -> NodeLoad:
        """Register a node with capacity."""
        if node_id not in self._node_loads:
            self._node_loads[node_id] = NodeLoad(
                node_id=node_id,
                max_concurrent=max_concurrent,
            )
            logger.info(
                "node_registered node=%s max_concurrent=%d", node_id, max_concurrent
            )
        return self._node_loads[node_id]

    def get_node_load(self, node_id: str) -> Optional[NodeLoad]:
        """Get load state for a node."""
        return self._node_loads.get(node_id)

    def get_role_queue(self, role: str) -> RoleQueue:
        """Get or create queue for a role."""
        if role not in self._role_queues:
            self._role_queues[role] = RoleQueue(role)
            logger.info("role_queue_created role=%s", role)
        return self._role_queues[role]

    async def try_acquire_node(self, node_id: str) -> bool:
        """Try to acquire a slot on a node."""
        async with self._lock:
            load = self._node_loads.get(node_id)
            if load:
                return load.acquire()
            return False

    async def release_node(
        self, node_id: str, success: bool = True, latency_ms: float = 0.0
    ) -> None:
        """Release a slot on a node."""
        async with self._lock:
            load = self._node_loads.get(node_id)
            if load:
                load.release(success, latency_ms)

    def select_best_node(
        self,
        compatible_nodes: List[str],
        prefer_low_load: bool = True,
    ) -> Optional[str]:
        """
        Select best available node from compatible list.

        Selection criteria:
        1. Has available capacity
        2. Lowest current load
        3. Best average latency
        """
        candidates = []

        for node_id in compatible_nodes:
            load = self._node_loads.get(node_id)
            if not load:
                # Unknown node - register with defaults
                load = self.register_node(node_id)

            if load.can_accept():
                # Score: prefer low load, then low latency
                load_score = load.current_load / max(1, load.max_concurrent)
                latency_score = (
                    load.avg_latency_ms / 1000 if load.avg_latency_ms > 0 else 0.5
                )
                score = load_score * 0.7 + latency_score * 0.3
                candidates.append((node_id, score, load))

        if not candidates:
            logger.warning("no_available_nodes compatible=%d", len(compatible_nodes))
            return None

        # Sort by score (lower is better) if prefer_low_load
        if prefer_low_load:
            candidates.sort(key=lambda x: x[1])

        selected = candidates[0]
        logger.info(
            "node_selected node=%s score=%.2f load=%d/%d",
            selected[0],
            selected[1],
            selected[2].current_load,
            selected[2].max_concurrent,
        )
        return selected[0]

    async def queue_step(
        self,
        task_id: str,
        subtask_id: str,
        role: str,
        preferred_node: Optional[str] = None,
    ) -> bool:
        """Queue a step for later execution."""
        queue = self.get_role_queue(role)
        step = QueuedStep(
            task_id=task_id,
            subtask_id=subtask_id,
            role=role,
            preferred_node=preferred_node,
        )
        return await queue.enqueue(step)

    async def get_next_queued(self, role: str) -> Optional[QueuedStep]:
        """Get next queued step for a role."""
        queue = self._role_queues.get(role)
        if queue:
            return await queue.dequeue()
        return None

    def get_queue_stats(self) -> Dict[str, Dict]:
        """Get stats for all queues."""
        return {role: queue.to_dict() for role, queue in self._role_queues.items()}

    def get_load_stats(self) -> Dict[str, Dict]:
        """Get load stats for all nodes."""
        return {node_id: load.to_dict() for node_id, load in self._node_loads.items()}

    def get_total_load(self) -> Dict[str, int]:
        """Get aggregate load across all nodes."""
        total_slots = sum(n.max_concurrent for n in self._node_loads.values())
        used_slots = sum(n.current_load for n in self._node_loads.values())
        queued = sum(q.size() for q in self._role_queues.values())

        return {
            "total_slots": total_slots,
            "used_slots": used_slots,
            "available_slots": total_slots - used_slots,
            "utilization_pct": round(100 * used_slots / total_slots, 1)
            if total_slots > 0
            else 0,
            "queued_steps": queued,
        }


# Global singleton
load_manager = LoadManager()
