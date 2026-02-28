"""
DISC-314 — System Innovation Scoring.

Measures how effectively the swarm discovers and integrates improvements.
Tracks innovation rate, prototype success rate, system improvement index,
and capability growth rate.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.discovery.innovation_scoring")


@dataclass
class InnovationSnapshot:
    """Point-in-time innovation metrics."""

    timestamp: float = field(default_factory=time.time)
    innovation_rate: float = 0.0  # discoveries per hour
    prototype_success_rate: float = 0.0  # pass rate
    improvement_index: float = 0.0  # weighted improvement
    capability_growth_rate: float = 0.0  # new capabilities per day


class InnovationScorer:
    """Computes and tracks system-level innovation metrics."""

    def __init__(self):
        self._discovery_timestamps: list[float] = []
        self._prototype_outcomes: list[bool] = []  # True=pass, False=fail
        self._improvement_scores: list[float] = []
        self._capability_timestamps: list[float] = []
        self._history: list[InnovationSnapshot] = []

    def record_discovery(self) -> None:
        self._discovery_timestamps.append(time.time())

    def record_prototype_outcome(self, passed: bool, improvement_score: float = 0.0) -> None:
        self._prototype_outcomes.append(passed)
        if passed:
            self._improvement_scores.append(improvement_score)

    def record_capability_added(self) -> None:
        self._capability_timestamps.append(time.time())

    def compute(self) -> InnovationSnapshot:
        """Compute current innovation metrics."""
        now = time.time()

        # Innovation rate: discoveries in the last hour
        hour_ago = now - 3600
        recent_discoveries = len([t for t in self._discovery_timestamps if t > hour_ago])
        innovation_rate = recent_discoveries  # per hour

        # Prototype success rate
        if self._prototype_outcomes:
            last_20 = self._prototype_outcomes[-20:]
            prototype_success = sum(last_20) / len(last_20)
        else:
            prototype_success = 0.0

        # System improvement index (weighted avg of improvement scores)
        if self._improvement_scores:
            last_10 = self._improvement_scores[-10:]
            improvement_idx = sum(last_10) / len(last_10)
        else:
            improvement_idx = 0.0

        # Capability growth rate (new capabilities per day)
        day_ago = now - 86400
        recent_caps = len([t for t in self._capability_timestamps if t > day_ago])
        growth_rate = recent_caps  # per day

        snapshot = InnovationSnapshot(
            innovation_rate=round(innovation_rate, 2),
            prototype_success_rate=round(prototype_success, 3),
            improvement_index=round(improvement_idx, 3),
            capability_growth_rate=round(growth_rate, 2),
        )
        self._history.append(snapshot)
        return snapshot

    def get_score(self) -> float:
        """Get a composite innovation score (0-1)."""
        snap = self.compute() if not self._history else self._history[-1]
        # Weighted composite
        score = (
            0.25 * min(1.0, snap.innovation_rate / 5)
            + 0.30 * snap.prototype_success_rate
            + 0.30 * snap.improvement_index
            + 0.15 * min(1.0, snap.capability_growth_rate / 3)
        )
        return round(score, 3)

    def get_trend(self, limit: int = 20) -> list[dict]:
        return [
            {
                "timestamp": s.timestamp,
                "innovation_rate": s.innovation_rate,
                "success_rate": s.prototype_success_rate,
                "improvement_index": s.improvement_index,
                "growth_rate": s.capability_growth_rate,
            }
            for s in self._history[-limit:]
        ]

    def get_stats(self) -> dict:
        score = self.get_score()
        return {
            "composite_score": score,
            "total_discoveries": len(self._discovery_timestamps),
            "total_prototypes": len(self._prototype_outcomes),
            "total_capabilities": len(self._capability_timestamps),
            "total_improvements": len(self._improvement_scores),
            "snapshots": len(self._history),
        }
