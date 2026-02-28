"""
SWARM-102 — Reputation System.

Tracks agent contributions and influences task assignment and system privileges.
Reputation increases from: stored knowledge, merged code, successful tasks.
Reputation impacts: task bidding priority, resource allocation, spawn ability.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("swarm.evolution.reputation")


class ReputationTier(str, Enum):
    """Privilege tiers based on reputation score."""

    NOVICE = "novice"  # 0-19
    CONTRIBUTOR = "contributor"  # 20-49
    TRUSTED = "trusted"  # 50-79
    ELITE = "elite"  # 80-99
    LEGENDARY = "legendary"  # 100+


@dataclass
class AgentReputation:
    """Reputation profile for a single agent."""

    agent_id: str
    score: float = 0.0
    knowledge_contributions: int = 0
    code_contributions: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    discoveries: int = 0
    penalties: int = 0
    last_updated: float = field(default_factory=time.time)

    @property
    def tier(self) -> ReputationTier:
        if self.score >= 100:
            return ReputationTier.LEGENDARY
        elif self.score >= 80:
            return ReputationTier.ELITE
        elif self.score >= 50:
            return ReputationTier.TRUSTED
        elif self.score >= 20:
            return ReputationTier.CONTRIBUTOR
        return ReputationTier.NOVICE

    @property
    def can_spawn_helpers(self) -> bool:
        """Only TRUSTED tier and above can spawn helper agents."""
        return self.score >= 50

    @property
    def bidding_priority(self) -> float:
        """Higher reputation = higher bidding priority multiplier."""
        return 1.0 + (self.score / 100.0)

    @property
    def resource_allocation_weight(self) -> float:
        """Proportion of resources this agent should receive."""
        return max(0.1, self.score / 100.0)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "score": round(self.score, 2),
            "tier": self.tier.value,
            "knowledge_contributions": self.knowledge_contributions,
            "code_contributions": self.code_contributions,
            "successful_tasks": self.successful_tasks,
            "discoveries": self.discoveries,
            "can_spawn_helpers": self.can_spawn_helpers,
            "bidding_priority": round(self.bidding_priority, 2),
        }


class ReputationTracker:
    """Central reputation management for the entire swarm."""

    # Reward values
    KNOWLEDGE_REWARD = 5.0
    CODE_MERGE_REWARD = 8.0
    TASK_SUCCESS_REWARD = 3.0
    DISCOVERY_REWARD = 10.0
    TASK_FAILURE_PENALTY = -1.5
    IDLE_PENALTY = -0.5

    def __init__(self):
        self._reputations: dict[str, AgentReputation] = {}

    def get_or_create(self, agent_id: str) -> AgentReputation:
        if agent_id not in self._reputations:
            self._reputations[agent_id] = AgentReputation(agent_id=agent_id)
        return self._reputations[agent_id]

    def reward_knowledge(self, agent_id: str) -> None:
        """Research became stored knowledge."""
        rep = self.get_or_create(agent_id)
        rep.score += self.KNOWLEDGE_REWARD
        rep.knowledge_contributions += 1
        rep.last_updated = time.time()
        logger.info("reputation_up agent=%s reason=knowledge score=%.1f", agent_id, rep.score)

    def reward_code_merge(self, agent_id: str) -> None:
        """Code was merged or reused."""
        rep = self.get_or_create(agent_id)
        rep.score += self.CODE_MERGE_REWARD
        rep.code_contributions += 1
        rep.last_updated = time.time()
        logger.info("reputation_up agent=%s reason=code_merge score=%.1f", agent_id, rep.score)

    def reward_task_success(self, agent_id: str) -> None:
        """Task completed successfully."""
        rep = self.get_or_create(agent_id)
        rep.score += self.TASK_SUCCESS_REWARD
        rep.successful_tasks += 1
        rep.last_updated = time.time()

    def reward_discovery(self, agent_id: str) -> None:
        """Agent made a novel discovery."""
        rep = self.get_or_create(agent_id)
        rep.score += self.DISCOVERY_REWARD
        rep.discoveries += 1
        rep.last_updated = time.time()
        logger.info("reputation_up agent=%s reason=discovery score=%.1f", agent_id, rep.score)

    def penalize_failure(self, agent_id: str) -> None:
        """Task failed."""
        rep = self.get_or_create(agent_id)
        rep.score = max(0, rep.score + self.TASK_FAILURE_PENALTY)
        rep.failed_tasks += 1
        rep.last_updated = time.time()

    def penalize_idle(self, agent_id: str) -> None:
        """Agent was idle too long."""
        rep = self.get_or_create(agent_id)
        rep.score = max(0, rep.score + self.IDLE_PENALTY)
        rep.penalties += 1
        rep.last_updated = time.time()

    def get_ranking(self) -> list[AgentReputation]:
        return sorted(self._reputations.values(), key=lambda r: r.score, reverse=True)

    def get_all(self) -> list[dict]:
        return [r.to_dict() for r in self.get_ranking()]

    def remove_agent(self, agent_id: str) -> None:
        self._reputations.pop(agent_id, None)


# Global singleton
reputation_tracker = ReputationTracker()
