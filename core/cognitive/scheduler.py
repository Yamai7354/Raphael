"""
COG-208 — Cognitive Loop Scheduler.

Runs periodic cognition cycles: knowledge gap analysis,
question generation, hypothesis creation, experiment planning,
and executive review.
"""

import logging
import time
from dataclasses import dataclass, field

from .knowledge_gaps import KnowledgeGapDetector
from .questions import QuestionEngine
from .hypotheses import HypothesisSystem
from .experiments import ExperimentFramework
from .executive import SwarmExecutive
from .curiosity_throttle import CuriosityThrottle

logger = logging.getLogger("core.cognitive.scheduler")


@dataclass
class CycleResult:
    """Summary of a single cognitive loop cycle."""

    cycle_id: int
    gaps_detected: int = 0
    questions_generated: int = 0
    hypotheses_created: int = 0
    experiments_designed: int = 0
    directives_issued: int = 0
    duration_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "gaps_detected": self.gaps_detected,
            "questions_generated": self.questions_generated,
            "hypotheses_created": self.hypotheses_created,
            "experiments_designed": self.experiments_designed,
            "directives_issued": self.directives_issued,
            "duration_seconds": round(self.duration_seconds, 3),
        }


class CognitiveLoopScheduler:
    """
    Orchestrates the full cognition cycle:
    1. Knowledge gap analysis
    2. Question generation
    3. Hypothesis creation
    4. Experiment planning
    5. Executive review
    """

    def __init__(
        self,
        gap_detector: KnowledgeGapDetector | None = None,
        question_engine: QuestionEngine | None = None,
        hypothesis_system: HypothesisSystem | None = None,
        experiment_framework: ExperimentFramework | None = None,
        executive: SwarmExecutive | None = None,
        curiosity: CuriosityThrottle | None = None,
    ):
        self.gaps = gap_detector or KnowledgeGapDetector()
        self.questions = question_engine or QuestionEngine()
        self.hypotheses = hypothesis_system or HypothesisSystem()
        self.experiments = experiment_framework or ExperimentFramework()
        self.executive = executive or SwarmExecutive()
        self.curiosity = curiosity or CuriosityThrottle()
        self._cycle_count = 0
        self._history: list[CycleResult] = []

    def run_cycle(
        self,
        domain_densities: dict[str, float] | None = None,
        system_health: dict | None = None,
    ) -> CycleResult:
        """Execute one full cognition cycle."""
        self._cycle_count += 1
        start = time.time()
        result = CycleResult(cycle_id=self._cycle_count)

        logger.info("=== Cognitive Cycle %d START ===", self._cycle_count)

        # 1. Knowledge gap analysis
        new_gaps = self.gaps.run_scan(domain_densities)
        result.gaps_detected = len(new_gaps)

        # 2. Question generation (throttled)
        for gap in new_gaps:
            if self.curiosity.can_generate_question():
                self.questions.generate_from_gap(gap)
                self.curiosity.record_question()
                result.questions_generated += 1

        # 3. Hypothesis Creation (from top unassigned questions)
        for q in self.questions.get_unassigned()[:3]:
            h = self.hypotheses.propose(
                statement=f"Hypothesis for: {q.text}",
                domain=q.domain,
                proposing_agent="cognitive_scheduler",
                expected_outcome="Improved knowledge coverage",
                experiment_plan="Run targeted research and evaluation",
                question_id=q.question_id,
                gap_id=q.gap_id,
            )
            self.questions.mark_assigned(q.question_id)
            result.hypotheses_created += 1

        # 4. Experiment planning (from testable hypotheses)
        from .experiments import ExperimentType

        for h in self.hypotheses.get_testable()[:2]:
            self.experiments.design(
                title=f"Test: {h.statement[:60]}",
                experiment_type=ExperimentType.STRATEGY_TEST,
                variants=["approach_a", "approach_b"],
                hypothesis_id=h.hypothesis_id,
            )
            self.hypotheses.start_testing(h.hypothesis_id)
            result.experiments_designed += 1

        # 5. Executive review
        health = system_health or {}
        directives = self.executive.evaluate(
            health=health,
            research_output={"active_questions": len(self.questions.get_ranked())},
            memory_growth=health.get("memory", {}),
            productivity=health.get("productivity", {}),
        )
        result.directives_issued = len(directives)

        result.duration_seconds = time.time() - start
        self._history.append(result)
        logger.info(
            "=== Cognitive Cycle %d END (%.3fs) ===",
            self._cycle_count,
            result.duration_seconds,
        )
        return result

    def get_history(self) -> list[dict]:
        return [r.to_dict() for r in self._history]

    def get_status(self) -> dict:
        return {
            "total_cycles": self._cycle_count,
            "gap_report": self.gaps.get_report(),
            "active_questions": len(self.questions.get_ranked()),
            "hypothesis_stats": self.hypotheses.get_stats(),
            "experiment_stats": self.experiments.get_stats(),
            "curiosity": self.curiosity.get_status(),
            "executive": self.executive.get_status(),
        }
