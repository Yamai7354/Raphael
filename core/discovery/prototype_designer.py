"""
DISC-303 — Prototype Design System.

Automatically generates prototype agent designs and configurations
from capability proposals. Supports sandbox testing.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from .proposals import CapabilityProposal

logger = logging.getLogger("core.discovery.prototype_designer")


@dataclass
class PrototypeSpec:
    """A prototype agent specification."""

    prototype_id: str = field(default_factory=lambda: f"proto_{uuid.uuid4().hex[:8]}")
    proposal_id: str = ""
    agent_role: str = ""
    tool_access: list[str] = field(default_factory=list)
    reasoning_framework: str = "chain_of_thought"
    task_scope: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    status: str = "draft"  # draft, testing, passed, failed, integrated
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "prototype_id": self.prototype_id,
            "proposal_id": self.proposal_id,
            "agent_role": self.agent_role,
            "tool_access": self.tool_access,
            "reasoning_framework": self.reasoning_framework,
            "task_scope": self.task_scope,
            "status": self.status,
        }


# Maps proposal components to tool/framework selections
_TOOL_MAP = {
    "error_handler": ["error_logger", "retry_executor"],
    "retry_logic": ["retry_executor", "backoff_controller"],
    "fallback_agent": ["agent_spawner", "task_router"],
    "cache_layer": ["memory_cache", "embedding_cache"],
    "parallel_executor": ["thread_pool", "async_runner"],
    "load_balancer": ["task_router", "queue_manager"],
    "task_router": ["task_router", "skill_matcher"],
    "agent_specializer": ["training_pipeline", "role_assigner"],
    "pipeline_optimizer": ["workflow_analyzer", "step_eliminator"],
    "agent_definition": ["agent_spawner", "config_builder"],
    "tool_access": ["tool_registry", "permission_manager"],
    "reasoning_framework": ["prompt_builder", "chain_of_thought"],
    "research_agent": ["web_browser", "document_reader"],
    "knowledge_indexer": ["embedding_pipeline", "graph_writer"],
    "validation_pipeline": ["fact_checker", "cross_reference"],
}

_REASONING_MAP = {
    "task_failure": "error_analysis",
    "bottleneck": "performance_optimization",
    "inefficiency": "workflow_analysis",
    "missing_capability": "capability_design",
    "knowledge_gap": "research_synthesis",
}


class PrototypeDesigner:
    """Generates prototype agent specs from capability proposals."""

    def __init__(self):
        self._prototypes: dict[str, PrototypeSpec] = {}

    def design(self, proposal: CapabilityProposal) -> PrototypeSpec:
        """Auto-generate a prototype from a proposal."""
        # Collect tools from required components
        tools: list[str] = []
        for component in proposal.required_components:
            tools.extend(_TOOL_MAP.get(component, [component]))
        tools = list(dict.fromkeys(tools))  # deduplicate preserving order

        # Pick reasoning framework from opportunity type
        opp_type = (
            proposal.opportunity_id.split("_")[0]
            if "_" in proposal.opportunity_id
            else "inefficiency"
        )
        framework = _REASONING_MAP.get(opp_type, "chain_of_thought")

        proto = PrototypeSpec(
            proposal_id=proposal.proposal_id,
            agent_role=f"discovery_{proposal.proposal_id}",
            tool_access=tools,
            reasoning_framework=framework,
            task_scope=proposal.evaluation_criteria,
            config={
                "title": proposal.title,
                "impact_score": proposal.impact_score,
                "evaluation_criteria": proposal.evaluation_criteria,
            },
        )
        self._prototypes[proto.prototype_id] = proto
        logger.info(
            "prototype_designed id=%s role=%s tools=%d",
            proto.prototype_id,
            proto.agent_role,
            len(tools),
        )
        return proto

    def set_status(self, prototype_id: str, status: str) -> None:
        if prototype_id in self._prototypes:
            self._prototypes[prototype_id].status = status

    def get_drafts(self) -> list[PrototypeSpec]:
        return [p for p in self._prototypes.values() if p.status == "draft"]

    def get_testing(self) -> list[PrototypeSpec]:
        return [p for p in self._prototypes.values() if p.status == "testing"]

    def get_all(self) -> list[dict]:
        return [p.to_dict() for p in self._prototypes.values()]

    def get_stats(self) -> dict:
        by_status: dict[str, int] = {}
        for p in self._prototypes.values():
            by_status[p.status] = by_status.get(p.status, 0) + 1
        return {"total": len(self._prototypes), "by_status": by_status}
