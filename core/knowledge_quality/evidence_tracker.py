"""
KQ-602 — Evidence & Citation Tracking.

Tracks sources and supporting evidence for knowledge nodes:
research docs, URLs, experiment results, agent discoveries.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.evidence")


@dataclass
class Evidence:
    """A piece of supporting evidence for a knowledge node."""

    evidence_id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:8]}")
    node_id: str = ""
    source_type: str = ""  # research_doc, url, experiment, agent_discovery
    source_ref: str = ""  # URL, doc ID, experiment ID
    description: str = ""
    submitted_by: str = ""  # agent name
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "node_id": self.node_id,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "submitted_by": self.submitted_by,
            "confidence": round(self.confidence, 3),
        }


class EvidenceTracker:
    """Tracks citations and evidence for knowledge nodes."""

    def __init__(self):
        self._evidence: dict[str, list[Evidence]] = {}  # node_id -> [Evidence]
        self._all: dict[str, Evidence] = {}

    def add(
        self,
        node_id: str,
        source_type: str,
        source_ref: str,
        description: str = "",
        submitted_by: str = "",
        confidence: float = 0.5,
    ) -> Evidence:
        ev = Evidence(
            node_id=node_id,
            source_type=source_type,
            source_ref=source_ref,
            description=description,
            submitted_by=submitted_by,
            confidence=confidence,
        )
        self._evidence.setdefault(node_id, []).append(ev)
        self._all[ev.evidence_id] = ev
        logger.info("evidence_added node=%s type=%s by=%s", node_id, source_type, submitted_by)
        return ev

    def get_for_node(self, node_id: str) -> list[Evidence]:
        return self._evidence.get(node_id, [])

    def get_citation_count(self, node_id: str) -> int:
        return len(self._evidence.get(node_id, []))

    def get_agents_supporting(self, node_id: str) -> list[str]:
        return list({e.submitted_by for e in self._evidence.get(node_id, []) if e.submitted_by})

    def get_agent_agreement(self, node_id: str) -> float:
        """Fraction of unique agents supporting (out of total known agents)."""
        agents = self.get_agents_supporting(node_id)
        all_agents = {
            e.submitted_by for evs in self._evidence.values() for e in evs if e.submitted_by
        }
        if not all_agents:
            return 0.0
        return len(agents) / len(all_agents)

    def get_by_agent(self, agent_name: str) -> list[Evidence]:
        return [e for e in self._all.values() if e.submitted_by == agent_name]

    def get_stats(self) -> dict:
        return {
            "total_evidence": len(self._all),
            "nodes_with_evidence": len(self._evidence),
            "unique_agents": len({e.submitted_by for e in self._all.values() if e.submitted_by}),
        }
