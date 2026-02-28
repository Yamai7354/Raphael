"""
KQ-603 — Contradiction Detection System.

Detects conflicting knowledge nodes, flags contradictions,
notifies evaluation agents, allows resolution.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.contradictions")


@dataclass
class Contradiction:
    """A detected contradiction between knowledge nodes."""

    contradiction_id: str = field(default_factory=lambda: f"ct_{uuid.uuid4().hex[:8]}")
    node_a: str = ""
    node_b: str = ""
    description: str = ""
    severity: float = 0.5  # 0-1
    status: str = "open"  # open, reviewing, resolved, dismissed
    resolution: str = ""
    detected_at: float = field(default_factory=time.time)
    resolved_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.contradiction_id,
            "nodes": [self.node_a, self.node_b],
            "severity": round(self.severity, 3),
            "status": self.status,
            "resolution": self.resolution,
        }


class ContradictionDetector:
    """Detects and manages knowledge contradictions."""

    def __init__(self):
        self._contradictions: dict[str, Contradiction] = {}
        self._node_claims: dict[str, list[str]] = {}  # node_id -> [claim_keywords]

    def register_claim(self, node_id: str, keywords: list[str]) -> None:
        self._node_claims[node_id] = [k.lower() for k in keywords]

    def check(
        self, node_id: str, keywords: list[str], negation_prefixes: list[str] | None = None
    ) -> list[Contradiction]:
        """Check if a node contradicts existing knowledge."""
        neg = negation_prefixes or ["not_", "anti_", "false_", "no_"]
        kw_set = {k.lower() for k in keywords}
        found: list[Contradiction] = []

        for existing_id, existing_kw in self._node_claims.items():
            if existing_id == node_id:
                continue
            existing_set = set(existing_kw)

            # Check for negation-based contradictions
            for kw in kw_set:
                for prefix in neg:
                    negated = prefix + kw
                    if negated in existing_set:
                        c = self._create(
                            node_id, existing_id, f"'{kw}' contradicts '{negated}'", 0.7
                        )
                        found.append(c)
                    # Also check reverse
                    if kw.startswith(prefix):
                        base = kw[len(prefix) :]
                        if base in existing_set:
                            c = self._create(
                                node_id, existing_id, f"'{kw}' contradicts '{base}'", 0.7
                            )
                            found.append(c)

        self.register_claim(node_id, keywords)
        return found

    def flag(
        self, node_a: str, node_b: str, description: str, severity: float = 0.5
    ) -> Contradiction:
        return self._create(node_a, node_b, description, severity)

    def resolve(self, contradiction_id: str, resolution: str) -> None:
        c = self._contradictions.get(contradiction_id)
        if c:
            c.status = "resolved"
            c.resolution = resolution
            c.resolved_at = time.time()

    def dismiss(self, contradiction_id: str) -> None:
        c = self._contradictions.get(contradiction_id)
        if c:
            c.status = "dismissed"
            c.resolved_at = time.time()

    def _create(self, node_a: str, node_b: str, desc: str, severity: float) -> Contradiction:
        c = Contradiction(node_a=node_a, node_b=node_b, description=desc, severity=severity)
        self._contradictions[c.contradiction_id] = c
        logger.warning("contradiction_detected %s vs %s: %s", node_a, node_b, desc)
        return c

    def get_open(self) -> list[Contradiction]:
        return [c for c in self._contradictions.values() if c.status == "open"]

    def get_for_node(self, node_id: str) -> list[Contradiction]:
        return [
            c for c in self._contradictions.values() if c.node_a == node_id or c.node_b == node_id
        ]

    def get_stats(self) -> dict:
        by_status: dict[str, int] = {}
        for c in self._contradictions.values():
            by_status[c.status] = by_status.get(c.status, 0) + 1
        return {"total": len(self._contradictions), "by_status": by_status}
