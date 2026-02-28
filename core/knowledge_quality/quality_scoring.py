"""
KQ-601 — Knowledge Quality Scoring Engine.

Evaluates reliability and usefulness of knowledge nodes using:
citation count, agent agreement, recency, usage frequency,
and validation status. Scores update dynamically.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.scoring")


@dataclass
class QualityScore:
    """Quality assessment for a knowledge node."""

    node_id: str = ""
    citation_count: int = 0
    agent_agreement: float = 0.0  # 0-1, fraction of agents that agree
    recency_score: float = 1.0  # 1.0 = fresh, decays over time
    usage_frequency: int = 0
    validation_status: str = "unvalidated"  # unvalidated, pending, validated, rejected
    composite_score: float = 0.0
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "score": round(self.composite_score, 3),
            "citations": self.citation_count,
            "agreement": round(self.agent_agreement, 3),
            "recency": round(self.recency_score, 3),
            "usage": self.usage_frequency,
            "validation": self.validation_status,
        }


class QualityScoringEngine:
    """Scores knowledge nodes for reliability and usefulness."""

    WEIGHTS = {
        "citation": 0.25,
        "agreement": 0.25,
        "recency": 0.15,
        "usage": 0.15,
        "validation": 0.20,
    }
    VALIDATION_SCORES = {
        "validated": 1.0,
        "pending": 0.5,
        "unvalidated": 0.3,
        "rejected": 0.0,
    }
    RECENCY_HALFLIFE_HOURS = 168  # 1 week

    def __init__(self):
        self._scores: dict[str, QualityScore] = {}

    def score(
        self,
        node_id: str,
        citation_count: int = 0,
        agent_agreement: float = 0.0,
        created_at: float = 0,
        usage_frequency: int = 0,
        validation_status: str = "unvalidated",
    ) -> QualityScore:
        """Calculate or update quality score for a node."""
        # Recency decay
        age_hours = (time.time() - created_at) / 3600 if created_at > 0 else 0
        recency = 0.5 ** (age_hours / self.RECENCY_HALFLIFE_HOURS) if age_hours > 0 else 1.0

        # Normalize factors to 0-1
        citation_norm = min(1.0, citation_count / 10)
        usage_norm = min(1.0, usage_frequency / 50)
        validation_norm = self.VALIDATION_SCORES.get(validation_status, 0.3)

        composite = (
            self.WEIGHTS["citation"] * citation_norm
            + self.WEIGHTS["agreement"] * agent_agreement
            + self.WEIGHTS["recency"] * recency
            + self.WEIGHTS["usage"] * usage_norm
            + self.WEIGHTS["validation"] * validation_norm
        )

        qs = QualityScore(
            node_id=node_id,
            citation_count=citation_count,
            agent_agreement=agent_agreement,
            recency_score=recency,
            usage_frequency=usage_frequency,
            validation_status=validation_status,
            composite_score=composite,
        )
        self._scores[node_id] = qs
        return qs

    def get_score(self, node_id: str) -> QualityScore | None:
        return self._scores.get(node_id)

    def get_top(self, limit: int = 20) -> list[QualityScore]:
        return sorted(self._scores.values(), key=lambda s: s.composite_score, reverse=True)[:limit]

    def get_below_threshold(self, threshold: float = 0.3) -> list[QualityScore]:
        return [s for s in self._scores.values() if s.composite_score < threshold]

    def bulk_refresh(self, node_ages: dict[str, float]) -> int:
        """Refresh recency scores for all tracked nodes."""
        updated = 0
        for node_id, created_at in node_ages.items():
            qs = self._scores.get(node_id)
            if qs:
                age_hours = (time.time() - created_at) / 3600
                qs.recency_score = 0.5 ** (age_hours / self.RECENCY_HALFLIFE_HOURS)
                qs.composite_score = (
                    self.WEIGHTS["citation"] * min(1, qs.citation_count / 10)
                    + self.WEIGHTS["agreement"] * qs.agent_agreement
                    + self.WEIGHTS["recency"] * qs.recency_score
                    + self.WEIGHTS["usage"] * min(1, qs.usage_frequency / 50)
                    + self.WEIGHTS["validation"]
                    * self.VALIDATION_SCORES.get(qs.validation_status, 0.3)
                )
                qs.last_updated = time.time()
                updated += 1
        return updated

    def get_stats(self) -> dict:
        if not self._scores:
            return {"total_scored": 0}
        scores = [s.composite_score for s in self._scores.values()]
        return {
            "total_scored": len(self._scores),
            "avg_score": round(sum(scores) / len(scores), 3),
            "below_030": sum(1 for s in scores if s < 0.3),
            "above_070": sum(1 for s in scores if s > 0.7),
        }
