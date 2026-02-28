"""
DISC-306 — Capability Integration Engine.

Integrates validated prototypes into the swarm architecture.
Converts approved prototypes to active agents, updates roles,
knowledge graph, and tracks versions.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from .prototype_designer import PrototypeSpec
from .evaluation import EvaluationResult
from .capability_registry import CapabilityRegistry

logger = logging.getLogger("core.discovery.integration")


@dataclass
class IntegrationRecord:
    """Record of an integrated capability."""

    integration_id: str = field(default_factory=lambda: f"int_{uuid.uuid4().hex[:8]}")
    prototype_id: str = ""
    proposal_id: str = ""
    agent_role: str = ""
    improvement_score: float = 0.0
    version: int = 1
    integrated_at: float = field(default_factory=time.time)
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "integration_id": self.integration_id,
            "prototype_id": self.prototype_id,
            "agent_role": self.agent_role,
            "improvement_score": round(self.improvement_score, 3),
            "version": self.version,
            "active": self.active,
        }


class IntegrationEngine:
    """Integrates approved prototypes into the live swarm."""

    def __init__(self, registry: CapabilityRegistry | None = None):
        self.registry = registry or CapabilityRegistry()
        self._integrations: dict[str, IntegrationRecord] = {}
        self._role_updates: list[dict] = []

    def integrate(
        self, prototype: PrototypeSpec, evaluation: EvaluationResult
    ) -> IntegrationRecord:
        """Convert an approved prototype into an active agent capability."""
        if not evaluation.passed:
            raise ValueError(f"Cannot integrate rejected prototype {prototype.prototype_id}")

        # Register the capability
        title = prototype.config.get("title", prototype.agent_role)
        cap = self.registry.register(
            name=title,
            description=f"Auto-discovered: {title}",
            agent_class=prototype.agent_role,
            dependencies=prototype.tool_access,
        )
        self.registry.update_metrics(
            cap.capability_id,
            {
                "improvement_score": evaluation.improvement_score,
                "success_rate": evaluation.task_success_rate,
            },
        )

        # Create integration record
        record = IntegrationRecord(
            prototype_id=prototype.prototype_id,
            proposal_id=prototype.proposal_id,
            agent_role=prototype.agent_role,
            improvement_score=evaluation.improvement_score,
        )
        self._integrations[record.integration_id] = record

        # Track role update
        self._role_updates.append(
            {
                "role": prototype.agent_role,
                "tools": prototype.tool_access,
                "framework": prototype.reasoning_framework,
                "scope": prototype.task_scope,
                "integrated_at": time.time(),
            }
        )

        # Update prototype status
        prototype.status = "integrated"

        logger.info(
            "integration_complete id=%s role=%s score=%.3f",
            record.integration_id,
            prototype.agent_role,
            evaluation.improvement_score,
        )
        return record

    def rollback(self, integration_id: str) -> None:
        """Rollback an integration."""
        record = self._integrations.get(integration_id)
        if record:
            record.active = False
            logger.warning("integration_rolled_back id=%s", integration_id)

    def get_active(self) -> list[IntegrationRecord]:
        return [r for r in self._integrations.values() if r.active]

    def get_role_updates(self) -> list[dict]:
        return list(self._role_updates)

    def get_all(self) -> list[dict]:
        return [r.to_dict() for r in self._integrations.values()]

    def get_stats(self) -> dict:
        active = [r for r in self._integrations.values() if r.active]
        return {
            "total_integrations": len(self._integrations),
            "active": len(active),
            "avg_improvement": round(
                sum(r.improvement_score for r in active) / max(1, len(active)), 3
            ),
        }
