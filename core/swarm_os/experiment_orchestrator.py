"""
SOS-508 — Experiment Orchestration Engine.

Manages swarm experiments: task assignment, metric monitoring,
prototype integration, sandbox testing, and safe rollback.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.swarm_os.experiment_orchestrator")


class ExperimentPhase(str, Enum):
    DESIGN = "design"
    SANDBOX = "sandbox"
    RUNNING = "running"
    EVALUATING = "evaluating"
    INTEGRATING = "integrating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Experiment:
    """A swarm experiment."""

    exp_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:8]}")
    title: str = ""
    hypothesis: str = ""
    assigned_agents: list[str] = field(default_factory=list)
    phase: ExperimentPhase = ExperimentPhase.DESIGN
    metrics: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0
    rollback_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "exp_id": self.exp_id,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "phase": self.phase.value,
            "agents": self.assigned_agents,
            "metrics": self.metrics,
        }


class ExperimentOrchestrator:
    """Manages the full lifecycle of swarm experiments."""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._experiments: dict[str, Experiment] = {}

    def create(self, title: str, hypothesis: str, agents: list[str] | None = None) -> Experiment:
        exp = Experiment(title=title, hypothesis=hypothesis, assigned_agents=agents or [])
        self._experiments[exp.exp_id] = exp
        logger.info("experiment_created id=%s title=%s", exp.exp_id, title)
        return exp

    def can_start(self) -> bool:
        running = sum(
            1
            for e in self._experiments.values()
            if e.phase in (ExperimentPhase.SANDBOX, ExperimentPhase.RUNNING)
        )
        return running < self.max_concurrent

    def advance(self, exp_id: str) -> ExperimentPhase | None:
        """Advance experiment to next phase."""
        exp = self._experiments.get(exp_id)
        if not exp:
            return None

        phase_order = [
            ExperimentPhase.DESIGN,
            ExperimentPhase.SANDBOX,
            ExperimentPhase.RUNNING,
            ExperimentPhase.EVALUATING,
            ExperimentPhase.INTEGRATING,
            ExperimentPhase.COMPLETED,
        ]
        try:
            idx = phase_order.index(exp.phase)
            if idx + 1 < len(phase_order):
                exp.phase = phase_order[idx + 1]
                if exp.phase == ExperimentPhase.COMPLETED:
                    exp.completed_at = time.time()
                logger.info("experiment_advanced id=%s phase=%s", exp_id, exp.phase.value)
                return exp.phase
        except ValueError:
            pass
        return exp.phase

    def record_metrics(self, exp_id: str, metrics: dict) -> None:
        exp = self._experiments.get(exp_id)
        if exp:
            exp.metrics.update(metrics)

    def fail(self, exp_id: str, reason: str = "") -> None:
        exp = self._experiments.get(exp_id)
        if exp:
            exp.phase = ExperimentPhase.FAILED
            exp.metrics["failure_reason"] = reason
            exp.completed_at = time.time()

    def rollback(self, exp_id: str) -> None:
        exp = self._experiments.get(exp_id)
        if exp:
            exp.phase = ExperimentPhase.ROLLED_BACK
            exp.completed_at = time.time()
            logger.warning("experiment_rolled_back id=%s", exp_id)

    def get_running(self) -> list[Experiment]:
        return [
            e
            for e in self._experiments.values()
            if e.phase in (ExperimentPhase.SANDBOX, ExperimentPhase.RUNNING)
        ]

    def get_all(self, limit: int = 20) -> list[dict]:
        exps = sorted(self._experiments.values(), key=lambda e: e.created_at, reverse=True)
        return [e.to_dict() for e in exps[:limit]]

    def get_stats(self) -> dict:
        by_phase: dict[str, int] = {}
        for e in self._experiments.values():
            by_phase[e.phase.value] = by_phase.get(e.phase.value, 0) + 1
        return {"total": len(self._experiments), "by_phase": by_phase}
