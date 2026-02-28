"""
SOS-513 — Swarm Analytics & Optimization Engine.

Evaluates efficiency of agents, experiments, and memory.
Suggests improvements and provides actionable metrics.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.analytics")


@dataclass
class OptimizationSuggestion:
    category: str = ""  # task_allocation, resource, curiosity, memory
    description: str = ""
    expected_impact: str = ""
    priority: int = 5

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "description": self.description,
            "impact": self.expected_impact,
            "priority": self.priority,
        }


class SwarmAnalytics:
    """Analyzes swarm performance and generates optimization suggestions."""

    def __init__(self):
        self._snapshots: list[dict] = []
        self._suggestions: list[OptimizationSuggestion] = []

    def record_snapshot(self, data: dict) -> None:
        self._snapshots.append({**data, "timestamp": time.time()})
        if len(self._snapshots) > 200:
            self._snapshots = self._snapshots[-200:]

    def analyze(self, current_state: dict) -> list[OptimizationSuggestion]:
        """Analyze current state and generate suggestions."""
        suggestions: list[OptimizationSuggestion] = []

        # Task allocation efficiency
        task_stats = current_state.get("tasks", {})
        pending = task_stats.get("pending", 0)
        if pending > 10:
            suggestions.append(
                OptimizationSuggestion(
                    category="task_allocation",
                    description=f"{pending} tasks queued — consider spawning more agents or rebalancing roles",
                    expected_impact="Reduce task queue backlog",
                    priority=2,
                )
            )

        # Resource utilization
        resource_stats = current_state.get("resources", {})
        avg_load = resource_stats.get("avg_load", 0)
        if avg_load > 0.8:
            suggestions.append(
                OptimizationSuggestion(
                    category="resource",
                    description=f"Average load {avg_load:.0%} — system is overloaded",
                    expected_impact="Prevent task failures from resource exhaustion",
                    priority=1,
                )
            )
        elif avg_load < 0.1:
            suggestions.append(
                OptimizationSuggestion(
                    category="resource",
                    description=f"Average load {avg_load:.0%} — resources underutilized",
                    expected_impact="Better cost efficiency",
                    priority=7,
                )
            )

        # Memory health
        memory_stats = current_state.get("memory", {})
        dedup_rate = memory_stats.get("dedup_rate", 0)
        if dedup_rate > 0.3:
            suggestions.append(
                OptimizationSuggestion(
                    category="memory",
                    description=f"High duplicate rate ({dedup_rate:.0%}) — tighten memory acceptance threshold",
                    expected_impact="Reduce storage waste and improve retrieval quality",
                    priority=4,
                )
            )

        # Agent performance
        agent_stats = current_state.get("agents", {})
        low_performers = agent_stats.get("low_performers", 0)
        if low_performers > 3:
            suggestions.append(
                OptimizationSuggestion(
                    category="task_allocation",
                    description=f"{low_performers} agents underperforming — consider retirement or retraining",
                    expected_impact="Improve overall swarm efficiency",
                    priority=3,
                )
            )

        # Innovation rate
        innovation = current_state.get("innovation_score", 0.5)
        if innovation < 0.3:
            suggestions.append(
                OptimizationSuggestion(
                    category="curiosity",
                    description=f"Low innovation score ({innovation:.2f}) — increase exploration ratio",
                    expected_impact="Improve system self-improvement rate",
                    priority=5,
                )
            )

        self._suggestions.extend(suggestions)
        self.record_snapshot(current_state)
        return suggestions

    def get_suggestions(self, limit: int = 20) -> list[dict]:
        return [s.to_dict() for s in self._suggestions[-limit:]]

    def get_trends(self, metric: str, limit: int = 20) -> list:
        return [
            {"value": s.get(metric, 0), "timestamp": s.get("timestamp", 0)}
            for s in self._snapshots[-limit:]
            if metric in s
        ]

    def get_stats(self) -> dict:
        by_cat: dict[str, int] = {}
        for s in self._suggestions:
            by_cat[s.category] = by_cat.get(s.category, 0) + 1
        return {
            "total_snapshots": len(self._snapshots),
            "total_suggestions": len(self._suggestions),
            "by_category": by_cat,
        }
