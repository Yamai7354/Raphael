"""
KQ-607 — Agent Reputation System.

Scores agents based on knowledge quality they produce.
High-reputation agents influence validation; low performers flagged.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.reputation")


@dataclass
class ReputationRecord:
    agent_name: str = ""
    contributions: int = 0
    validated_count: int = 0
    rejected_count: int = 0
    total_quality_sum: float = 0.0
    reputation_score: float = 0.5  # 0-1
    last_contribution: float = field(default_factory=time.time)

    @property
    def avg_quality(self) -> float:
        return self.total_quality_sum / max(1, self.contributions)

    @property
    def validation_rate(self) -> float:
        total = self.validated_count + self.rejected_count
        return self.validated_count / max(1, total)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "reputation": round(self.reputation_score, 3),
            "contributions": self.contributions,
            "avg_quality": round(self.avg_quality, 3),
            "validation_rate": round(self.validation_rate, 3),
        }


class AgentReputationSystem:
    """Tracks and scores agent reliability based on knowledge quality."""

    def __init__(self, low_rep_threshold: float = 0.3):
        self.low_rep_threshold = low_rep_threshold
        self._records: dict[str, ReputationRecord] = {}

    def record_contribution(
        self, agent_name: str, quality_score: float, validated: bool | None = None
    ) -> ReputationRecord:
        rec = self._records.setdefault(agent_name, ReputationRecord(agent_name=agent_name))
        rec.contributions += 1
        rec.total_quality_sum += quality_score
        rec.last_contribution = time.time()

        if validated is True:
            rec.validated_count += 1
        elif validated is False:
            rec.rejected_count += 1

        # Update reputation: weighted average of validation rate and quality
        rec.reputation_score = 0.5 * rec.validation_rate + 0.5 * min(1.0, rec.avg_quality)
        return rec

    def get_reputation(self, agent_name: str) -> float:
        rec = self._records.get(agent_name)
        return rec.reputation_score if rec else 0.5

    def get_top_agents(self, limit: int = 10) -> list[ReputationRecord]:
        return sorted(self._records.values(), key=lambda r: r.reputation_score, reverse=True)[
            :limit
        ]

    def get_low_performers(self) -> list[ReputationRecord]:
        return [
            r
            for r in self._records.values()
            if r.reputation_score < self.low_rep_threshold and r.contributions >= 3
        ]

    def get_validation_weight(self, agent_name: str) -> float:
        """How much weight this agent's validation vote carries."""
        rep = self.get_reputation(agent_name)
        return max(0.1, rep)  # Minimum weight of 0.1

    def get_all(self, limit: int = 50) -> list[dict]:
        agents = sorted(self._records.values(), key=lambda r: r.reputation_score, reverse=True)
        return [r.to_dict() for r in agents[:limit]]

    def get_stats(self) -> dict:
        if not self._records:
            return {"total_agents": 0}
        reps = [r.reputation_score for r in self._records.values()]
        return {
            "total_agents": len(self._records),
            "avg_reputation": round(sum(reps) / len(reps), 3),
            "low_performers": len(self.get_low_performers()),
        }
