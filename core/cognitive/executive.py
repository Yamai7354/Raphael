"""
COG-206 — Swarm Executive Layer.

Strategic system that monitors swarm health, research output,
memory growth, and agent productivity. Sets research priorities,
task allocation bias, and exploration limits.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.cognitive.executive")


@dataclass
class ExecutiveDirective:
    """A strategic directive from the executive layer."""

    directive_id: str
    category: str  # research_priority, allocation_bias, exploration_limit
    description: str
    parameters: dict = field(default_factory=dict)
    issued_at: float = field(default_factory=time.time)
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "directive_id": self.directive_id,
            "category": self.category,
            "description": self.description,
            "parameters": self.parameters,
            "active": self.active,
        }


class SwarmExecutive:
    """
    Top-level strategic brain. Monitors system health and sets priorities.
    """

    def __init__(self):
        self._directives: list[ExecutiveDirective] = []
        self._research_priorities: list[str] = []
        self._allocation_bias: dict[str, float] = {}  # role -> weight
        self._exploration_limit: float = 0.5  # 0-1

    def evaluate(
        self,
        health: dict,
        research_output: dict,
        memory_growth: dict,
        productivity: dict,
    ) -> list[ExecutiveDirective]:
        """Evaluate system state and issue directives."""
        new_directives: list[ExecutiveDirective] = []

        # Low productivity → boost builders
        avg_productivity = productivity.get("average", 0.5)
        if avg_productivity < 0.3:
            d = ExecutiveDirective(
                directive_id=f"dir_{int(time.time())}",
                category="allocation_bias",
                description="Low productivity detected — increase builder allocation",
                parameters={"builder": 0.4, "researcher": 0.2},
            )
            new_directives.append(d)
            self._allocation_bias = d.parameters

        # Memory growing too fast → throttle exploration
        growth_rate = memory_growth.get("rate_per_hour", 0)
        if growth_rate > 100:
            d = ExecutiveDirective(
                directive_id=f"dir_{int(time.time())}_explore",
                category="exploration_limit",
                description=f"Memory growth too fast ({growth_rate}/hr) — throttle exploration",
                parameters={"limit": 0.2},
            )
            new_directives.append(d)
            self._exploration_limit = 0.2

        # Research output low → prioritize research domains
        active_questions = research_output.get("active_questions", 0)
        if active_questions > 20:
            d = ExecutiveDirective(
                directive_id=f"dir_{int(time.time())}_focus",
                category="research_priority",
                description="Too many open questions — focus on top priorities only",
                parameters={"max_active": 10},
            )
            new_directives.append(d)

        self._directives.extend(new_directives)
        if new_directives:
            logger.info("executive_directives_issued count=%d", len(new_directives))
        return new_directives

    def set_research_priorities(self, domains: list[str]) -> None:
        self._research_priorities = domains
        logger.info("research_priorities_set domains=%s", domains)

    def get_exploration_limit(self) -> float:
        return self._exploration_limit

    def get_allocation_bias(self) -> dict[str, float]:
        return self._allocation_bias

    def get_research_priorities(self) -> list[str]:
        return self._research_priorities

    def get_active_directives(self) -> list[dict]:
        return [d.to_dict() for d in self._directives if d.active]

    def get_status(self) -> dict:
        return {
            "active_directives": len([d for d in self._directives if d.active]),
            "research_priorities": self._research_priorities,
            "exploration_limit": self._exploration_limit,
            "allocation_bias": self._allocation_bias,
        }
