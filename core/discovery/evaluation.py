"""
DISC-305 — Experiment Evaluation System.

Evaluates prototype performance: performance improvement,
task success rate, system efficiency, collaboration effectiveness.
Produces pass/fail decision and improvement score.
"""

import logging
from dataclasses import dataclass, field

from .sandbox import SandboxResult

logger = logging.getLogger("core.discovery.evaluation")


@dataclass
class EvaluationResult:
    """Result of evaluating a prototype experiment."""

    prototype_id: str = ""
    sandbox_result_id: str = ""
    passed: bool = False
    improvement_score: float = 0.0
    performance_improvement: float = 0.0
    task_success_rate: float = 0.0
    system_efficiency: float = 0.0
    collaboration_score: float = 0.0
    verdict: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "prototype_id": self.prototype_id,
            "passed": self.passed,
            "improvement_score": round(self.improvement_score, 3),
            "verdict": self.verdict,
            "metrics": {
                "performance_improvement": round(self.performance_improvement, 3),
                "task_success_rate": round(self.task_success_rate, 3),
                "system_efficiency": round(self.system_efficiency, 3),
                "collaboration_score": round(self.collaboration_score, 3),
            },
        }


class ExperimentEvaluator:
    """Evaluates sandbox results and scores prototypes."""

    def __init__(
        self,
        min_success_rate: float = 0.6,
        min_improvement_score: float = 0.5,
        weights: dict | None = None,
    ):
        self.min_success_rate = min_success_rate
        self.min_improvement_score = min_improvement_score
        self.weights = weights or {
            "performance": 0.3,
            "success_rate": 0.3,
            "efficiency": 0.2,
            "collaboration": 0.2,
        }
        self._evaluations: list[EvaluationResult] = []

    def evaluate(
        self,
        sandbox_result: SandboxResult,
        baseline_success_rate: float = 0.5,
        baseline_execution_ms: float = 3000,
    ) -> EvaluationResult:
        """Evaluate a sandbox result against baselines."""

        # Task success rate
        success_rate = sandbox_result.success_rate

        # Performance improvement (lower execution time = better)
        if baseline_execution_ms > 0 and sandbox_result.avg_execution_ms > 0:
            perf_improvement = 1.0 - (sandbox_result.avg_execution_ms / baseline_execution_ms)
            perf_improvement = max(-1.0, min(1.0, perf_improvement))
        else:
            perf_improvement = 0.0

        # System efficiency (fewer errors, lower resource usage)
        error_rate = len(sandbox_result.errors) / max(1, sandbox_result.tasks_attempted)
        efficiency = max(0.0, 1.0 - error_rate)

        # Collaboration (how well it integrates — based on variety of tasks)
        collab = min(1.0, sandbox_result.tasks_attempted / 10)

        # Weighted improvement score
        w = self.weights
        improvement_score = (
            w["performance"] * max(0, perf_improvement)
            + w["success_rate"] * success_rate
            + w["efficiency"] * efficiency
            + w["collaboration"] * collab
        )

        # Pass/fail decision
        passed = (
            success_rate >= self.min_success_rate
            and improvement_score >= self.min_improvement_score
            and len(sandbox_result.errors) < sandbox_result.tasks_attempted
        )

        verdict = "APPROVED" if passed else "REJECTED"
        if not passed:
            reasons = []
            if success_rate < self.min_success_rate:
                reasons.append(f"low success rate ({success_rate:.0%})")
            if improvement_score < self.min_improvement_score:
                reasons.append(f"low improvement score ({improvement_score:.3f})")
            if len(sandbox_result.errors) >= sandbox_result.tasks_attempted:
                reasons.append("too many errors")
            verdict = f"REJECTED: {', '.join(reasons)}"

        result = EvaluationResult(
            prototype_id=sandbox_result.prototype_id,
            sandbox_result_id=sandbox_result.result_id,
            passed=passed,
            improvement_score=improvement_score,
            performance_improvement=perf_improvement,
            task_success_rate=success_rate,
            system_efficiency=efficiency,
            collaboration_score=collab,
            verdict=verdict,
            details={
                "baseline_success_rate": baseline_success_rate,
                "baseline_execution_ms": baseline_execution_ms,
                "tasks_attempted": sandbox_result.tasks_attempted,
            },
        )
        self._evaluations.append(result)
        logger.info(
            "evaluation_complete prototype=%s passed=%s score=%.3f",
            sandbox_result.prototype_id,
            passed,
            improvement_score,
        )
        return result

    def get_history(self) -> list[dict]:
        return [e.to_dict() for e in self._evaluations]

    def get_stats(self) -> dict:
        passed = sum(1 for e in self._evaluations if e.passed)
        return {
            "total_evaluations": len(self._evaluations),
            "passed": passed,
            "failed": len(self._evaluations) - passed,
            "avg_improvement": round(
                sum(e.improvement_score for e in self._evaluations)
                / max(1, len(self._evaluations)),
                3,
            ),
        }
