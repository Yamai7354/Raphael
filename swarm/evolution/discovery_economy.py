"""
SWARM-113 — Discovery Economy.

Reward system encouraging valuable research and system improvements.
Agents earn rewards for: accepted discoveries, system improvements,
task completions, and innovation. Low-performing agents lose influence.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("swarm.evolution.discovery_economy")


@dataclass
class EconomyAccount:
    """Economic account for a single agent."""

    agent_id: str
    balance: float = 10.0  # Starting credits
    total_earned: float = 0.0
    total_spent: float = 0.0
    discoveries: int = 0
    improvements: int = 0
    innovations: int = 0
    last_activity: float = field(default_factory=time.time)

    @property
    def influence(self) -> float:
        """Agent's economic influence — derived from balance and contributions."""
        contribution_bonus = (self.discoveries + self.improvements + self.innovations) * 0.5
        return max(0.0, self.balance + contribution_bonus)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "balance": round(self.balance, 2),
            "influence": round(self.influence, 2),
            "total_earned": round(self.total_earned, 2),
            "discoveries": self.discoveries,
            "improvements": self.improvements,
            "innovations": self.innovations,
        }


class DiscoveryEconomy:
    """
    Economic system that rewards agents for valuable contributions
    and reduces influence for underperformers.
    """

    # Reward amounts
    DISCOVERY_REWARD = 5.0
    IMPROVEMENT_REWARD = 3.0
    TASK_COMPLETION_REWARD = 1.0
    INNOVATION_REWARD = 8.0

    # Penalty amounts
    IDLE_DECAY = 0.5  # Per idle check
    FAILURE_PENALTY = 1.0

    def __init__(self):
        self._accounts: dict[str, EconomyAccount] = {}

    def get_or_create(self, agent_id: str) -> EconomyAccount:
        if agent_id not in self._accounts:
            self._accounts[agent_id] = EconomyAccount(agent_id=agent_id)
        return self._accounts[agent_id]

    def reward_discovery(self, agent_id: str) -> None:
        acc = self.get_or_create(agent_id)
        acc.balance += self.DISCOVERY_REWARD
        acc.total_earned += self.DISCOVERY_REWARD
        acc.discoveries += 1
        acc.last_activity = time.time()
        logger.info("economy_reward agent=%s type=discovery balance=%.1f", agent_id, acc.balance)

    def reward_improvement(self, agent_id: str) -> None:
        acc = self.get_or_create(agent_id)
        acc.balance += self.IMPROVEMENT_REWARD
        acc.total_earned += self.IMPROVEMENT_REWARD
        acc.improvements += 1
        acc.last_activity = time.time()

    def reward_task(self, agent_id: str) -> None:
        acc = self.get_or_create(agent_id)
        acc.balance += self.TASK_COMPLETION_REWARD
        acc.total_earned += self.TASK_COMPLETION_REWARD
        acc.last_activity = time.time()

    def reward_innovation(self, agent_id: str) -> None:
        acc = self.get_or_create(agent_id)
        acc.balance += self.INNOVATION_REWARD
        acc.total_earned += self.INNOVATION_REWARD
        acc.innovations += 1
        acc.last_activity = time.time()
        logger.info("economy_reward agent=%s type=innovation balance=%.1f", agent_id, acc.balance)

    def penalize_failure(self, agent_id: str) -> None:
        acc = self.get_or_create(agent_id)
        acc.balance = max(0, acc.balance - self.FAILURE_PENALTY)
        acc.total_spent += self.FAILURE_PENALTY

    def apply_idle_decay(self, agent_id: str) -> None:
        """Reduce balance for idle agents."""
        acc = self.get_or_create(agent_id)
        acc.balance = max(0, acc.balance - self.IDLE_DECAY)
        acc.total_spent += self.IDLE_DECAY

    def get_ranking(self) -> list[EconomyAccount]:
        return sorted(self._accounts.values(), key=lambda a: a.influence, reverse=True)

    def get_low_influence(self, threshold: float = 2.0) -> list[str]:
        """Return agent IDs with influence below threshold."""
        return [acc.agent_id for acc in self._accounts.values() if acc.influence < threshold]

    def get_all(self) -> list[dict]:
        return [a.to_dict() for a in self.get_ranking()]

    def remove_agent(self, agent_id: str) -> None:
        self._accounts.pop(agent_id, None)
