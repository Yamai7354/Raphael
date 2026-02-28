"""
KQ-608 — Embedding Quality Filter.

Ensures only high-value knowledge is embedded and indexed.
Low-confidence research bypasses embeddings.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.embedding_filter")


@dataclass
class EmbeddingDecision:
    node_id: str = ""
    quality_score: float = 0.0
    decision: str = ""  # embed, skip, defer, update
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


class EmbeddingQualityFilter:
    """Gates the embedding pipeline based on knowledge quality."""

    def __init__(self, min_score_for_embedding: float = 0.4, update_threshold_delta: float = 0.2):
        self.min_score = min_score_for_embedding
        self.update_delta = update_threshold_delta
        self._decisions: list[EmbeddingDecision] = []
        self._embedded: dict[str, float] = {}  # node_id -> score at embed time

    def evaluate(
        self, node_id: str, quality_score: float, validation_status: str = "unvalidated"
    ) -> EmbeddingDecision:
        """Decide whether to embed a knowledge node."""

        # Rejected knowledge never gets embedded
        if validation_status == "rejected":
            return self._decide(node_id, quality_score, "skip", "rejected_knowledge")

        # Below minimum score
        if quality_score < self.min_score:
            return self._decide(
                node_id, quality_score, "skip", f"score {quality_score:.2f} < {self.min_score}"
            )

        # Already embedded: check if update needed
        if node_id in self._embedded:
            old_score = self._embedded[node_id]
            if abs(quality_score - old_score) >= self.update_delta:
                self._embedded[node_id] = quality_score
                return self._decide(
                    node_id,
                    quality_score,
                    "update",
                    f"score changed {old_score:.2f} -> {quality_score:.2f}",
                )
            return self._decide(node_id, quality_score, "skip", "already_embedded_no_change")

        # Pending validation: defer
        if validation_status == "pending":
            return self._decide(node_id, quality_score, "defer", "awaiting_validation")

        # Embed it
        self._embedded[node_id] = quality_score
        return self._decide(
            node_id, quality_score, "embed", f"score {quality_score:.2f} >= {self.min_score}"
        )

    def _decide(self, node_id: str, score: float, decision: str, reason: str) -> EmbeddingDecision:
        d = EmbeddingDecision(
            node_id=node_id, quality_score=score, decision=decision, reason=reason
        )
        self._decisions.append(d)
        return d

    def get_embedded_nodes(self) -> set[str]:
        return set(self._embedded.keys())

    def get_stats(self) -> dict:
        by_decision: dict[str, int] = {}
        for d in self._decisions:
            by_decision[d.decision] = by_decision.get(d.decision, 0) + 1
        return {
            "total_evaluated": len(self._decisions),
            "currently_embedded": len(self._embedded),
            "by_decision": by_decision,
        }
