"""
SWARM-111 — Mutation Strategy Engine.

Adjusts agent behavior during cloning by mutating DNA traits
within defined safe constraints.
"""

import logging
import random
from dataclasses import dataclass

from .dna import AgentDNA

logger = logging.getLogger("swarm.evolution.mutation")


@dataclass
class MutationConfig:
    """Constraints for mutation operations."""

    mutation_rate: float = 0.3  # Probability of each trait mutating
    float_mutation_range: float = 0.15  # Max delta for float traits
    min_float: float = 0.05
    max_float: float = 0.95


class MutationEngine:
    """
    Applies controlled mutations to AgentDNA during cloning.
    Mutations can modify:
    - Reasoning approaches
    - Exploration thresholds
    - Collaboration patterns
    - Tool usage strategies
    - Memory strategies

    All mutations remain within defined safe constraints.
    """

    def __init__(self, config: MutationConfig | None = None):
        self.config = config or MutationConfig()

    def mutate(self, dna: AgentDNA, mutation_id: str = "") -> AgentDNA:
        """
        Apply random mutations to a DNA instance.
        Returns the mutated DNA (modifies in place and returns).
        """
        mutations_applied: list[str] = []

        # Mutate float traits
        for trait_name in dna.FLOAT_TRAITS:
            if random.random() < self.config.mutation_rate:
                old_val = getattr(dna, trait_name)
                delta = random.uniform(
                    -self.config.float_mutation_range,
                    self.config.float_mutation_range,
                )
                new_val = round(
                    max(self.config.min_float, min(self.config.max_float, old_val + delta)),
                    3,
                )
                setattr(dna, trait_name, new_val)
                mutations_applied.append(f"{trait_name}: {old_val:.3f} -> {new_val:.3f}")

        # Mutate reasoning style
        if random.random() < self.config.mutation_rate:
            old = dna.reasoning_style
            dna.reasoning_style = random.choice(dna.REASONING_STYLES)
            if dna.reasoning_style != old:
                mutations_applied.append(f"reasoning_style: {old} -> {dna.reasoning_style}")

        # Mutate memory strategy
        if random.random() < self.config.mutation_rate:
            old = dna.memory_strategy
            dna.memory_strategy = random.choice(dna.MEMORY_STRATEGIES)
            if dna.memory_strategy != old:
                mutations_applied.append(f"memory_strategy: {old} -> {dna.memory_strategy}")

        # Mutate collaboration style
        if random.random() < self.config.mutation_rate:
            old = dna.collaboration_style
            dna.collaboration_style = random.choice(dna.COLLABORATION_STYLES)
            if dna.collaboration_style != old:
                mutations_applied.append(f"collaboration_style: {old} -> {dna.collaboration_style}")

        # Record mutation history
        if mutations_applied:
            label = mutation_id or f"gen_{dna.generation}"
            dna.mutation_history.append(f"{label}: {', '.join(mutations_applied)}")
            logger.info(
                "mutation_applied count=%d details=%s",
                len(mutations_applied),
                mutations_applied,
            )
        else:
            logger.debug("mutation_skipped — no traits were selected for mutation")

        return dna

    def crossover(self, parent_a: AgentDNA, parent_b: AgentDNA) -> AgentDNA:
        """
        Combine traits from two parent DNAs to produce offspring.
        Uses uniform crossover — each trait randomly selected from a parent.
        """
        child = AgentDNA(
            reasoning_style=random.choice([parent_a.reasoning_style, parent_b.reasoning_style]),
            exploration_rate=random.choice([parent_a.exploration_rate, parent_b.exploration_rate]),
            memory_strategy=random.choice([parent_a.memory_strategy, parent_b.memory_strategy]),
            collaboration_style=random.choice(
                [parent_a.collaboration_style, parent_b.collaboration_style]
            ),
            tool_preferences=list(set(parent_a.tool_preferences + parent_b.tool_preferences)),
            preferred_domains=list(set(parent_a.preferred_domains + parent_b.preferred_domains)),
            risk_tolerance=random.choice([parent_a.risk_tolerance, parent_b.risk_tolerance]),
            creativity_bias=random.choice([parent_a.creativity_bias, parent_b.creativity_bias]),
            depth_vs_breadth=random.choice([parent_a.depth_vs_breadth, parent_b.depth_vs_breadth]),
            response_verbosity=random.choice(
                [parent_a.response_verbosity, parent_b.response_verbosity]
            ),
            generation=max(parent_a.generation, parent_b.generation) + 1,
            mutation_history=["crossover"],
        )
        return child
