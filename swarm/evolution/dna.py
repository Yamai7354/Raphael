"""
SWARM-104 — Agent DNA Model.

Defines a configuration model representing agent behavioral traits
that can evolve over time through mutation and cloning.
"""

import logging
import random
from dataclasses import dataclass, field

logger = logging.getLogger("swarm.evolution.dna")


@dataclass
class AgentDNA:
    """
    Encapsulates the heritable behavioral traits of a swarm agent.
    Every agent carries a DNA instance that defines its operating parameters.
    Mutation adjusts these values within safe, clamped ranges.
    """

    # Core behavioral traits
    reasoning_style: str = "analytical"  # analytical, creative, systematic, exploratory
    exploration_rate: float = 0.3  # 0.0 (exploit only) → 1.0 (explore only)
    memory_strategy: str = "balanced"  # aggressive, balanced, conservative
    collaboration_style: str = "cooperative"  # cooperative, independent, competitive

    # Tool & task preferences
    tool_preferences: list[str] = field(default_factory=lambda: ["web_browser", "python_execute"])
    preferred_domains: list[str] = field(default_factory=list)

    # Performance tuning genes
    risk_tolerance: float = 0.5  # 0.0 (risk-averse) → 1.0 (risk-seeking)
    creativity_bias: float = 0.5  # 0.0 (follow patterns) → 1.0 (novel approaches)
    depth_vs_breadth: float = 0.5  # 0.0 (deep specialist) → 1.0 (broad generalist)
    response_verbosity: float = 0.5  # 0.0 (terse) → 1.0 (detailed)

    # Metadata
    generation: int = 0
    parent_id: str | None = None
    mutation_history: list[str] = field(default_factory=list)

    # Constants for clamping
    FLOAT_TRAITS: tuple[str, ...] = (
        "exploration_rate",
        "risk_tolerance",
        "creativity_bias",
        "depth_vs_breadth",
        "response_verbosity",
    )
    REASONING_STYLES: tuple[str, ...] = (
        "analytical",
        "creative",
        "systematic",
        "exploratory",
    )
    MEMORY_STRATEGIES: tuple[str, ...] = (
        "aggressive",
        "balanced",
        "conservative",
    )
    COLLABORATION_STYLES: tuple[str, ...] = (
        "cooperative",
        "independent",
        "competitive",
    )

    def clone(self, child_id: str) -> "AgentDNA":
        """Create a copy of this DNA for a child agent."""
        return AgentDNA(
            reasoning_style=self.reasoning_style,
            exploration_rate=self.exploration_rate,
            memory_strategy=self.memory_strategy,
            collaboration_style=self.collaboration_style,
            tool_preferences=list(self.tool_preferences),
            preferred_domains=list(self.preferred_domains),
            risk_tolerance=self.risk_tolerance,
            creativity_bias=self.creativity_bias,
            depth_vs_breadth=self.depth_vs_breadth,
            response_verbosity=self.response_verbosity,
            generation=self.generation + 1,
            parent_id=child_id,
            mutation_history=list(self.mutation_history),
        )

    def to_dict(self) -> dict:
        """Serialize DNA to dictionary."""
        return {
            "reasoning_style": self.reasoning_style,
            "exploration_rate": self.exploration_rate,
            "memory_strategy": self.memory_strategy,
            "collaboration_style": self.collaboration_style,
            "tool_preferences": self.tool_preferences,
            "preferred_domains": self.preferred_domains,
            "risk_tolerance": self.risk_tolerance,
            "creativity_bias": self.creativity_bias,
            "depth_vs_breadth": self.depth_vs_breadth,
            "response_verbosity": self.response_verbosity,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "mutation_history": self.mutation_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentDNA":
        """Deserialize DNA from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def random(cls) -> "AgentDNA":
        """Generate a random DNA profile."""
        return cls(
            reasoning_style=random.choice(cls.REASONING_STYLES),
            exploration_rate=round(random.uniform(0.1, 0.9), 2),
            memory_strategy=random.choice(cls.MEMORY_STRATEGIES),
            collaboration_style=random.choice(cls.COLLABORATION_STYLES),
            risk_tolerance=round(random.uniform(0.1, 0.9), 2),
            creativity_bias=round(random.uniform(0.1, 0.9), 2),
            depth_vs_breadth=round(random.uniform(0.1, 0.9), 2),
            response_verbosity=round(random.uniform(0.2, 0.8), 2),
        )
