"""
SWARM-109 — Central Intelligence Monitor.

Monitors swarm health and triggers system adjustments.
Tracks: graph growth, knowledge quality, agent effectiveness,
exploration rate, and memory efficiency.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("swarm.evolution.monitor")


@dataclass
class SwarmHealthSnapshot:
    """Point-in-time health reading."""

    timestamp: float = field(default_factory=time.time)
    graph_node_count: int = 0
    graph_edge_count: int = 0
    knowledge_quality: float = 0.0  # 0-1
    agent_effectiveness: float = 0.0  # avg composite fitness
    exploration_rate: float = 0.0  # tasks exploring vs exploiting
    memory_efficiency: float = 0.0  # useful memories / total
    active_agents: int = 0
    pending_tasks: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "graph_node_count": self.graph_node_count,
            "graph_edge_count": self.graph_edge_count,
            "knowledge_quality": round(self.knowledge_quality, 2),
            "agent_effectiveness": round(self.agent_effectiveness, 2),
            "exploration_rate": round(self.exploration_rate, 2),
            "memory_efficiency": round(self.memory_efficiency, 2),
            "active_agents": self.active_agents,
            "pending_tasks": self.pending_tasks,
        }


@dataclass
class SystemAdjustment:
    """A corrective action triggered by the monitor."""

    action: str
    reason: str
    timestamp: float = field(default_factory=time.time)
    parameters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "parameters": self.parameters,
        }


class CentralIntelligenceMonitor:
    """
    Continuously monitors swarm health and triggers adjustments.

    Can:
    - Adjust role ratios
    - Throttle exploration
    - Trigger consolidation cycles
    """

    # Thresholds for triggering adjustments
    LOW_EFFECTIVENESS_THRESHOLD = 0.3
    HIGH_EXPLORATION_THRESHOLD = 0.7
    LOW_MEMORY_EFFICIENCY_THRESHOLD = 0.3
    MAX_HISTORY_SIZE = 100

    def __init__(self):
        self._history: list[SwarmHealthSnapshot] = []
        self._adjustments: list[SystemAdjustment] = []
        self._adjustment_callbacks: dict[str, list] = {
            "adjust_roles": [],
            "throttle_exploration": [],
            "trigger_consolidation": [],
        }

    def record_snapshot(self, snapshot: SwarmHealthSnapshot) -> list[SystemAdjustment]:
        """
        Record a health snapshot and evaluate whether adjustments are needed.
        Returns any triggered adjustments.
        """
        self._history.append(snapshot)
        if len(self._history) > self.MAX_HISTORY_SIZE:
            self._history = self._history[-self.MAX_HISTORY_SIZE :]

        adjustments = self._evaluate(snapshot)
        self._adjustments.extend(adjustments)
        return adjustments

    def _evaluate(self, snapshot: SwarmHealthSnapshot) -> list[SystemAdjustment]:
        """Evaluate current health and produce necessary adjustments."""
        adjustments = []

        # Check agent effectiveness
        if snapshot.agent_effectiveness < self.LOW_EFFECTIVENESS_THRESHOLD:
            adj = SystemAdjustment(
                action="adjust_roles",
                reason=f"Agent effectiveness too low ({snapshot.agent_effectiveness:.2f})",
                parameters={"increase_evaluators": True},
            )
            adjustments.append(adj)
            logger.warning("monitor_alert low_effectiveness=%.2f", snapshot.agent_effectiveness)

        # Check exploration rate
        if snapshot.exploration_rate > self.HIGH_EXPLORATION_THRESHOLD:
            adj = SystemAdjustment(
                action="throttle_exploration",
                reason=f"Exploration rate too high ({snapshot.exploration_rate:.2f})",
                parameters={"target_rate": 0.4},
            )
            adjustments.append(adj)
            logger.warning("monitor_alert high_exploration=%.2f", snapshot.exploration_rate)

        # Check memory efficiency
        if snapshot.memory_efficiency < self.LOW_MEMORY_EFFICIENCY_THRESHOLD:
            adj = SystemAdjustment(
                action="trigger_consolidation",
                reason=f"Memory efficiency too low ({snapshot.memory_efficiency:.2f})",
                parameters={"aggressive": True},
            )
            adjustments.append(adj)
            logger.warning("monitor_alert low_memory_eff=%.2f", snapshot.memory_efficiency)

        return adjustments

    def get_latest_snapshot(self) -> SwarmHealthSnapshot | None:
        return self._history[-1] if self._history else None

    def get_trend(self, metric: str, window: int = 10) -> list[float]:
        """Get recent trend for a specific metric."""
        recent = self._history[-window:]
        return [getattr(s, metric, 0.0) for s in recent]

    def get_adjustments(self, limit: int = 10) -> list[dict]:
        return [a.to_dict() for a in self._adjustments[-limit:]]

    def get_dashboard_data(self) -> dict:
        latest = self.get_latest_snapshot()
        return {
            "current": latest.to_dict() if latest else {},
            "trends": {
                "effectiveness": self.get_trend("agent_effectiveness"),
                "exploration": self.get_trend("exploration_rate"),
                "memory_efficiency": self.get_trend("memory_efficiency"),
            },
            "recent_adjustments": self.get_adjustments(5),
            "total_snapshots": len(self._history),
        }
