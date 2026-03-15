"""
HabitatEvolver — Adaptive experimentation and auto-blueprint creation.

Observes metrics and experiments with habitat configurations:
  1. Varies agent counts (±1) to find optimal throughput
  2. Tests different agent type combinations
  3. Adjusts resource allocations based on cost/performance
  4. Creates new HabitatBlueprint nodes when experiments succeed
"""

import logging
import random

from director.models import BlueprintCandidate

logger = logging.getLogger("director.habitat_evolver")


class Experiment:
    """A single experiment with a habitat configuration variant."""

    __slots__ = ("blueprint_name", "variant_name", "mutations", "score", "attempts", "successes")

    def __init__(self, blueprint_name: str, variant_name: str, mutations: dict):
        self.blueprint_name = blueprint_name
        self.variant_name = variant_name
        self.mutations = mutations  # e.g. {"agent_count_delta": +1}
        self.score = 0.0
        self.attempts = 0
        self.successes = 0

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.attempts, 1)


class HabitatEvolver:
    """
    Evolves habitat blueprints through experimentation.

    Strategy:
      - After N successful runs of a blueprint, propose a variant
      - Run the variant in parallel or as next run
      - If variant outperforms original, promote it to a new blueprint
    """

    MIN_RUNS_BEFORE_EXPERIMENT = 5  # need baseline data first
    PROMOTION_THRESHOLD = 0.15  # 15% improvement required
    MAX_ACTIVE_EXPERIMENTS = 3

    def __init__(self, graph_store, metrics_tracker):
        self._graph = graph_store
        self._metrics = metrics_tracker
        self._experiments: dict[str, Experiment] = {}
        self._promoted: list[str] = []

    def should_experiment(self, blueprint_name: str) -> bool:
        """Check if a blueprint has enough baseline data for experiments."""
        stats = self._metrics.get_blueprint_stats(blueprint_name)
        has_data = stats["attempts"] >= self.MIN_RUNS_BEFORE_EXPERIMENT
        not_maxed = len(self._experiments) < self.MAX_ACTIVE_EXPERIMENTS
        no_running = blueprint_name not in self._experiments
        return has_data and not_maxed and no_running

    def propose_experiment(self, blueprint: BlueprintCandidate) -> Experiment | None:
        """Generate a mutation of the blueprint for experimentation."""
        if not self.should_experiment(blueprint.name):
            return None

        mutation_type = random.choice(
            [
                "scale_agents",
                "adjust_resources",
            ]
        )

        if mutation_type == "scale_agents":
            delta = random.choice([-1, 1])
            new_count = max(1, blueprint.recommended_agents + delta)
            mutations = {
                "mutation_type": "scale_agents",
                "agent_count_delta": delta,
                "new_agent_count": new_count,
            }
        else:  # adjust_resources
            # Scale memory/CPU requests by ±20%
            factor = random.choice([0.8, 1.2])
            mutations = {
                "mutation_type": "adjust_resources",
                "resource_factor": factor,
            }

        variant_name = f"{blueprint.name}_exp_{mutation_type}"
        experiment = Experiment(
            blueprint_name=blueprint.name,
            variant_name=variant_name,
            mutations=mutations,
        )
        self._experiments[blueprint.name] = experiment
        logger.info(f"🧪 Experiment proposed: {variant_name} — {mutations}")
        return experiment

    def record_experiment_result(self, blueprint_name: str, success: bool, score: float = 0.0):
        """Record the result of an experiment run."""
        exp = self._experiments.get(blueprint_name)
        if not exp:
            return

        exp.attempts += 1
        if success:
            exp.successes += 1
        exp.score = (exp.score * (exp.attempts - 1) + score) / exp.attempts

        logger.info(
            f"Experiment {exp.variant_name}: "
            f"attempt {exp.attempts}, "
            f"rate={exp.success_rate:.0%}, "
            f"score={exp.score:.3f}"
        )

    async def check_promotions(self) -> list[str]:
        """
        Check if any experiments should be promoted to new blueprints.
        Returns list of promoted variant names.
        """
        promoted = []
        to_remove = []

        for bp_name, exp in self._experiments.items():
            if exp.attempts < 3:
                continue  # not enough data yet

            baseline = self._metrics.get_blueprint_stats(bp_name)
            baseline_rate = baseline["success_rate"]
            improvement = exp.success_rate - baseline_rate

            if improvement >= self.PROMOTION_THRESHOLD:
                # Promote: create a new blueprint in the graph
                await self._create_evolved_blueprint(exp)
                promoted.append(exp.variant_name)
                to_remove.append(bp_name)
                logger.info(f"🎉 Promoted {exp.variant_name}! +{improvement:.0%} vs baseline")
            elif exp.attempts >= 5 and improvement < 0:
                # Failed experiment — remove it
                to_remove.append(bp_name)
                logger.info(f"❌ Dropped experiment {exp.variant_name}")

        for bp_name in to_remove:
            self._experiments.pop(bp_name, None)

        self._promoted.extend(promoted)
        return promoted

    async def _create_evolved_blueprint(self, experiment: Experiment):
        """Create a new HabitatBlueprint node from a successful experiment."""
        mutations = experiment.mutations

        if mutations["mutation_type"] == "scale_agents":
            agent_count = mutations["new_agent_count"]
        else:
            agent_count = None  # keep original

        # Create the evolved blueprint in Neo4j
        query = """
        MATCH (original:HabitatBlueprint {name: $original_name})
        CREATE (evolved:HabitatBlueprint {
            name: $variant_name,
            helmChart: original.helmChart,
            description: "Evolved from " + original.name + " via " + $mutation_type,
            memory_type: "infrastructure",
            promotion_score: 0.8,
            evolved_from: $original_name,
            mutations: $mutations_json
        })
        // Copy capability requirements
        WITH original, evolved
        MATCH (original)-[:REQUIRES_CAPABILITY]->(c:Capability)
        CREATE (evolved)-[:REQUIRES_CAPABILITY]->(c)
        // Copy service dependencies
        WITH original, evolved
        MATCH (original)-[:USES_SERVICE]->(s:Service)
        CREATE (evolved)-[:USES_SERVICE]->(s)
        RETURN evolved.name AS name
        """
        import json

        await self._graph.execute_cypher(
            query,
            {
                "original_name": experiment.blueprint_name,
                "variant_name": experiment.variant_name,
                "mutation_type": mutations["mutation_type"],
                "mutations_json": json.dumps(mutations),
            },
        )

        # Update agent count if that was the mutation
        if agent_count is not None:
            await self._graph.execute_cypher(
                """
                MATCH (original:HabitatBlueprint {name: $original})-[r:SPAWNS_AGENT]->(a:AgentType)
                MATCH (evolved:HabitatBlueprint {name: $variant})
                CREATE (evolved)-[:SPAWNS_AGENT {
                    count: CASE WHEN r.count > 1
                        THEN $new_count
                        ELSE r.count END,
                    role: r.role
                }]->(a)
                """,
                {
                    "original": experiment.blueprint_name,
                    "variant": experiment.variant_name,
                    "new_count": agent_count,
                },
            )

    @property
    def active_experiments(self) -> int:
        return len(self._experiments)

    @property
    def total_promoted(self) -> int:
        return len(self._promoted)
