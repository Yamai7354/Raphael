"""
COG-202 — Question Generation Engine.

Generates meaningful research questions from knowledge gaps,
performance metrics, and system weaknesses. Questions become mission seeds.
"""

import logging
import uuid
import time
from dataclasses import dataclass, field
from enum import Enum

from .knowledge_gaps import KnowledgeGap, GapSeverity

logger = logging.getLogger("swarm.cognition.questions")


class QuestionSource(str, Enum):
    KNOWLEDGE_GAP = "knowledge_gap"
    PERFORMANCE_METRIC = "performance_metric"
    SYSTEM_WEAKNESS = "system_weakness"
    AGENT_OBSERVATION = "agent_observation"
    EXECUTIVE_DIRECTIVE = "executive_directive"


@dataclass
class ResearchQuestion:
    """A generated research question for the swarm."""

    question_id: str
    text: str
    source: QuestionSource
    domain: str
    importance: float = 5.0
    gap_id: str | None = None
    generated_at: float = field(default_factory=time.time)
    assigned: bool = False
    answered: bool = False

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "text": self.text,
            "source": self.source.value,
            "domain": self.domain,
            "importance": round(self.importance, 1),
            "gap_id": self.gap_id,
            "assigned": self.assigned,
            "answered": self.answered,
        }


class QuestionEngine:
    """Generates and ranks research questions. Questions seed missions."""

    def __init__(self):
        self._questions: dict[str, ResearchQuestion] = {}

    def generate_from_gap(self, gap: KnowledgeGap) -> ResearchQuestion:
        importance_map = {
            GapSeverity.CRITICAL: 9.0,
            GapSeverity.HIGH: 7.0,
            GapSeverity.MEDIUM: 5.0,
            GapSeverity.LOW: 3.0,
        }
        q = ResearchQuestion(
            question_id=f"q_{uuid.uuid4().hex[:8]}",
            text=f"How can the swarm address: {gap.description}?",
            source=QuestionSource.KNOWLEDGE_GAP,
            domain=gap.domain,
            importance=importance_map.get(gap.severity, 5.0),
            gap_id=gap.gap_id,
        )
        self._questions[q.question_id] = q
        gap.mission_generated = True
        logger.info(
            "question_generated id=%s domain=%s importance=%.1f",
            q.question_id,
            q.domain,
            q.importance,
        )
        return q

    def generate_from_metric(
        self, domain: str, metric_name: str, current: float, target: float
    ) -> ResearchQuestion:
        delta = abs(current - target)
        direction = "improve" if current < target else "reduce"
        q = ResearchQuestion(
            question_id=f"q_{uuid.uuid4().hex[:8]}",
            text=f"How can the swarm {direction} {metric_name} in {domain}? (current={current:.2f}, target={target:.2f})",
            source=QuestionSource.PERFORMANCE_METRIC,
            domain=domain,
            importance=min(10.0, 3.0 + delta * 5.0),
        )
        self._questions[q.question_id] = q
        return q

    def generate_from_weakness(self, domain: str, weakness: str) -> ResearchQuestion:
        q = ResearchQuestion(
            question_id=f"q_{uuid.uuid4().hex[:8]}",
            text=f"What approach can fix: {weakness}?",
            source=QuestionSource.SYSTEM_WEAKNESS,
            domain=domain,
            importance=7.0,
        )
        self._questions[q.question_id] = q
        return q

    def add_custom(
        self, text: str, domain: str, importance: float = 5.0
    ) -> ResearchQuestion:
        q = ResearchQuestion(
            question_id=f"q_{uuid.uuid4().hex[:8]}",
            text=text,
            source=QuestionSource.EXECUTIVE_DIRECTIVE,
            domain=domain,
            importance=importance,
        )
        self._questions[q.question_id] = q
        return q

    def mark_assigned(self, qid: str) -> None:
        q = self._questions.get(qid)
        if q:
            q.assigned = True

    def mark_answered(self, qid: str) -> None:
        q = self._questions.get(qid)
        if q:
            q.answered = True

    def get_ranked(self) -> list[ResearchQuestion]:
        return sorted(
            [q for q in self._questions.values() if not q.answered],
            key=lambda q: q.importance,
            reverse=True,
        )

    def get_unassigned(self) -> list[ResearchQuestion]:
        return [
            q for q in self._questions.values() if not q.assigned and not q.answered
        ]

    def get_all(self) -> list[dict]:
        return [q.to_dict() for q in self.get_ranked()]
