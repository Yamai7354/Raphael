"""
WORLD-414 — Autonomous Infrastructure Improvement.

Proposes model redistribution, infrastructure scaling,
agent deployment strategies, and hardware optimization.
Proposals reviewed before execution.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from .resource_awareness import ResourceAwareness
from .hardware_registry import HardwareRegistry
from .model_capabilities import ModelCapabilityMap
from .infra_optimizer import InfraOptimizer

logger = logging.getLogger("core.world_model.infra_improvement")


@dataclass
class ImprovementProposal:
    """A proposal for autonomous infrastructure improvement."""

    proposal_id: str = field(default_factory=lambda: f"imp_{uuid.uuid4().hex[:8]}")
    category: str = ""  # model_redistribution, scaling, deployment, hardware
    title: str = ""
    description: str = ""
    steps: list[str] = field(default_factory=list)
    estimated_impact: str = ""
    risk_level: str = "medium"  # low, medium, high
    status: str = "proposed"  # proposed, approved, executing, completed, rejected
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "steps": self.steps,
            "risk": self.risk_level,
            "status": self.status,
        }


class InfraImprovementEngine:
    """Generates and tracks infrastructure improvement proposals."""

    def __init__(
        self,
        resources: ResourceAwareness | None = None,
        hardware: HardwareRegistry | None = None,
        models: ModelCapabilityMap | None = None,
        optimizer: InfraOptimizer | None = None,
    ):
        self.resources = resources or ResourceAwareness()
        self.hardware = hardware or HardwareRegistry()
        self.models = models or ModelCapabilityMap()
        self.optimizer = optimizer or InfraOptimizer(self.resources, self.hardware)
        self._proposals: dict[str, ImprovementProposal] = {}

    def analyze_and_propose(self) -> list[ImprovementProposal]:
        """Analyze system state and generate improvement proposals."""
        proposals: list[ImprovementProposal] = []

        # Model redistribution: check if models are poorly distributed
        model_stats = self.models.get_stats()
        if model_stats.get("available", 0) > 0:
            # Check if any host has too many models vs others
            host_models: dict[str, int] = {}
            for m in self.models._models.values():
                for h in m.hosted_on:
                    host_models[h] = host_models.get(h, 0) + 1
            if host_models:
                max_host = max(host_models.values())
                min_host = min(host_models.values()) if len(host_models) > 1 else max_host
                if max_host > min_host * 2 and max_host > 3:
                    proposals.append(
                        ImprovementProposal(
                            category="model_redistribution",
                            title="Rebalance model distribution across hosts",
                            description=f"Model imbalance detected: max={max_host}, min={min_host} per host",
                            steps=[
                                "Identify least-used models on overloaded hosts",
                                "Select underloaded target hosts with sufficient VRAM",
                                "Migrate model instances",
                                "Verify availability after migration",
                            ],
                            estimated_impact="Better model access latency and GPU utilization",
                            risk_level="medium",
                        )
                    )

        # Scaling recommendations from optimizer
        opt_recs = self.optimizer.analyze()
        for rec in opt_recs:
            if rec.rec_type == "scale_up":
                proposals.append(
                    ImprovementProposal(
                        category="scaling",
                        title="Scale infrastructure",
                        description=rec.description,
                        steps=[
                            "Assess current workload demands",
                            "Identify bottleneck resources (CPU/GPU/RAM)",
                            "Provision additional capacity",
                            "Rebalance workloads across new infrastructure",
                        ],
                        estimated_impact=rec.estimated_improvement,
                        risk_level="low",
                    )
                )

        # Agent deployment: check for underserved roles
        hw_stats = self.hardware.get_stats()
        if hw_stats.get("total_gpus", 0) > 0:
            gpu_machines = self.hardware.get_with_gpu()
            if len(gpu_machines) > 0:
                idle_gpu = [m for m in gpu_machines if len(m.active_workloads) == 0]
                if idle_gpu:
                    proposals.append(
                        ImprovementProposal(
                            category="deployment",
                            title=f"Deploy agents on {len(idle_gpu)} idle GPU machines",
                            description=f"{len(idle_gpu)} GPU-equipped machines have no active workloads",
                            steps=[
                                "Identify tasks that would benefit from GPU",
                                "Spawn specialized agents on idle machines",
                                "Route GPU-heavy tasks to new agents",
                            ],
                            estimated_impact="Better GPU utilization",
                            risk_level="low",
                        )
                    )

        # Hardware optimization: check overloaded
        overloaded = self.resources.get_overloaded()
        if overloaded:
            proposals.append(
                ImprovementProposal(
                    category="hardware",
                    title=f"Optimize {len(overloaded)} overloaded machines",
                    description=f"Machines at high load: {', '.join(overloaded[:5])}",
                    steps=[
                        "Audit running processes for unnecessary workloads",
                        "Migrate non-critical tasks to underloaded machines",
                        "Increase resource limits if possible",
                        "Consider hardware upgrades for persistent bottlenecks",
                    ],
                    estimated_impact="Reduce overload and improve task latency",
                    risk_level="medium",
                )
            )

        for p in proposals:
            self._proposals[p.proposal_id] = p
        return proposals

    def approve(self, proposal_id: str) -> None:
        p = self._proposals.get(proposal_id)
        if p:
            p.status = "approved"

    def reject(self, proposal_id: str) -> None:
        p = self._proposals.get(proposal_id)
        if p:
            p.status = "rejected"

    def complete(self, proposal_id: str) -> None:
        p = self._proposals.get(proposal_id)
        if p:
            p.status = "completed"

    def get_pending(self) -> list[dict]:
        return [p.to_dict() for p in self._proposals.values() if p.status == "proposed"]

    def get_all(self) -> list[dict]:
        return [p.to_dict() for p in self._proposals.values()]

    def get_stats(self) -> dict:
        by_status: dict[str, int] = {}
        for p in self._proposals.values():
            by_status[p.status] = by_status.get(p.status, 0) + 1
        return {"total_proposals": len(self._proposals), "by_status": by_status}
