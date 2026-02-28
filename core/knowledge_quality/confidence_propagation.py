"""
KQ-609 — Knowledge Confidence Propagation.

Propagates trust scores across related knowledge nodes.
Trusted nodes boost neighbors; low-confidence nodes reduce them.
"""

import logging
from collections import defaultdict

logger = logging.getLogger("core.knowledge_quality.confidence_propagation")


class ConfidencePropagation:
    """Propagates confidence through the knowledge graph."""

    def __init__(
        self,
        propagation_factor: float = 0.3,
        max_iterations: int = 5,
        min_change_threshold: float = 0.001,
    ):
        self.factor = propagation_factor
        self.max_iterations = max_iterations
        self.min_change = min_change_threshold
        self._scores: dict[str, float] = {}
        self._edges: dict[str, set[str]] = defaultdict(set)
        self._iterations_run = 0

    def set_score(self, node_id: str, confidence: float) -> None:
        self._scores[node_id] = confidence

    def add_edge(self, node_a: str, node_b: str) -> None:
        self._edges[node_a].add(node_b)
        self._edges[node_b].add(node_a)

    def propagate(self) -> dict[str, float]:
        """Run propagation until convergence or max iterations."""
        self._iterations_run = 0
        for iteration in range(self.max_iterations):
            self._iterations_run += 1
            max_delta = 0.0
            new_scores: dict[str, float] = {}

            for node_id, score in self._scores.items():
                neighbors = self._edges.get(node_id, set())
                if not neighbors:
                    new_scores[node_id] = score
                    continue

                # Average neighbor confidence
                neighbor_scores = [self._scores.get(n, 0.5) for n in neighbors]
                neighbor_avg = sum(neighbor_scores) / len(neighbor_scores)

                # Blend: own score + factor * neighbor influence
                new_score = score * (1 - self.factor) + neighbor_avg * self.factor
                new_score = max(0, min(1, new_score))
                new_scores[node_id] = new_score

                delta = abs(new_score - score)
                if delta > max_delta:
                    max_delta = delta

            self._scores = new_scores
            if max_delta < self.min_change:
                break

        return dict(self._scores)

    def get_score(self, node_id: str) -> float:
        return self._scores.get(node_id, 0.5)

    def get_boosted(self, threshold: float = 0.7) -> list[str]:
        return [nid for nid, s in self._scores.items() if s >= threshold]

    def get_diminished(self, threshold: float = 0.3) -> list[str]:
        return [nid for nid, s in self._scores.items() if s < threshold]

    def get_stats(self) -> dict:
        if not self._scores:
            return {"total_nodes": 0}
        scores = list(self._scores.values())
        return {
            "total_nodes": len(self._scores),
            "total_edges": sum(len(v) for v in self._edges.values()) // 2,
            "avg_confidence": round(sum(scores) / len(scores), 3),
            "iterations_last_run": self._iterations_run,
        }
