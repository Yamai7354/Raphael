"""
WORLD-408 — Infrastructure Optimization Agent.

Rebalances workloads, recommends infrastructure changes,
moves processes, and suggests new hardware needs.
"""

import logging
import time
from dataclasses import dataclass, field

from .resource_awareness import ResourceAwareness
from .hardware_registry import HardwareRegistry

logger = logging.getLogger("core.world_model.infra_optimizer")


@dataclass
class OptimizationRecommendation:
    """A recommendation for infrastructure improvement."""

    rec_id: str = ""
    rec_type: str = ""  # rebalance, scale_up, migrate, decommission
    description: str = ""
    target: str = ""  # hostname or component
    priority: int = 5  # 1-10
    estimated_improvement: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "type": self.rec_type,
            "description": self.description,
            "target": self.target,
            "priority": self.priority,
            "estimated_improvement": self.estimated_improvement,
        }


class InfraOptimizer:
    """Analyzes system state and generates optimization recommendations."""

    def __init__(
        self,
        resources: ResourceAwareness | None = None,
        hardware: HardwareRegistry | None = None,
        overload_threshold: float = 0.8,
        underload_threshold: float = 0.15,
    ):
        self.resources = resources or ResourceAwareness()
        self.hardware = hardware or HardwareRegistry()
        self.overload_threshold = overload_threshold
        self.underload_threshold = underload_threshold
        self._recommendations: list[OptimizationRecommendation] = []

    def analyze(self) -> list[OptimizationRecommendation]:
        """Analyze current state and generate recommendations."""
        recs: list[OptimizationRecommendation] = []
        current = self.resources.get_all_current()

        overloaded: list[dict] = []
        underloaded: list[dict] = []
        for snap in current:
            if snap["load_score"] > self.overload_threshold:
                overloaded.append(snap)
            elif snap["load_score"] < self.underload_threshold:
                underloaded.append(snap)

        # Rebalance: move work from overloaded to underloaded
        for over in overloaded:
            for under in underloaded:
                rec = OptimizationRecommendation(
                    rec_type="rebalance",
                    description=f"Move workloads from {over['hostname']} (load={over['load_score']}) to {under['hostname']} (load={under['load_score']})",
                    target=over["hostname"],
                    priority=3,
                    estimated_improvement=f"Reduce load on {over['hostname']} by ~{(over['load_score'] - under['load_score']) / 2:.0%}",
                )
                recs.append(rec)
                break  # One recommendation per overloaded machine

        # Scale up: all machines overloaded
        if overloaded and not underloaded:
            recs.append(
                OptimizationRecommendation(
                    rec_type="scale_up",
                    description="All machines are overloaded. Consider adding infrastructure.",
                    target="infrastructure",
                    priority=1,
                    estimated_improvement="Needed to prevent performance degradation",
                )
            )

        # Decommission: very underloaded machines
        for under in underloaded:
            if under["load_score"] < 0.05 and under["queue"] == 0:
                recs.append(
                    OptimizationRecommendation(
                        rec_type="decommission",
                        description=f"Machine {under['hostname']} is idle. Consider decommissioning.",
                        target=under["hostname"],
                        priority=8,
                        estimated_improvement="Reduce infrastructure costs",
                    )
                )

        # GPU optimization: high GPU load
        for snap in current:
            if snap.get("gpu_load_avg", 0) > 90:
                recs.append(
                    OptimizationRecommendation(
                        rec_type="gpu_optimization",
                        description=f"GPU on {snap['hostname']} at {snap['gpu_load_avg']:.0f}%. Consider distributing GPU tasks.",
                        target=snap["hostname"],
                        priority=2,
                        estimated_improvement="Reduce GPU bottleneck",
                    )
                )

        self._recommendations.extend(recs)
        return recs

    def get_recommendations(self, limit: int = 20) -> list[dict]:
        return [r.to_dict() for r in self._recommendations[-limit:]]

    def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        for r in self._recommendations:
            by_type[r.rec_type] = by_type.get(r.rec_type, 0) + 1
        return {"total_recommendations": len(self._recommendations), "by_type": by_type}
