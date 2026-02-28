"""
SOS-505 — Policy & Behavior Controller.

System-wide policies: curiosity thresholds, exploration limits,
role distribution, memory gate thresholds, dynamic strategy adjustment.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.policy_controller")


@dataclass
class SwarmPolicy:
    """Configurable swarm behavior policy."""

    # Curiosity & exploration
    curiosity_threshold: float = 0.5  # 0-1, how aggressively to explore
    max_exploration_ratio: float = 0.3  # max % of agents exploring
    # Role distribution
    min_researchers: int = 2
    min_analysts: int = 1
    max_idle_agents: int = 3
    # Memory gates
    memory_acceptance_threshold: float = 0.6  # min quality for embedding
    memory_dedup_similarity: float = 0.92  # similarity threshold for dedup
    # Discovery & evolution
    max_concurrent_experiments: int = 3
    min_improvement_for_integration: float = 0.5
    # Safety
    max_agent_count: int = 50
    auto_retire_below_score: float = 0.2

    def to_dict(self) -> dict:
        return {
            "curiosity_threshold": self.curiosity_threshold,
            "max_exploration_ratio": self.max_exploration_ratio,
            "memory_acceptance_threshold": self.memory_acceptance_threshold,
            "max_concurrent_experiments": self.max_concurrent_experiments,
            "max_agent_count": self.max_agent_count,
            "auto_retire_below_score": self.auto_retire_below_score,
        }


class PolicyController:
    """Manages and enforces swarm-wide policies."""

    def __init__(self, policy: SwarmPolicy | None = None):
        self.policy = policy or SwarmPolicy()
        self._adjustments: list[dict] = []

    def should_explore(self, current_exploring_ratio: float) -> bool:
        return current_exploring_ratio < self.policy.max_exploration_ratio

    def should_accept_memory(self, quality_score: float) -> bool:
        return quality_score >= self.policy.memory_acceptance_threshold

    def should_retire_agent(self, fitness_score: float) -> bool:
        return fitness_score < self.policy.auto_retire_below_score

    def can_spawn_agent(self, current_count: int) -> bool:
        return current_count < self.policy.max_agent_count

    def can_start_experiment(self, running_count: int) -> bool:
        return running_count < self.policy.max_concurrent_experiments

    def adjust(self, **kwargs) -> None:
        """Dynamically adjust policy values."""
        changes: dict = {}
        for k, v in kwargs.items():
            if hasattr(self.policy, k):
                old = getattr(self.policy, k)
                setattr(self.policy, k, v)
                changes[k] = {"old": old, "new": v}
        if changes:
            self._adjustments.append({"changes": changes, "timestamp": time.time()})
            logger.info("policy_adjusted %s", changes)

    def get_policy(self) -> dict:
        return self.policy.to_dict()

    def get_adjustment_history(self) -> list[dict]:
        return self._adjustments[-20:]

    def get_stats(self) -> dict:
        return {
            "policy": self.policy.to_dict(),
            "total_adjustments": len(self._adjustments),
        }
