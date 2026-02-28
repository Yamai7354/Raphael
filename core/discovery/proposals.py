"""
DISC-302 — Capability Proposal Generator.

Generates proposals for new capabilities or agents based on
detected opportunities. Proposals include description, expected
improvement, required components, and evaluation criteria.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from .opportunities import Opportunity, OpportunityType

logger = logging.getLogger("core.discovery.proposals")


@dataclass
class CapabilityProposal:
    """A proposal for a new swarm capability."""

    proposal_id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    opportunity_id: str = ""
    expected_improvement: str = ""
    required_components: list[str] = field(default_factory=list)
    evaluation_criteria: list[str] = field(default_factory=list)
    impact_score: float = 0.0
    status: str = "proposed"  # proposed, accepted, rejected, prototyped, integrated
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "opportunity_id": self.opportunity_id,
            "expected_improvement": self.expected_improvement,
            "required_components": self.required_components,
            "evaluation_criteria": self.evaluation_criteria,
            "impact_score": round(self.impact_score, 3),
            "status": self.status,
        }


# Templates map opportunity types to proposal blueprints
_TEMPLATES: dict[OpportunityType, dict] = {
    OpportunityType.TASK_FAILURE: {
        "prefix": "Failure Recovery",
        "components": ["error_handler", "retry_logic", "fallback_agent"],
        "criteria": ["failure_rate_reduction", "recovery_time", "task_completion_rate"],
        "improvement": "Reduce failure rate by implementing specialized error handling",
    },
    OpportunityType.BOTTLENECK: {
        "prefix": "Performance Optimizer",
        "components": ["cache_layer", "parallel_executor", "load_balancer"],
        "criteria": ["latency_reduction", "throughput_increase", "resource_efficiency"],
        "improvement": "Reduce execution time through caching and parallelization",
    },
    OpportunityType.INEFFICIENCY: {
        "prefix": "Workflow Optimizer",
        "components": ["task_router", "agent_specializer", "pipeline_optimizer"],
        "criteria": ["utilization_increase", "idle_time_reduction", "task_throughput"],
        "improvement": "Improve agent utilization through better task routing",
    },
    OpportunityType.MISSING_CAPABILITY: {
        "prefix": "New Capability Agent",
        "components": ["agent_definition", "tool_access", "reasoning_framework"],
        "criteria": ["task_coverage", "success_rate", "quality_score"],
        "improvement": "Add new agent type to handle previously unsupported tasks",
    },
    OpportunityType.KNOWLEDGE_GAP: {
        "prefix": "Knowledge Expansion",
        "components": ["research_agent", "knowledge_indexer", "validation_pipeline"],
        "criteria": ["coverage_increase", "accuracy", "retrieval_quality"],
        "improvement": "Expand knowledge base to cover identified gaps",
    },
}


class ProposalGenerator:
    """Generates capability proposals from opportunities."""

    def __init__(self):
        self._proposals: dict[str, CapabilityProposal] = {}

    def generate(self, opportunity: Opportunity) -> CapabilityProposal:
        """Generate a proposal from an opportunity using templates."""
        template = _TEMPLATES.get(
            opportunity.opportunity_type, _TEMPLATES[OpportunityType.INEFFICIENCY]
        )

        proposal = CapabilityProposal(
            title=f"{template['prefix']}: {opportunity.title}",
            description=f"Proposal to address: {opportunity.description}",
            opportunity_id=opportunity.opportunity_id,
            expected_improvement=template["improvement"],
            required_components=list(template["components"]),
            evaluation_criteria=list(template["criteria"]),
            impact_score=opportunity.impact_estimate,
        )
        self._proposals[proposal.proposal_id] = proposal
        logger.info(
            "proposal_generated id=%s title=%s impact=%.3f",
            proposal.proposal_id,
            proposal.title,
            proposal.impact_score,
        )
        return proposal

    def accept(self, proposal_id: str) -> None:
        if proposal_id in self._proposals:
            self._proposals[proposal_id].status = "accepted"

    def reject(self, proposal_id: str) -> None:
        if proposal_id in self._proposals:
            self._proposals[proposal_id].status = "rejected"

    def get_ranked(self) -> list[CapabilityProposal]:
        return sorted(
            [p for p in self._proposals.values() if p.status == "proposed"],
            key=lambda p: p.impact_score,
            reverse=True,
        )

    def get_all(self) -> list[dict]:
        return [p.to_dict() for p in self._proposals.values()]

    def get_stats(self) -> dict:
        by_status: dict[str, int] = {}
        for p in self._proposals.values():
            by_status[p.status] = by_status.get(p.status, 0) + 1
        return {"total": len(self._proposals), "by_status": by_status}
