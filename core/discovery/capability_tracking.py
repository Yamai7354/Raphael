"""
DISC-313 — Long-Term Capability Tracking.

Monitors impact of integrated capabilities over time.
Identifies degradation and triggers reevaluation.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.discovery.capability_tracking")


@dataclass
class CapabilitySnapshot:
    """A point-in-time performance snapshot for a capability."""

    capability_id: str
    timestamp: float = field(default_factory=time.time)
    success_rate: float = 0.0
    avg_execution_ms: float = 0.0
    tasks_completed: int = 0
    error_count: int = 0


class CapabilityTracker:
    """Tracks long-term effectiveness of integrated capabilities."""

    def __init__(self, degradation_threshold: float = 0.15, min_snapshots: int = 5):
        self.degradation_threshold = degradation_threshold
        self.min_snapshots = min_snapshots
        self._snapshots: dict[str, list[CapabilitySnapshot]] = {}  # cap_id -> [snapshots]
        self._flagged: set[str] = set()

    def record(
        self,
        capability_id: str,
        success_rate: float,
        avg_execution_ms: float,
        tasks_completed: int,
        error_count: int = 0,
    ) -> None:
        """Record a new performance snapshot."""
        snap = CapabilitySnapshot(
            capability_id=capability_id,
            success_rate=success_rate,
            avg_execution_ms=avg_execution_ms,
            tasks_completed=tasks_completed,
            error_count=error_count,
        )
        self._snapshots.setdefault(capability_id, []).append(snap)

    def check_degradation(self, capability_id: str) -> dict | None:
        """Check if a capability has degraded over time."""
        snapshots = self._snapshots.get(capability_id, [])
        if len(snapshots) < self.min_snapshots:
            return None

        # Compare latest to baseline (first few snapshots)
        baseline = snapshots[:3]
        recent = snapshots[-3:]

        baseline_sr = sum(s.success_rate for s in baseline) / len(baseline)
        recent_sr = sum(s.success_rate for s in recent) / len(recent)
        delta = baseline_sr - recent_sr

        if delta > self.degradation_threshold:
            self._flagged.add(capability_id)
            result = {
                "capability_id": capability_id,
                "degradation": round(delta, 3),
                "baseline_success_rate": round(baseline_sr, 3),
                "recent_success_rate": round(recent_sr, 3),
                "needs_reevaluation": True,
            }
            logger.warning("capability_degraded id=%s delta=%.3f", capability_id, delta)
            return result
        return None

    def check_all(self) -> list[dict]:
        """Check all tracked capabilities for degradation."""
        results = []
        for cap_id in self._snapshots:
            r = self.check_degradation(cap_id)
            if r:
                results.append(r)
        return results

    def get_trend(self, capability_id: str, limit: int = 20) -> list[dict]:
        snapshots = self._snapshots.get(capability_id, [])[-limit:]
        return [
            {
                "timestamp": s.timestamp,
                "success_rate": round(s.success_rate, 3),
                "avg_ms": round(s.avg_execution_ms, 1),
                "tasks": s.tasks_completed,
            }
            for s in snapshots
        ]

    def get_flagged(self) -> list[str]:
        return list(self._flagged)

    def clear_flag(self, capability_id: str) -> None:
        self._flagged.discard(capability_id)

    def get_stats(self) -> dict:
        return {
            "tracked_capabilities": len(self._snapshots),
            "total_snapshots": sum(len(v) for v in self._snapshots.values()),
            "flagged_for_review": len(self._flagged),
        }
