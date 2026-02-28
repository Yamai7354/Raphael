"""
SWARM-105 — Swarm Population Control.

Limits the total number of active agents to prevent resource exhaustion.
Retires lowest-fitness agents when the limit is reached.
"""

import logging
from dataclasses import dataclass

from .fitness import FitnessScorer

logger = logging.getLogger("swarm.evolution.population")


@dataclass
class PopulationConfig:
    """Configuration for population control."""

    max_swarm_size: int = 50
    min_swarm_size: int = 5
    retirement_batch_size: int = 3  # How many to retire per cycle
    spawn_cooldown_seconds: float = 60.0  # Min time between spawns


class PopulationController:
    """
    Manages swarm population size.
    Retires low-fitness agents when the cap is reached.
    Provides metrics for dashboard display.
    """

    def __init__(
        self, config: PopulationConfig | None = None, fitness_scorer: FitnessScorer | None = None
    ):
        self.config = config or PopulationConfig()
        self.fitness = fitness_scorer or FitnessScorer()
        self._active_agents: set[str] = set()
        self._retired_agents: list[str] = []
        self._total_spawned: int = 0
        self._total_retired: int = 0

    @property
    def current_size(self) -> int:
        return len(self._active_agents)

    @property
    def at_capacity(self) -> bool:
        return self.current_size >= self.config.max_swarm_size

    def register_agent(self, agent_id: str) -> bool:
        """Register a new agent. Returns False if at capacity."""
        if self.at_capacity:
            logger.warning(
                "population_at_capacity current=%d max=%d",
                self.current_size,
                self.config.max_swarm_size,
            )
            return False
        self._active_agents.add(agent_id)
        self._total_spawned += 1
        logger.info("agent_registered id=%s population=%d", agent_id, self.current_size)
        return True

    def retire_agent(self, agent_id: str) -> None:
        """Remove an agent from the active population."""
        self._active_agents.discard(agent_id)
        self._retired_agents.append(agent_id)
        self._total_retired += 1
        self.fitness.remove_agent(agent_id)
        logger.info("agent_retired id=%s population=%d", agent_id, self.current_size)

    def enforce_limit(self) -> list[str]:
        """
        If over capacity, retire the lowest-fitness agents.
        Returns list of retired agent IDs.
        """
        retired = []
        while self.current_size > self.config.max_swarm_size:
            bottom = self.fitness.get_bottom_n(1)
            if not bottom:
                break
            victim_id = bottom[0].agent_id
            self.retire_agent(victim_id)
            retired.append(victim_id)
            logger.info("population_enforced retired=%s", victim_id)
        return retired

    def can_spawn(self) -> bool:
        """Check if a new agent can be spawned."""
        return not self.at_capacity

    def get_metrics(self) -> dict:
        """Population metrics for dashboard display."""
        return {
            "current_size": self.current_size,
            "max_size": self.config.max_swarm_size,
            "utilization": round(self.current_size / self.config.max_swarm_size, 2),
            "total_spawned": self._total_spawned,
            "total_retired": self._total_retired,
            "active_agents": list(self._active_agents),
            "recently_retired": self._retired_agents[-10:],
        }
