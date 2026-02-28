"""
SWARM-107 — Collective Intelligence Extraction.

Identifies successful agent strategies and distributes them across the swarm.
Extracts best prompts, workflows, and reasoning strategies.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("swarm.evolution.collective_intel")


@dataclass
class StrategyRecord:
    """A recorded successful strategy from an agent."""

    strategy_id: str
    agent_id: str
    domain: str
    description: str
    success_count: int = 1
    effectiveness: float = 0.0
    prompt_template: str = ""
    workflow_steps: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "agent_id": self.agent_id,
            "domain": self.domain,
            "description": self.description,
            "success_count": self.success_count,
            "effectiveness": round(self.effectiveness, 2),
            "workflow_steps": self.workflow_steps,
        }


class CollectiveIntelligence:
    """
    Extracts, stores, and distributes high-performing strategies
    across the swarm. Acts as a shared knowledge base of best practices.
    """

    def __init__(self, min_successes_to_share: int = 3):
        self._strategies: dict[str, StrategyRecord] = {}
        self._shared_strategies: list[str] = []  # IDs distributed to swarm
        self.min_successes_to_share = min_successes_to_share

    def record_strategy(
        self,
        agent_id: str,
        domain: str,
        description: str,
        effectiveness: float = 1.0,
        prompt_template: str = "",
        workflow_steps: list[str] | None = None,
    ) -> StrategyRecord:
        """Record a successful strategy from an agent."""
        strategy_id = f"strat_{agent_id}_{domain}"

        if strategy_id in self._strategies:
            existing = self._strategies[strategy_id]
            existing.success_count += 1
            existing.effectiveness = existing.effectiveness * 0.7 + effectiveness * 0.3
            if prompt_template:
                existing.prompt_template = prompt_template
            if workflow_steps:
                existing.workflow_steps = workflow_steps
            logger.info(
                "strategy_updated id=%s count=%d eff=%.2f",
                strategy_id,
                existing.success_count,
                existing.effectiveness,
            )
            return existing

        record = StrategyRecord(
            strategy_id=strategy_id,
            agent_id=agent_id,
            domain=domain,
            description=description,
            effectiveness=effectiveness,
            prompt_template=prompt_template,
            workflow_steps=workflow_steps or [],
        )
        self._strategies[strategy_id] = record
        logger.info("strategy_recorded id=%s domain=%s", strategy_id, domain)
        return record

    def extract_shareable(self) -> list[StrategyRecord]:
        """
        Identify strategies worth distributing to the swarm.
        Criteria: repeated success + high effectiveness.
        """
        shareable = [
            s
            for s in self._strategies.values()
            if s.success_count >= self.min_successes_to_share
            and s.effectiveness >= 0.5
            and s.strategy_id not in self._shared_strategies
        ]
        return sorted(shareable, key=lambda s: s.effectiveness, reverse=True)

    def distribute(self) -> list[dict]:
        """
        Mark top strategies as shared and return them for swarm distribution.
        """
        candidates = self.extract_shareable()
        distributed = []
        for strategy in candidates[:5]:  # Max 5 per distribution cycle
            self._shared_strategies.append(strategy.strategy_id)
            distributed.append(strategy.to_dict())
            logger.info(
                "strategy_distributed id=%s domain=%s eff=%.2f",
                strategy.strategy_id,
                strategy.domain,
                strategy.effectiveness,
            )
        return distributed

    def get_best_for_domain(self, domain: str) -> StrategyRecord | None:
        """Get the best strategy for a specific domain."""
        domain_strategies = [s for s in self._strategies.values() if s.domain == domain]
        if not domain_strategies:
            return None
        return max(domain_strategies, key=lambda s: s.effectiveness)

    def get_all_strategies(self) -> list[dict]:
        return [s.to_dict() for s in self._strategies.values()]
