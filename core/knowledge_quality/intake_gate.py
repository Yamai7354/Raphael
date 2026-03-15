"""
KQ-700 — Knowledge Intake Gate.

Centralized gateway that validates and enriches ALL data before
it enters Neo4j. Every write path must submit NodeProposal or
EdgeProposal objects through the gate instead of writing raw Cypher.

Rules enforced:
  1. No provenance  → Quarantine label
  2. Skill not in dictionary → Rejected
  3. Tool without manifest → Rejected
  4. PerformanceProfile with zero telemetry → Rejected
  5. PerformanceProfile missing composite key → Rejected
  6. Confidence clamped to [0.0, 1.0]
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from core.knowledge_quality.skill_dictionary import SkillDictionary
from core.knowledge_quality.tool_manifest_registry import ToolManifestRegistry

logger = logging.getLogger("core.knowledge_quality.intake_gate")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class ProposalVerdict(str, Enum):
    APPROVED = "approved"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


@dataclass
class Provenance:
    """Provenance metadata stamped on every node and edge."""

    source: str  # e.g. "llm_registry", "telemetry_agent", "memory_graph"
    confidence: float = 0.5
    first_seen: str = ""  # ISO timestamp, auto-filled
    last_seen: str = ""  # ISO timestamp, auto-filled
    evidence: str = ""  # free-text or ref ID

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now

    def to_props(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "evidence": self.evidence,
        }


@dataclass
class NodeProposal:
    """A proposal to create or update a node in Neo4j."""

    label: str  # e.g. "Model", "Skill", "Tool"
    match_keys: Dict[str, Any]  # MERGE key(s) e.g. {"name": "deepseek-r1"}
    properties: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None
    submitted_by: str = "system"

    @property
    def node_key(self) -> str:
        """Deterministic identifier for dedup."""
        parts = [self.label] + [f"{k}={v}" for k, v in sorted(self.match_keys.items())]
        return "|".join(parts)


@dataclass
class EdgeProposal:
    """A proposal to create or update an edge in Neo4j."""

    from_label: str
    from_keys: Dict[str, Any]
    rel_type: str  # e.g. "HAS_CAPABILITY", "RUNS_ON"
    to_label: str
    to_keys: Dict[str, Any]
    properties: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None
    submitted_by: str = "system"


@dataclass
class GateResult:
    """Result of gate evaluation."""

    verdict: ProposalVerdict
    reason: str = ""
    cypher: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The Gate
# ---------------------------------------------------------------------------

_PERF_PROFILE_REQUIRED_KEYS = {"model", "machine", "quantization"}


class IntakeGate:
    """
    Centralized gate for all Neo4j writes.

    Usage::

        gate = IntakeGate(driver, skill_dict, tool_manifests)
        result = gate.submit_node(proposal)
        results = gate.submit_batch(proposals)

    Supports both sync and async Neo4j drivers — use ``submit_*``
    for sync drivers and ``asubmit_*`` for async drivers.
    """

    def __init__(
        self,
        driver,
        skill_dictionary: SkillDictionary,
        tool_manifest_registry: ToolManifestRegistry,
        database: str = "neo4j",
    ):
        self.driver = driver
        self.skills = skill_dictionary
        self.tools = tool_manifest_registry
        self.database = database
        self._stats = {"approved": 0, "quarantined": 0, "rejected": 0}

    # ── Sync API ──────────────────────────────────────────────────────────

    def submit_node(self, proposal: NodeProposal) -> GateResult:
        """Validate, enrich, and write a single node (sync)."""
        result = self._evaluate_node(proposal)
        if result.verdict != ProposalVerdict.REJECTED:
            self._execute(result.cypher, result.params)
        self._stats[result.verdict.value] += 1
        logger.debug(
            "node %s → %s (%s)", proposal.node_key, result.verdict.value, result.reason
        )
        return result

    def submit_edge(self, proposal: EdgeProposal) -> GateResult:
        """Validate, enrich, and write a single edge (sync)."""
        result = self._evaluate_edge(proposal)
        if result.verdict != ProposalVerdict.REJECTED:
            self._execute(result.cypher, result.params)
        self._stats[result.verdict.value] += 1
        return result

    def submit_batch(
        self, proposals: List[Union[NodeProposal, EdgeProposal]]
    ) -> List[GateResult]:
        """Validate and write a batch of proposals (sync)."""
        results = []
        for p in proposals:
            if isinstance(p, NodeProposal):
                results.append(self.submit_node(p))
            else:
                results.append(self.submit_edge(p))
        return results

    # ── Async API ─────────────────────────────────────────────────────────

    async def asubmit_node(self, proposal: NodeProposal) -> GateResult:
        """Validate, enrich, and write a single node (async)."""
        result = self._evaluate_node(proposal)
        if result.verdict != ProposalVerdict.REJECTED:
            await self._aexecute(result.cypher, result.params)
        self._stats[result.verdict.value] += 1
        logger.debug(
            "node %s → %s (%s)", proposal.node_key, result.verdict.value, result.reason
        )
        return result

    async def asubmit_edge(self, proposal: EdgeProposal) -> GateResult:
        """Validate, enrich, and write a single edge (async)."""
        result = self._evaluate_edge(proposal)
        if result.verdict != ProposalVerdict.REJECTED:
            await self._aexecute(result.cypher, result.params)
        self._stats[result.verdict.value] += 1
        return result

    async def asubmit_batch(
        self, proposals: List[Union[NodeProposal, EdgeProposal]]
    ) -> List[GateResult]:
        """Validate and write a batch of proposals (async)."""
        results = []
        for p in proposals:
            if isinstance(p, NodeProposal):
                results.append(await self.asubmit_node(p))
            else:
                results.append(await self.asubmit_edge(p))
        return results

    # ── Evaluation logic ──────────────────────────────────────────────────

    def _evaluate_node(self, p: NodeProposal) -> GateResult:
        # Rule 1: Provenance required — quarantine if missing
        if p.provenance is None:
            cypher, params = self._build_node_cypher(p, quarantine=True)
            return GateResult(
                ProposalVerdict.QUARANTINED,
                "No provenance provided",
                cypher,
                params,
            )

        # Clamp confidence
        p.provenance.confidence = max(0.0, min(1.0, p.provenance.confidence))

        # Rule 2: Skill nodes must match controlled dictionary
        if p.label == "Skill":
            skill_name = p.match_keys.get("name", "")
            if not self.skills.is_valid(skill_name):
                return GateResult(
                    ProposalVerdict.REJECTED,
                    f"Skill '{skill_name}' not in controlled dictionary",
                )
            # Canonicalize the name
            canonical = self.skills.canonicalize(skill_name)
            if canonical != skill_name:
                p.match_keys["name"] = canonical

        # Rule 3: Tool nodes must have a manifest
        if p.label == "Tool":
            tool_name = p.match_keys.get("name", "")
            if not self.tools.has_manifest(tool_name):
                return GateResult(
                    ProposalVerdict.REJECTED,
                    f"Tool '{tool_name}' has no manifest",
                )

        # Rule 4: PerformanceProfile telemetry filter
        if p.label == "PerformanceProfile":
            tps = p.properties.get("tokens_per_sec", 0)
            lat = p.properties.get("latency_ms", 0)
            if tps == 0 and lat == 0:
                return GateResult(
                    ProposalVerdict.REJECTED,
                    "Zero telemetry — tokens_per_sec=0 and latency_ms=0",
                )
            # Rule 5: Composite key enforcement
            missing = _PERF_PROFILE_REQUIRED_KEYS - set(p.match_keys.keys())
            if missing:
                return GateResult(
                    ProposalVerdict.REJECTED,
                    f"PerformanceProfile missing composite keys: {missing}",
                )

        # Approved
        cypher, params = self._build_node_cypher(p, quarantine=False)
        return GateResult(ProposalVerdict.APPROVED, "", cypher, params)

    def _evaluate_edge(self, p: EdgeProposal) -> GateResult:
        if p.provenance is None:
            props = {**p.properties, "_quarantined": True}
            now = datetime.now(timezone.utc).isoformat()
            props.setdefault("source", p.submitted_by)
            props.setdefault("first_seen", now)
            props.setdefault("last_seen", now)
            cypher, params = self._build_edge_cypher(p, extra_props=props)
            return GateResult(
                ProposalVerdict.QUARANTINED,
                "Edge has no provenance",
                cypher,
                params,
            )

        p.provenance.confidence = max(0.0, min(1.0, p.provenance.confidence))
        props = {**p.properties, **p.provenance.to_props()}
        cypher, params = self._build_edge_cypher(p, extra_props=props)
        return GateResult(ProposalVerdict.APPROVED, "", cypher, params)

    # ── Cypher builders ───────────────────────────────────────────────────

    def _build_node_cypher(
        self, p: NodeProposal, quarantine: bool
    ) -> tuple[str, dict]:
        label = f"{p.label}:Quarantine" if quarantine else p.label

        all_props = {**p.properties}
        if p.provenance:
            all_props.update(p.provenance.to_props())
        else:
            now = datetime.now(timezone.utc).isoformat()
            all_props["first_seen"] = now
            all_props["last_seen"] = now
            all_props["source"] = p.submitted_by
            all_props["confidence"] = 0.0
            all_props["evidence"] = ""
            all_props["_quarantined"] = True

        # ON MATCH: update last_seen + non-key props but preserve first_seen
        set_props = {k: v for k, v in all_props.items() if k != "first_seen"}

        key_clause = ", ".join(f"{k}: $mk_{k}" for k in p.match_keys)
        cypher = (
            f"MERGE (n:{label} {{{key_clause}}})\n"
            f"ON CREATE SET n += $create_props\n"
            f"ON MATCH SET n += $update_props"
        )

        params = {
            **{f"mk_{k}": v for k, v in p.match_keys.items()},
            "create_props": all_props,
            "update_props": set_props,
        }
        return cypher, params

    def _build_edge_cypher(
        self, p: EdgeProposal, extra_props: dict
    ) -> tuple[str, dict]:
        from_clause = ", ".join(f"{k}: $from_{k}" for k in p.from_keys)
        to_clause = ", ".join(f"{k}: $to_{k}" for k in p.to_keys)

        cypher = (
            f"MATCH (a:{p.from_label} {{{from_clause}}})\n"
            f"MATCH (b:{p.to_label} {{{to_clause}}})\n"
            f"MERGE (a)-[r:{p.rel_type}]->(b)\n"
            f"SET r += $props"
        )

        params = {
            **{f"from_{k}": v for k, v in p.from_keys.items()},
            **{f"to_{k}": v for k, v in p.to_keys.items()},
            "props": extra_props,
        }
        return cypher, params

    # ── Execution ─────────────────────────────────────────────────────────

    def _execute(self, cypher: str, params: dict):
        with self.driver.session(database=self.database) as session:
            session.run(cypher, parameters=params)

    async def _aexecute(self, cypher: str, params: dict):
        async with self.driver.session(database=self.database) as session:
            await session.run(cypher, parameters=params)

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        total = sum(self._stats.values())
        return {
            **self._stats,
            "total": total,
            "rejection_rate": (
                round(self._stats["rejected"] / max(1, total), 3)
            ),
        }
