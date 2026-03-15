"""
HabitatSelector — Decides which habitat blueprint to deploy for a task.

Responsibilities:
  - Take ranked blueprint candidates from GraphReasoner
  - Apply selection heuristics (capability coverage, resource fit, historical performance)
  - Return the best blueprint for deployment
"""

import logging

from director.models import BlueprintCandidate
from director.task_manager import SwarmTask

logger = logging.getLogger("director.habitat_selector")


class HabitatSelector:
    """Selects the optimal habitat blueprint for a given task."""

    def __init__(self):
        self._performance_cache: dict[str, dict] = {}

    def select(
        self,
        task: SwarmTask,
        candidates: list[BlueprintCandidate],
    ) -> BlueprintCandidate | None:
        """
        Select the best habitat blueprint for a task.

        Scoring:
          1. Capability coverage  (how many required caps does the blueprint match?)
          2. Resource efficiency   (prefer smaller habitats if they cover all caps)
          3. Historical performance (if we've seen this blueprint solve similar tasks)
        """
        if not candidates:
            logger.warning(f"No candidates available for task {task.id}")
            return None

        required = set(task.required_capabilities)
        scored: list[tuple[float, BlueprintCandidate]] = []

        for candidate in candidates:
            provided = set(candidate.capabilities)
            coverage = len(required & provided) / max(len(required), 1)

            # Prefer smaller habitats that still cover requirements
            efficiency = 1.0 / max(candidate.recommended_agents, 1)

            # Check historical performance
            perf = self._performance_cache.get(candidate.name, {})
            success_rate = perf.get("success_rate", 0.5)

            # Weighted score
            score = (coverage * 0.6) + (success_rate * 0.3) + (efficiency * 0.1)
            scored.append((score, candidate))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]

        logger.info(
            f"Selected '{best.name}' for task {task.id} "
            f"(score={best_score:.2f}, coverage={len(set(task.required_capabilities) & set(best.capabilities))}/{len(task.required_capabilities)})"
        )
        return best

    def update_performance(self, blueprint_name: str, success: bool, duration_s: float = 0.0):
        """Update performance cache for a blueprint after a task completes."""
        perf = self._performance_cache.setdefault(
            blueprint_name, {"attempts": 0, "successes": 0, "total_duration": 0.0}
        )
        perf["attempts"] += 1
        if success:
            perf["successes"] += 1
        perf["total_duration"] += duration_s
        perf["success_rate"] = perf["successes"] / max(perf["attempts"], 1)
        perf["avg_duration"] = perf["total_duration"] / max(perf["attempts"], 1)
