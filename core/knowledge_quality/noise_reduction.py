"""
KQ-605 — Memory Noise Reduction System.

Prevents low-value research from cluttering the graph:
redundancy detection, duplicate merging, compression,
and archival of low-quality data.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.noise_reduction")


@dataclass
class NoiseAction:
    action_type: str = ""  # merge, archive, compress, skip
    node_ids: list[str] = field(default_factory=list)
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


class NoiseReduction:
    """Detects and reduces noise in the knowledge graph."""

    def __init__(
        self, min_quality_for_retention: float = 0.2, similarity_merge_threshold: float = 0.9
    ):
        self.min_quality = min_quality_for_retention
        self.merge_threshold = similarity_merge_threshold
        self._actions: list[NoiseAction] = []
        self._archived: set[str] = set()

    def scan(self, nodes: list[dict]) -> list[NoiseAction]:
        """Scan a batch of nodes for noise. Each dict has id, content, quality_score."""
        actions: list[NoiseAction] = []

        # 1. Archive low-quality nodes
        for node in nodes:
            if node.get("quality_score", 1) < self.min_quality:
                actions.append(
                    NoiseAction(
                        action_type="archive",
                        node_ids=[node["id"]],
                        reason=f"quality {node.get('quality_score', 0):.2f} < {self.min_quality}",
                    )
                )

        # 2. Detect near-duplicates for merging
        contents = [
            (n["id"], set(n.get("content", "").lower().split())) for n in nodes if n.get("content")
        ]
        for i, (id_a, words_a) in enumerate(contents):
            for j, (id_b, words_b) in enumerate(contents):
                if j <= i:
                    continue
                if not words_a or not words_b:
                    continue
                jaccard = len(words_a & words_b) / len(words_a | words_b)
                if jaccard >= self.merge_threshold:
                    actions.append(
                        NoiseAction(
                            action_type="merge",
                            node_ids=[id_a, id_b],
                            reason=f"similarity {jaccard:.2f} >= {self.merge_threshold}",
                        )
                    )

        self._actions.extend(actions)
        return actions

    def archive(self, node_id: str, reason: str = "") -> None:
        self._archived.add(node_id)
        self._actions.append(
            NoiseAction(
                action_type="archive",
                node_ids=[node_id],
                reason=reason,
            )
        )

    def is_archived(self, node_id: str) -> bool:
        return node_id in self._archived

    def get_actions(self, limit: int = 30) -> list[dict]:
        return [
            {"type": a.action_type, "nodes": a.node_ids, "reason": a.reason}
            for a in self._actions[-limit:]
        ]

    def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        for a in self._actions:
            by_type[a.action_type] = by_type.get(a.action_type, 0) + 1
        return {
            "total_actions": len(self._actions),
            "archived": len(self._archived),
            "by_type": by_type,
        }
