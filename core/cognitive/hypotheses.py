"""
COG-203 — Hypothesis Generation System.

Agents propose hypotheses with expected outcomes, experiment plans,
and success metrics. Hypotheses link to knowledge gaps and follow
a propose → test → confirm/reject lifecycle.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("swarm.cognition.hypotheses")


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


@dataclass
class Hypothesis:
    """A testable hypothesis proposed by the swarm."""

    hypothesis_id: str
    statement: str
    domain: str
    proposing_agent: str
    expected_outcome: str
    experiment_plan: str
    success_metrics: list[str] = field(default_factory=list)
    gap_id: str | None = None
    question_id: str | None = None
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.5
    result_data: dict | None = None
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "domain": self.domain,
            "proposing_agent": self.proposing_agent,
            "expected_outcome": self.expected_outcome,
            "experiment_plan": self.experiment_plan,
            "success_metrics": self.success_metrics,
            "status": self.status.value,
            "confidence": round(self.confidence, 2),
            "gap_id": self.gap_id,
            "question_id": self.question_id,
        }


class HypothesisSystem:
    """Manages hypothesis lifecycle: propose → test → confirm/reject."""

    def __init__(self):
        self._hypotheses: dict[str, Hypothesis] = {}

    def propose(
        self,
        statement: str,
        domain: str,
        proposing_agent: str,
        expected_outcome: str,
        experiment_plan: str,
        success_metrics: list[str] | None = None,
        gap_id: str | None = None,
        question_id: str | None = None,
        confidence: float = 0.5,
    ) -> Hypothesis:
        h = Hypothesis(
            hypothesis_id=f"hyp_{uuid.uuid4().hex[:8]}",
            statement=statement,
            domain=domain,
            proposing_agent=proposing_agent,
            expected_outcome=expected_outcome,
            experiment_plan=experiment_plan,
            success_metrics=success_metrics or [],
            gap_id=gap_id,
            question_id=question_id,
            confidence=confidence,
        )
        self._hypotheses[h.hypothesis_id] = h
        logger.info(
            "hypothesis_proposed id=%s domain=%s agent=%s",
            h.hypothesis_id,
            domain,
            proposing_agent,
        )
        return h

    def start_testing(self, hid: str) -> None:
        h = self._hypotheses.get(hid)
        if h and h.status == HypothesisStatus.PROPOSED:
            h.status = HypothesisStatus.TESTING

    def confirm(self, hid: str, result_data: dict | None = None) -> None:
        h = self._hypotheses.get(hid)
        if h:
            h.status = HypothesisStatus.CONFIRMED
            h.result_data = result_data
            h.resolved_at = time.time()

    def reject(self, hid: str, result_data: dict | None = None) -> None:
        h = self._hypotheses.get(hid)
        if h:
            h.status = HypothesisStatus.REJECTED
            h.result_data = result_data
            h.resolved_at = time.time()

    def mark_inconclusive(self, hid: str) -> None:
        h = self._hypotheses.get(hid)
        if h:
            h.status = HypothesisStatus.INCONCLUSIVE
            h.resolved_at = time.time()

    def get_testable(self) -> list[Hypothesis]:
        return [
            h
            for h in self._hypotheses.values()
            if h.status == HypothesisStatus.PROPOSED
        ]

    def get_active(self) -> list[Hypothesis]:
        return [
            h for h in self._hypotheses.values() if h.status == HypothesisStatus.TESTING
        ]

    def get_for_gap(self, gap_id: str) -> list[Hypothesis]:
        return [h for h in self._hypotheses.values() if h.gap_id == gap_id]

    def get_all(self) -> list[dict]:
        return [h.to_dict() for h in self._hypotheses.values()]

    def get_stats(self) -> dict:
        counts: dict[str, int] = {}
        for h in self._hypotheses.values():
            counts[h.status.value] = counts.get(h.status.value, 0) + 1
        return {"total": len(self._hypotheses), "by_status": counts}
