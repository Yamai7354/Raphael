"""
SOS-509 — Autonomy & Self-Regulation Module.

Enables the swarm to adjust its own operational parameters:
role ratios, curiosity, exploration, agent retirement,
and efficiency improvements.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.self_regulation")


@dataclass
class RegulationAction:
    """An automatic regulation action taken by the swarm."""

    action_type: str = ""  # adjust_curiosity, retire_agent, rebalance_roles, optimize
    description: str = ""
    parameters: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class SelfRegulation:
    """Autonomously adjusts swarm operational parameters."""

    def __init__(
        self,
        target_exploration_ratio: float = 0.25,
        min_fitness_threshold: float = 0.2,
        rebalance_interval_seconds: float = 300,
    ):
        self.target_exploration = target_exploration_ratio
        self.min_fitness = min_fitness_threshold
        self.rebalance_interval = rebalance_interval_seconds
        self._actions: list[RegulationAction] = []
        self._last_rebalance: float = 0

    def evaluate_and_adjust(self, swarm_snapshot: dict) -> list[RegulationAction]:
        """Evaluate swarm state and generate regulatory actions."""
        actions: list[RegulationAction] = []

        # 1. Adjust curiosity based on discovery rate
        discovery_rate = swarm_snapshot.get("discovery_rate", 0)
        innovation_score = swarm_snapshot.get("innovation_score", 0.5)
        if innovation_score < 0.3:
            actions.append(
                RegulationAction(
                    action_type="adjust_curiosity",
                    description=f"Increase curiosity: innovation score low ({innovation_score:.2f})",
                    parameters={"curiosity_delta": 0.1, "reason": "low_innovation"},
                )
            )
        elif innovation_score > 0.8 and discovery_rate > 5:
            actions.append(
                RegulationAction(
                    action_type="adjust_curiosity",
                    description="Decrease curiosity: innovation saturated",
                    parameters={"curiosity_delta": -0.05, "reason": "saturated"},
                )
            )

        # 2. Identify underperforming agents
        agents = swarm_snapshot.get("agents", [])
        for agent in agents:
            fitness = agent.get("fitness_score", 1.0)
            name = agent.get("name", "unknown")
            if fitness < self.min_fitness:
                actions.append(
                    RegulationAction(
                        action_type="retire_agent",
                        description=f"Retire {name}: fitness {fitness:.2f} below threshold {self.min_fitness}",
                        parameters={"agent": name, "fitness": fitness},
                    )
                )

        # 3. Rebalance roles
        now = time.time()
        if now - self._last_rebalance >= self.rebalance_interval:
            role_counts = swarm_snapshot.get("role_counts", {})
            total_agents = sum(role_counts.values()) if role_counts else 0
            if total_agents > 0:
                exploring = role_counts.get("Explorer", 0)
                ratio = exploring / total_agents
                if abs(ratio - self.target_exploration) > 0.1:
                    actions.append(
                        RegulationAction(
                            action_type="rebalance_roles",
                            description=f"Rebalance: exploration ratio {ratio:.0%} vs target {self.target_exploration:.0%}",
                            parameters={"current_ratio": ratio, "target": self.target_exploration},
                        )
                    )
            self._last_rebalance = now

        # 4. Efficiency improvements
        task_failure_rate = swarm_snapshot.get("task_failure_rate", 0)
        if task_failure_rate > 0.3:
            actions.append(
                RegulationAction(
                    action_type="optimize",
                    description=f"High failure rate ({task_failure_rate:.0%}): investigate root causes",
                    parameters={"failure_rate": task_failure_rate},
                )
            )

        self._actions.extend(actions)
        if actions:
            logger.info("self_regulation: %d actions generated", len(actions))
        return actions

    def get_history(self, limit: int = 30) -> list[dict]:
        return [
            {"type": a.action_type, "description": a.description, "params": a.parameters}
            for a in self._actions[-limit:]
        ]

    def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        for a in self._actions:
            by_type[a.action_type] = by_type.get(a.action_type, 0) + 1
        return {"total_actions": len(self._actions), "by_type": by_type}
