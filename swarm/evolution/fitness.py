"""
SWARM-101 — Agent Fitness Scoring.

Evaluates agent performance using measurable outputs:
accepted_memories, completed_tasks, system_impact, and efficiency.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("swarm.evolution.fitness")


@dataclass
class FitnessScore:
    """Composite fitness score for a single agent."""

    agent_id: str
    accepted_memories: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    system_impact: float = 0.0  # Cumulative value of contributions
    total_time_spent: float = 0.0  # Seconds spent on tasks
    last_updated: float = field(default_factory=time.time)

    @property
    def efficiency(self) -> float:
        """Tasks completed per unit time. Higher is better."""
        if self.total_time_spent <= 0:
            return 0.0
        return self.completed_tasks / self.total_time_spent

    @property
    def success_rate(self) -> float:
        """Ratio of successful tasks to total attempted."""
        total = self.completed_tasks + self.failed_tasks
        if total == 0:
            return 0.0
        return self.completed_tasks / total

    @property
    def composite_score(self) -> float:
        """
        Weighted composite fitness score (0..100 scale).
        Weights:
            completed_tasks: 30%
            accepted_memories: 25%
            system_impact: 25%
            efficiency: 20%
        """
        task_score = min(self.completed_tasks * 2.0, 30.0)
        memory_score = min(self.accepted_memories * 5.0, 25.0)
        impact_score = min(self.system_impact * 2.5, 25.0)
        eff_score = min(self.efficiency * 1000.0, 20.0)
        return round(task_score + memory_score + impact_score + eff_score, 2)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "accepted_memories": self.accepted_memories,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "system_impact": self.system_impact,
            "efficiency": round(self.efficiency, 4),
            "success_rate": round(self.success_rate, 4),
            "composite_score": self.composite_score,
            "last_updated": self.last_updated,
        }


class FitnessScorer:
    """
    Central fitness scoring system.
    Tracks per-agent fitness and provides ranking and evaluation APIs.
    """

    def __init__(self):
        self._scores: dict[str, FitnessScore] = {}

    def get_or_create(self, agent_id: str) -> FitnessScore:
        if agent_id not in self._scores:
            self._scores[agent_id] = FitnessScore(agent_id=agent_id)
        return self._scores[agent_id]

    def record_task_completion(
        self, agent_id: str, time_spent: float = 0.0, impact: float = 1.0
    ) -> None:
        score = self.get_or_create(agent_id)
        score.completed_tasks += 1
        score.total_time_spent += time_spent
        score.system_impact += impact
        score.last_updated = time.time()
        logger.info(
            "fitness_updated agent=%s tasks=%d score=%.2f",
            agent_id,
            score.completed_tasks,
            score.composite_score,
        )

    def record_task_failure(self, agent_id: str, time_spent: float = 0.0) -> None:
        score = self.get_or_create(agent_id)
        score.failed_tasks += 1
        score.total_time_spent += time_spent
        score.last_updated = time.time()

    def record_memory_accepted(self, agent_id: str, value: float = 1.0) -> None:
        score = self.get_or_create(agent_id)
        score.accepted_memories += 1
        score.system_impact += value
        score.last_updated = time.time()

    def get_ranking(self) -> list[FitnessScore]:
        """Return all agents ranked by composite fitness (highest first)."""
        return sorted(
            self._scores.values(),
            key=lambda s: s.composite_score,
            reverse=True,
        )

    def get_bottom_n(self, n: int) -> list[FitnessScore]:
        """Return the N lowest-performing agents."""
        ranking = self.get_ranking()
        return ranking[-n:] if len(ranking) >= n else ranking

    def get_top_n(self, n: int) -> list[FitnessScore]:
        """Return the N highest-performing agents."""
        return self.get_ranking()[:n]

    def get_all_scores(self) -> list[dict]:
        return [s.to_dict() for s in self.get_ranking()]

    def remove_agent(self, agent_id: str) -> None:
        self._scores.pop(agent_id, None)


# Global singleton
fitness_scorer = FitnessScorer()
