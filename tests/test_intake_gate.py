"""Tests for the Knowledge Intake Gate (KQ-700)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from core.knowledge_quality.intake_gate import (
    IntakeGate,
    NodeProposal,
    EdgeProposal,
    Provenance,
    GateResult,
    ProposalVerdict,
)
from core.knowledge_quality.skill_dictionary import SkillDictionary, SkillEntry
from core.knowledge_quality.tool_manifest_registry import (
    ToolManifestRegistry,
    ToolManifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = MagicMock()
    session.run = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    driver.session.return_value = ctx
    return driver


@pytest.fixture
def skill_dict():
    sd = SkillDictionary.__new__(SkillDictionary)
    sd._skills = {
        "code_generation": SkillEntry(name="code_generation", category="development"),
        "research_analysis": SkillEntry(name="research_analysis", category="research"),
        "testing": SkillEntry(name="testing", category="development"),
    }
    sd._alias_map = {
        "coding": "code_generation",
        "research": "research_analysis",
    }
    return sd


@pytest.fixture
def tool_registry():
    tr = ToolManifestRegistry.__new__(ToolManifestRegistry)
    tr._manifests = {
        "shell_executor": ToolManifest(name="shell_executor", tool_type="system"),
        "web_browser": ToolManifest(name="web_browser", tool_type="api"),
    }
    return tr


@pytest.fixture
def gate(mock_driver, skill_dict, tool_registry):
    return IntakeGate(mock_driver, skill_dict, tool_registry)


# ---------------------------------------------------------------------------
# Provenance dataclass
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_timestamps_auto_filled(self):
        p = Provenance(source="test")
        assert p.first_seen != ""
        assert p.last_seen != ""
        assert "T" in p.first_seen  # ISO format

    def test_explicit_timestamps_preserved(self):
        p = Provenance(source="test", first_seen="2026-01-01T00:00:00", last_seen="2026-01-02T00:00:00")
        assert p.first_seen == "2026-01-01T00:00:00"
        assert p.last_seen == "2026-01-02T00:00:00"

    def test_to_props(self):
        p = Provenance(source="llm_registry", confidence=0.9, evidence="config.json")
        props = p.to_props()
        assert props["source"] == "llm_registry"
        assert props["confidence"] == 0.9
        assert props["evidence"] == "config.json"
        assert "first_seen" in props
        assert "last_seen" in props


# ---------------------------------------------------------------------------
# Node proposals
# ---------------------------------------------------------------------------


class TestNodeWithProvenance:
    def test_approved(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Model",
            match_keys={"name": "deepseek-r1"},
            properties={"family": "deepseek"},
            provenance=Provenance(source="llm_registry", confidence=0.9),
        ))
        assert result.verdict == ProposalVerdict.APPROVED
        assert "MERGE" in result.cypher
        assert "Model" in result.cypher
        assert "Quarantine" not in result.cypher

    def test_provenance_in_params(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Machine",
            match_keys={"id": "macbook"},
            provenance=Provenance(source="hardware_json", confidence=0.95),
        ))
        assert result.params["create_props"]["source"] == "hardware_json"
        assert result.params["create_props"]["confidence"] == 0.95


class TestNodeWithoutProvenance:
    def test_quarantined(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Model",
            match_keys={"name": "mystery-model"},
        ))
        assert result.verdict == ProposalVerdict.QUARANTINED
        assert "Quarantine" in result.cypher
        assert result.params["create_props"]["_quarantined"] is True
        assert result.params["create_props"]["confidence"] == 0.0

    def test_reason(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Agent",
            match_keys={"name": "unknown"},
        ))
        assert "provenance" in result.reason.lower()


# ---------------------------------------------------------------------------
# Skill dictionary enforcement
# ---------------------------------------------------------------------------


class TestSkillValidation:
    def test_valid_skill_approved(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Skill",
            match_keys={"name": "code_generation"},
            provenance=Provenance(source="skill_dictionary", confidence=1.0),
        ))
        assert result.verdict == ProposalVerdict.APPROVED

    def test_invalid_skill_rejected(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Skill",
            match_keys={"name": "junk_folder_name"},
            provenance=Provenance(source="filesystem_scrape", confidence=0.3),
        ))
        assert result.verdict == ProposalVerdict.REJECTED
        assert "not in controlled dictionary" in result.reason

    def test_alias_canonicalized(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Skill",
            match_keys={"name": "coding"},
            provenance=Provenance(source="test", confidence=0.8),
        ))
        assert result.verdict == ProposalVerdict.APPROVED
        # The match_keys should have been canonicalized
        assert result.params["mk_name"] == "code_generation"


# ---------------------------------------------------------------------------
# Tool manifest enforcement
# ---------------------------------------------------------------------------


class TestToolValidation:
    def test_tool_with_manifest_approved(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Tool",
            match_keys={"name": "shell_executor"},
            provenance=Provenance(source="registry", confidence=0.9),
        ))
        assert result.verdict == ProposalVerdict.APPROVED

    def test_tool_without_manifest_rejected(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Tool",
            match_keys={"name": "agent_ecosystem_portfolio_doc_generator"},
            provenance=Provenance(source="path_scrape", confidence=0.5),
        ))
        assert result.verdict == ProposalVerdict.REJECTED
        assert "no manifest" in result.reason


# ---------------------------------------------------------------------------
# PerformanceProfile telemetry filter
# ---------------------------------------------------------------------------


class TestPerformanceProfile:
    def test_zero_telemetry_rejected(self, gate):
        result = gate.submit_node(NodeProposal(
            label="PerformanceProfile",
            match_keys={"model": "test", "machine": "mac", "quantization": "q4"},
            properties={"tokens_per_sec": 0, "latency_ms": 0},
            provenance=Provenance(source="telemetry", confidence=0.5),
        ))
        assert result.verdict == ProposalVerdict.REJECTED
        assert "Zero telemetry" in result.reason

    def test_valid_telemetry_approved(self, gate):
        result = gate.submit_node(NodeProposal(
            label="PerformanceProfile",
            match_keys={"model": "deepseek", "machine": "mac", "quantization": "q4"},
            properties={"tokens_per_sec": 50, "latency_ms": 200},
            provenance=Provenance(source="telemetry", confidence=0.9),
        ))
        assert result.verdict == ProposalVerdict.APPROVED

    def test_nonzero_latency_only_approved(self, gate):
        result = gate.submit_node(NodeProposal(
            label="PerformanceProfile",
            match_keys={"model": "m", "machine": "mac", "quantization": "q4"},
            properties={"tokens_per_sec": 0, "latency_ms": 150},
            provenance=Provenance(source="telemetry", confidence=0.7),
        ))
        assert result.verdict == ProposalVerdict.APPROVED

    def test_missing_composite_key_rejected(self, gate):
        result = gate.submit_node(NodeProposal(
            label="PerformanceProfile",
            match_keys={"model": "test", "machine": "mac"},
            properties={"tokens_per_sec": 50, "latency_ms": 100},
            provenance=Provenance(source="telemetry", confidence=0.9),
        ))
        assert result.verdict == ProposalVerdict.REJECTED
        assert "composite keys" in result.reason


# ---------------------------------------------------------------------------
# Edge proposals
# ---------------------------------------------------------------------------


class TestEdgeProposals:
    def test_edge_with_provenance_approved(self, gate):
        result = gate.submit_edge(EdgeProposal(
            from_label="Model",
            from_keys={"name": "deepseek"},
            rel_type="RUNS_ON",
            to_label="Machine",
            to_keys={"id": "macbook"},
            provenance=Provenance(source="llm_registry", confidence=0.9),
        ))
        assert result.verdict == ProposalVerdict.APPROVED
        assert "MERGE (a)-[r:RUNS_ON]->(b)" in result.cypher
        assert result.params["props"]["source"] == "llm_registry"

    def test_edge_without_provenance_quarantined(self, gate):
        result = gate.submit_edge(EdgeProposal(
            from_label="Agent",
            from_keys={"name": "portfolio_agent"},
            rel_type="HAS_SKILL",
            to_label="Skill",
            to_keys={"name": "code_generation"},
        ))
        assert result.verdict == ProposalVerdict.QUARANTINED
        assert result.params["props"]["_quarantined"] is True


# ---------------------------------------------------------------------------
# Confidence clamping
# ---------------------------------------------------------------------------


class TestConfidenceClamping:
    def test_over_one_clamped(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Agent",
            match_keys={"name": "test"},
            provenance=Provenance(source="test", confidence=1.5),
        ))
        assert result.verdict == ProposalVerdict.APPROVED
        assert result.params["create_props"]["confidence"] == 1.0

    def test_negative_clamped(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Agent",
            match_keys={"name": "test"},
            provenance=Provenance(source="test", confidence=-0.5),
        ))
        assert result.verdict == ProposalVerdict.APPROVED
        assert result.params["create_props"]["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Cypher generation
# ---------------------------------------------------------------------------


class TestCypherGeneration:
    def test_node_merge_structure(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Machine",
            match_keys={"id": "desktop"},
            properties={"hostname": "ai-desktop"},
            provenance=Provenance(source="hw", confidence=0.95),
        ))
        assert "MERGE (n:Machine {id: $mk_id})" in result.cypher
        assert "ON CREATE SET" in result.cypher
        assert "ON MATCH SET" in result.cypher

    def test_on_match_preserves_first_seen(self, gate):
        result = gate.submit_node(NodeProposal(
            label="Model",
            match_keys={"name": "test"},
            provenance=Provenance(source="test", confidence=0.5),
        ))
        # first_seen should be in create_props but NOT in update_props
        assert "first_seen" in result.params["create_props"]
        assert "first_seen" not in result.params["update_props"]

    def test_edge_cypher_structure(self, gate):
        result = gate.submit_edge(EdgeProposal(
            from_label="Model",
            from_keys={"name": "m1"},
            rel_type="HAS_CAPABILITY",
            to_label="Capability",
            to_keys={"name": "reasoning"},
            provenance=Provenance(source="test"),
        ))
        assert "MATCH (a:Model {name: $from_name})" in result.cypher
        assert "MATCH (b:Capability {name: $to_name})" in result.cypher
        assert "MERGE (a)-[r:HAS_CAPABILITY]->(b)" in result.cypher


# ---------------------------------------------------------------------------
# Batch submission
# ---------------------------------------------------------------------------


class TestBatch:
    def test_mixed_batch(self, gate):
        proposals = [
            NodeProposal(
                label="Model",
                match_keys={"name": "m1"},
                provenance=Provenance(source="test"),
            ),
            EdgeProposal(
                from_label="Model",
                from_keys={"name": "m1"},
                rel_type="RUNS_ON",
                to_label="Machine",
                to_keys={"id": "mac"},
                provenance=Provenance(source="test"),
            ),
            NodeProposal(
                label="Skill",
                match_keys={"name": "junk_path"},
                provenance=Provenance(source="test"),
            ),
        ]
        results = gate.submit_batch(proposals)
        assert len(results) == 3
        assert results[0].verdict == ProposalVerdict.APPROVED
        assert results[1].verdict == ProposalVerdict.APPROVED
        assert results[2].verdict == ProposalVerdict.REJECTED


# ---------------------------------------------------------------------------
# Stats tracking
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_tracked(self, gate):
        gate.submit_node(NodeProposal(
            label="Model", match_keys={"name": "m1"},
            provenance=Provenance(source="test"),
        ))
        gate.submit_node(NodeProposal(
            label="Model", match_keys={"name": "m2"},
        ))
        gate.submit_node(NodeProposal(
            label="Skill", match_keys={"name": "junk"},
            provenance=Provenance(source="test"),
        ))
        stats = gate.get_stats()
        assert stats["approved"] == 1
        assert stats["quarantined"] == 1
        assert stats["rejected"] == 1
        assert stats["total"] == 3


# ---------------------------------------------------------------------------
# Async API
# ---------------------------------------------------------------------------


class TestAsync:
    @pytest.mark.asyncio
    async def test_async_node_submission(self, skill_dict, tool_registry):
        mock_driver = MagicMock()
        session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_driver.session.return_value = ctx
        gate = IntakeGate(mock_driver, skill_dict, tool_registry)

        result = await gate.asubmit_node(NodeProposal(
            label="Model",
            match_keys={"name": "test"},
            provenance=Provenance(source="test"),
        ))
        assert result.verdict == ProposalVerdict.APPROVED
        session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_rejected_not_executed(self, skill_dict, tool_registry):
        mock_driver = MagicMock()
        session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_driver.session.return_value = ctx
        gate = IntakeGate(mock_driver, skill_dict, tool_registry)

        result = await gate.asubmit_node(NodeProposal(
            label="Skill",
            match_keys={"name": "junk_skill"},
            provenance=Provenance(source="test"),
        ))
        assert result.verdict == ProposalVerdict.REJECTED
        session.run.assert_not_called()


# ---------------------------------------------------------------------------
# SkillDictionary unit tests
# ---------------------------------------------------------------------------


class TestSkillDictionary:
    def test_loads_from_yaml(self):
        sd = SkillDictionary()
        assert "code_generation" in sd.list_all()
        assert sd.is_valid("code_generation")

    def test_alias_valid(self):
        sd = SkillDictionary()
        assert sd.is_valid("coding")
        assert sd.canonicalize("coding") == "code_generation"

    def test_invalid_name(self):
        sd = SkillDictionary()
        assert not sd.is_valid("totally_fake_skill_xyz")

    def test_runtime_add(self):
        sd = SkillDictionary()
        sd.add("new_skill", category="test")
        assert sd.is_valid("new_skill")

    def test_get_by_category(self):
        sd = SkillDictionary()
        devs = sd.get_by_category("development")
        names = [s.name for s in devs]
        assert "code_generation" in names

    def test_empty_path(self, tmp_path):
        sd = SkillDictionary(path=tmp_path / "nonexistent.yaml")
        assert sd.list_all() == []


# ---------------------------------------------------------------------------
# ToolManifestRegistry unit tests
# ---------------------------------------------------------------------------


class TestToolManifestRegistry:
    def test_loads_from_directory(self):
        tr = ToolManifestRegistry()
        assert tr.has_manifest("shell_executor")
        assert tr.has_manifest("web_browser")

    def test_get_manifest(self):
        tr = ToolManifestRegistry()
        m = tr.get("shell_executor")
        assert m is not None
        assert m.tool_type == "system"
        assert "shell_access" in m.requires_capabilities

    def test_unknown_tool(self):
        tr = ToolManifestRegistry()
        assert not tr.has_manifest("agent_ecosystem_portfolio_doc_generator")

    def test_get_capabilities(self):
        tr = ToolManifestRegistry()
        caps = tr.get_capabilities_for("web_browser")
        assert "network_access" in caps

    def test_empty_directory(self, tmp_path):
        tr = ToolManifestRegistry(manifests_dir=tmp_path / "empty")
        assert tr.list_all() == []
