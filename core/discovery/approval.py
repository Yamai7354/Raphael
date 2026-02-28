"""
DISC-307 — Capability Approval Threshold System.

Prevents unstable changes by enforcing improvement thresholds.
Configurable minimum scores, archives failed prototypes,
blocks low-value integrations.
"""

import logging
import time
from dataclasses import dataclass, field

from .evaluation import EvaluationResult

logger = logging.getLogger("core.discovery.approval")


@dataclass
class ApprovalDecision:
    prototype_id: str
    approved: bool
    reason: str
    improvement_score: float
    threshold: float
    decided_at: float = field(default_factory=time.time)


class ApprovalGate:
    """Enforces quality thresholds before capability integration."""

    def __init__(
        self,
        min_improvement_score: float = 0.5,
        min_success_rate: float = 0.6,
        max_error_rate: float = 0.3,
        require_positive_perf: bool = True,
    ):
        self.min_improvement_score = min_improvement_score
        self.min_success_rate = min_success_rate
        self.max_error_rate = max_error_rate
        self.require_positive_perf = require_positive_perf
        self._decisions: list[ApprovalDecision] = []
        self._archived: list[str] = []  # rejected prototype IDs

    def check(self, evaluation: EvaluationResult) -> ApprovalDecision:
        """Check if an evaluation passes the approval gate."""
        reasons: list[str] = []

        if evaluation.improvement_score < self.min_improvement_score:
            reasons.append(
                f"improvement_score {evaluation.improvement_score:.3f} < {self.min_improvement_score}"
            )

        if evaluation.task_success_rate < self.min_success_rate:
            reasons.append(
                f"success_rate {evaluation.task_success_rate:.2%} < {self.min_success_rate:.0%}"
            )

        error_rate = 1.0 - evaluation.system_efficiency
        if error_rate > self.max_error_rate:
            reasons.append(f"error_rate {error_rate:.2%} > {self.max_error_rate:.0%}")

        if self.require_positive_perf and evaluation.performance_improvement <= 0:
            reasons.append(
                f"negative performance improvement ({evaluation.performance_improvement:.3f})"
            )

        approved = len(reasons) == 0
        reason = "All thresholds met" if approved else "; ".join(reasons)

        if not approved:
            self._archived.append(evaluation.prototype_id)

        decision = ApprovalDecision(
            prototype_id=evaluation.prototype_id,
            approved=approved,
            reason=reason,
            improvement_score=evaluation.improvement_score,
            threshold=self.min_improvement_score,
        )
        self._decisions.append(decision)
        logger.info(
            "approval_decision prototype=%s approved=%s reason=%s",
            evaluation.prototype_id,
            approved,
            reason,
        )
        return decision

    def update_thresholds(
        self,
        min_improvement: float | None = None,
        min_success: float | None = None,
        max_errors: float | None = None,
    ) -> None:
        if min_improvement is not None:
            self.min_improvement_score = min_improvement
        if min_success is not None:
            self.min_success_rate = min_success
        if max_errors is not None:
            self.max_error_rate = max_errors

    def get_archived(self) -> list[str]:
        return list(self._archived)

    def get_history(self) -> list[dict]:
        return [
            {
                "prototype_id": d.prototype_id,
                "approved": d.approved,
                "reason": d.reason,
                "score": round(d.improvement_score, 3),
            }
            for d in self._decisions
        ]

    def get_stats(self) -> dict:
        approved = sum(1 for d in self._decisions if d.approved)
        return {
            "total_decisions": len(self._decisions),
            "approved": approved,
            "rejected": len(self._decisions) - approved,
            "archived": len(self._archived),
            "thresholds": {
                "min_improvement": self.min_improvement_score,
                "min_success_rate": self.min_success_rate,
                "max_error_rate": self.max_error_rate,
            },
        }
