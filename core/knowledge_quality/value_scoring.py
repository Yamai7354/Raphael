"""
KQ-614 — Long-Term Knowledge Value Scoring.

Measures long-term usefulness: reuse frequency, experiment impact,
contribution to improvements, citation by agents.
Scores influence memory retention decisions.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.value_scoring")


@dataclass
class ValueScore:
    node_id: str = ""
    reuse_count: int = 0
    experiment_impact_count: int = 0
    improvement_contributions: int = 0
    agent_citations: int = 0
    composite_value: float = 0.0
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "value": round(self.composite_value, 3),
            "reuse": self.reuse_count,
            "experiment_impact": self.experiment_impact_count,
            "improvements": self.improvement_contributions,
            "citations": self.agent_citations,
        }


class LongTermValueScorer:
    """Scores knowledge nodes for long-term value."""

    WEIGHTS = {
        "reuse": 0.30,
        "experiment": 0.25,
        "improvement": 0.25,
        "citation": 0.20,
    }

    def __init__(self, retention_threshold: float = 0.2):
        self.retention_threshold = retention_threshold
        self._scores: dict[str, ValueScore] = {}

    def record_reuse(self, node_id: str) -> None:
        vs = self._scores.setdefault(node_id, ValueScore(node_id=node_id))
        vs.reuse_count += 1
        self._recalculate(vs)

    def record_experiment_impact(self, node_id: str) -> None:
        vs = self._scores.setdefault(node_id, ValueScore(node_id=node_id))
        vs.experiment_impact_count += 1
        self._recalculate(vs)

    def record_improvement(self, node_id: str) -> None:
        vs = self._scores.setdefault(node_id, ValueScore(node_id=node_id))
        vs.improvement_contributions += 1
        self._recalculate(vs)

    def record_citation(self, node_id: str) -> None:
        vs = self._scores.setdefault(node_id, ValueScore(node_id=node_id))
        vs.agent_citations += 1
        self._recalculate(vs)

    def _recalculate(self, vs: ValueScore) -> None:
        reuse_norm = min(1.0, vs.reuse_count / 20)
        exp_norm = min(1.0, vs.experiment_impact_count / 5)
        imp_norm = min(1.0, vs.improvement_contributions / 5)
        cite_norm = min(1.0, vs.agent_citations / 10)

        vs.composite_value = (
            self.WEIGHTS["reuse"] * reuse_norm
            + self.WEIGHTS["experiment"] * exp_norm
            + self.WEIGHTS["improvement"] * imp_norm
            + self.WEIGHTS["citation"] * cite_norm
        )
        vs.last_updated = time.time()

    def should_retain(self, node_id: str) -> bool:
        vs = self._scores.get(node_id)
        if not vs:
            return True  # Unknown nodes retained by default
        return vs.composite_value >= self.retention_threshold

    def get_top(self, limit: int = 20) -> list[ValueScore]:
        return sorted(self._scores.values(), key=lambda v: v.composite_value, reverse=True)[:limit]

    def get_candidates_for_archival(self) -> list[str]:
        return [
            nid for nid, vs in self._scores.items() if vs.composite_value < self.retention_threshold
        ]

    def get_score(self, node_id: str) -> ValueScore | None:
        return self._scores.get(node_id)

    def get_stats(self) -> dict:
        if not self._scores:
            return {"total_scored": 0}
        values = [v.composite_value for v in self._scores.values()]
        return {
            "total_scored": len(self._scores),
            "avg_value": round(sum(values) / len(values), 3),
            "archival_candidates": len(self.get_candidates_for_archival()),
        }
