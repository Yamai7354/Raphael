"""
COG-204 — Experiment Framework.

Infrastructure for running controlled experiments: prompt testing,
agent strategy testing, model benchmarking, architecture testing.
Results stored with metrics; winning strategies recorded.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("swarm.cognition.experiments")


class ExperimentType(str, Enum):
    PROMPT_TEST = "prompt_test"
    STRATEGY_TEST = "strategy_test"
    MODEL_BENCHMARK = "model_benchmark"
    ARCHITECTURE_TEST = "architecture_test"
    CUSTOM = "custom"


class ExperimentStatus(str, Enum):
    DESIGNED = "designed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExperimentResult:
    """Result of an experiment variant."""

    variant_id: str
    metrics: dict[str, float] = field(default_factory=dict)
    output: str = ""
    success: bool = False
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "metrics": self.metrics,
            "success": self.success,
            "duration_seconds": round(self.duration_seconds, 3),
        }


@dataclass
class Experiment:
    """A controlled experiment within the swarm."""

    experiment_id: str
    title: str
    experiment_type: ExperimentType
    hypothesis_id: str | None = None
    description: str = ""
    variants: list[str] = field(default_factory=list)  # e.g., ["prompt_A", "prompt_B"]
    success_metric: str = "accuracy"
    status: ExperimentStatus = ExperimentStatus.DESIGNED
    assigned_agent: str | None = None
    results: list[ExperimentResult] = field(default_factory=list)
    winner: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "title": self.title,
            "type": self.experiment_type.value,
            "hypothesis_id": self.hypothesis_id,
            "variants": self.variants,
            "success_metric": self.success_metric,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "winner": self.winner,
            "results": [r.to_dict() for r in self.results],
        }


class ExperimentFramework:
    """Manages the lifecycle of experiments."""

    def __init__(self):
        self._experiments: dict[str, Experiment] = {}

    def design(
        self,
        title: str,
        experiment_type: ExperimentType,
        variants: list[str],
        success_metric: str = "accuracy",
        hypothesis_id: str | None = None,
        description: str = "",
    ) -> Experiment:
        exp = Experiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            title=title,
            experiment_type=experiment_type,
            hypothesis_id=hypothesis_id,
            description=description,
            variants=variants,
            success_metric=success_metric,
        )
        self._experiments[exp.experiment_id] = exp
        logger.info(
            "experiment_designed id=%s type=%s variants=%d",
            exp.experiment_id,
            experiment_type.value,
            len(variants),
        )
        return exp

    def start(self, experiment_id: str, agent_id: str) -> None:
        exp = self._experiments.get(experiment_id)
        if exp and exp.status == ExperimentStatus.DESIGNED:
            exp.status = ExperimentStatus.RUNNING
            exp.assigned_agent = agent_id
            logger.info("experiment_started id=%s agent=%s", experiment_id, agent_id)

    def record_result(
        self,
        experiment_id: str,
        variant_id: str,
        metrics: dict[str, float],
        success: bool = True,
        duration: float = 0.0,
        output: str = "",
    ) -> None:
        exp = self._experiments.get(experiment_id)
        if exp:
            result = ExperimentResult(
                variant_id=variant_id,
                metrics=metrics,
                success=success,
                duration_seconds=duration,
                output=output,
            )
            exp.results.append(result)

    def complete(self, experiment_id: str) -> str | None:
        """Complete an experiment and determine the winner."""
        exp = self._experiments.get(experiment_id)
        if not exp or not exp.results:
            return None

        successful = [r for r in exp.results if r.success]
        if successful:
            best = max(successful, key=lambda r: r.metrics.get(exp.success_metric, 0))
            exp.winner = best.variant_id
        exp.status = ExperimentStatus.COMPLETED
        exp.completed_at = time.time()
        logger.info("experiment_completed id=%s winner=%s", experiment_id, exp.winner)
        return exp.winner

    def fail(self, experiment_id: str) -> None:
        exp = self._experiments.get(experiment_id)
        if exp:
            exp.status = ExperimentStatus.FAILED
            exp.completed_at = time.time()

    def get_running(self) -> list[Experiment]:
        return [
            e
            for e in self._experiments.values()
            if e.status == ExperimentStatus.RUNNING
        ]

    def get_designed(self) -> list[Experiment]:
        return [
            e
            for e in self._experiments.values()
            if e.status == ExperimentStatus.DESIGNED
        ]

    def get_all(self) -> list[dict]:
        return [e.to_dict() for e in self._experiments.values()]

    def get_stats(self) -> dict:
        counts: dict[str, int] = {}
        for e in self._experiments.values():
            counts[e.status.value] = counts.get(e.status.value, 0) + 1
        return {"total": len(self._experiments), "by_status": counts}
