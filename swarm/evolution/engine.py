"""
SWARM-103 — Evolution Cycle Engine.

Automated cycle that evaluates and evolves the swarm population.
- Scores all agents
- Retires bottom performers
- Clones top performers
- Applies mutations to clones
- Rebalances role distribution
"""

import logging
import time
import uuid

from .dna import AgentDNA
from .fitness import FitnessScorer
from .mutation import MutationEngine
from .population import PopulationController
from .reputation import ReputationTracker

logger = logging.getLogger("swarm.evolution.engine")


class EvolutionCycleEngine:
    """
    Orchestrates periodic swarm evolution cycles:
    1. Evaluate all agent fitness
    2. Retire bottom N agents
    3. Clone top N agents with mutations
    4. Rebalance role distribution
    """

    def __init__(
        self,
        fitness: FitnessScorer | None = None,
        reputation: ReputationTracker | None = None,
        population: PopulationController | None = None,
        mutation_engine: MutationEngine | None = None,
        retire_count: int = 3,
        clone_count: int = 2,
    ):
        self.fitness = fitness or FitnessScorer()
        self.reputation = reputation or ReputationTracker()
        self.population = population or PopulationController(fitness_scorer=self.fitness)
        self.mutation = mutation_engine or MutationEngine()
        self.retire_count = retire_count
        self.clone_count = clone_count

        # Cycle tracking
        self._cycle_count: int = 0
        self._last_cycle_time: float = 0.0
        self._cycle_history: list[dict] = []

        # Agent DNA registry
        self._agent_dna: dict[str, AgentDNA] = {}

    def register_agent_dna(self, agent_id: str, dna: AgentDNA | None = None) -> None:
        """Register DNA for an agent (creates random if none provided)."""
        self._agent_dna[agent_id] = dna or AgentDNA.random()
        self.population.register_agent(agent_id)

    def get_agent_dna(self, agent_id: str) -> AgentDNA | None:
        return self._agent_dna.get(agent_id)

    def run_cycle(self) -> dict:
        """
        Execute one full evolution cycle.
        Returns a summary of actions taken.
        """
        self._cycle_count += 1
        cycle_start = time.time()
        summary: dict = {
            "cycle": self._cycle_count,
            "timestamp": cycle_start,
            "retired": [],
            "cloned": [],
            "mutations": [],
        }

        logger.info("=== Evolution Cycle %d START ===", self._cycle_count)

        # --- Phase 1: Evaluate ---
        ranking = self.fitness.get_ranking()
        if len(ranking) < 2:
            logger.info("evolution_skipped — not enough agents for evolution")
            return summary

        # --- Phase 2: Retire bottom performers ---
        bottom = self.fitness.get_bottom_n(self.retire_count)
        for score in bottom:
            agent_id = score.agent_id
            self.population.retire_agent(agent_id)
            self.reputation.remove_agent(agent_id)
            self._agent_dna.pop(agent_id, None)
            summary["retired"].append(agent_id)
            logger.info(
                "evolution_retired agent=%s fitness=%.2f",
                agent_id,
                score.composite_score,
            )

        # --- Phase 3: Clone top performers with mutation ---
        top = self.fitness.get_top_n(self.clone_count)
        for score in top:
            parent_id = score.agent_id
            parent_dna = self._agent_dna.get(parent_id)
            if not parent_dna:
                continue

            child_id = f"evolved_{uuid.uuid4().hex[:8]}"
            child_dna = parent_dna.clone(child_id)

            # Apply mutation
            self.mutation.mutate(child_dna, mutation_id=f"cycle_{self._cycle_count}")

            # Register child
            if self.population.can_spawn():
                self._agent_dna[child_id] = child_dna
                self.population.register_agent(child_id)
                summary["cloned"].append(
                    {
                        "child_id": child_id,
                        "parent_id": parent_id,
                        "generation": child_dna.generation,
                    }
                )
                logger.info(
                    "evolution_cloned parent=%s child=%s gen=%d",
                    parent_id,
                    child_id,
                    child_dna.generation,
                )

        # --- Phase 4: Record cycle ---
        cycle_duration = time.time() - cycle_start
        summary["duration_seconds"] = round(cycle_duration, 3)
        self._last_cycle_time = cycle_start
        self._cycle_history.append(summary)

        logger.info(
            "=== Evolution Cycle %d END — retired=%d cloned=%d duration=%.3fs ===",
            self._cycle_count,
            len(summary["retired"]),
            len(summary["cloned"]),
            cycle_duration,
        )

        return summary

    def get_cycle_history(self) -> list[dict]:
        return self._cycle_history

    def get_status(self) -> dict:
        return {
            "total_cycles": self._cycle_count,
            "last_cycle_time": self._last_cycle_time,
            "population": self.population.get_metrics(),
            "agent_count": len(self._agent_dna),
        }
