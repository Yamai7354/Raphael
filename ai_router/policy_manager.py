"""
Policy Metrics & Validation Manager for AI Router (Phase 12).

Aggregates metrics to evaluate policies and manages safe rollouts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque

logger = logging.getLogger("ai_router.policy_manager")


@dataclass
class PolicyMetricSnapshot:
    """Aggregated metrics for a time window."""

    timestamp: datetime
    avg_latency_ms: float
    success_rate: float
    avg_queue_depth: float
    utilization: float


class PolicyMetricsAggregator:
    """
    Collects high-level metrics to feed into the policy engine (Ticket 1).
    """

    def __init__(self):
        self.snapshots = deque(maxlen=60)  # Keep last hour of minute-snapshots

    def record_snapshot(self, metrics: Dict[str, Any]):
        """Record a metric snapshot."""
        snapshot = PolicyMetricSnapshot(
            timestamp=datetime.now(),
            avg_latency_ms=metrics.get("avg_latency_ms", 0),
            success_rate=metrics.get("success_rate", 1.0),
            avg_queue_depth=metrics.get("queue_depth", 0),
            utilization=metrics.get("utilization", 0.0),
        )
        self.snapshots.append(snapshot)
        logger.debug("policy_snapshot_recorded latency=%.1f", snapshot.avg_latency_ms)

    def get_trend(self, window_minutes: int = 5) -> Dict[str, float]:
        """Get trend for the last N minutes."""
        if not self.snapshots:
            return {}

        recent = [
            s
            for s in self.snapshots
            if s.timestamp > datetime.now() - timedelta(minutes=window_minutes)
        ]

        if not recent:
            return {}

        return {
            "avg_latency": sum(s.avg_latency_ms for s in recent) / len(recent),
            "avg_success": sum(s.success_rate for s in recent) / len(recent),
        }


@dataclass
class PolicyConfig:
    """Represents a set of tunable policy parameters."""

    max_concurrent_tasks: int = 10
    scale_up_threshold_queue: int = 5
    offload_queue_threshold: int = 10
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)


class PolicyManager:
    """
    Manages active policy configuration, validation, and rollback (Ticket 5).
    """

    def __init__(self):
        self.current_policy = PolicyConfig()
        self.history: List[PolicyConfig] = [self.current_policy]
        self.dry_run_mode = False
        self.metrics = PolicyMetricsAggregator()

    def propose_change(self, changes: Dict[str, Any], dry_run: bool = False) -> Dict:
        """
        Propose a policy change.
        If dry_run=True, returns what WOULD change without applying it.
        """
        new_config = PolicyConfig(
            max_concurrent_tasks=changes.get(
                "max_concurrent_tasks", self.current_policy.max_concurrent_tasks
            ),
            scale_up_threshold_queue=changes.get(
                "scale_up_threshold_queue", self.current_policy.scale_up_threshold_queue
            ),
            offload_queue_threshold=changes.get(
                "offload_queue_threshold", self.current_policy.offload_queue_threshold
            ),
            version=self.current_policy.version + 1,
        )

        diff = {"old": self.current_policy.__dict__, "new": new_config.__dict__}

        if dry_run or self.dry_run_mode:
            logger.info("policy_change_dry_run diff=%s", diff)
            return {"status": "dry_run", "diff": diff}

        # Apply change
        self.history.append(new_config)
        self.current_policy = new_config
        logger.info("policy_updated version=%d diff=%s", new_config.version, diff)
        return {"status": "applied", "version": new_config.version}

    def rollback(self) -> bool:
        """Rollback to previous policy version."""
        if len(self.history) < 2:
            return False

        self.history.pop()  # Remove current
        self.current_policy = self.history[-1]
        logger.info("policy_rollback version=%d", self.current_policy.version)
        return True


# Global singleton
policy_manager = PolicyManager()
