"""
Knowledge Promotion Pipeline.

Manages the lifecycle: Research → Candidate → Embedding → Evaluation → Verified → Used.
Prevents the "Research → Node Explosion" problem by gating each transition.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.knowledge_quality.promotion_pipeline")


class PromotionStage(str, Enum):
    CANDIDATE = "candidate"
    EMBEDDED = "embedded"
    EVALUATED = "evaluated"
    VERIFIED = "verified"
    ACTIVE = "active"  # used by tasks
    DEPRECATED = "deprecated"
    MERGED = "merged"
    ORPHANED = "orphaned"


VALID_PROMOTIONS = {
    PromotionStage.CANDIDATE: {PromotionStage.EMBEDDED, PromotionStage.DEPRECATED},
    PromotionStage.EMBEDDED: {PromotionStage.EVALUATED, PromotionStage.DEPRECATED},
    PromotionStage.EVALUATED: {
        PromotionStage.VERIFIED,
        PromotionStage.CANDIDATE,
        PromotionStage.DEPRECATED,
    },
    PromotionStage.VERIFIED: {PromotionStage.ACTIVE, PromotionStage.DEPRECATED},
    PromotionStage.ACTIVE: {PromotionStage.DEPRECATED, PromotionStage.ORPHANED},
    PromotionStage.DEPRECATED: {PromotionStage.CANDIDATE},  # can be rehabilitated
    PromotionStage.ORPHANED: {PromotionStage.ACTIVE, PromotionStage.DEPRECATED},
    PromotionStage.MERGED: set(),  # terminal
}


@dataclass
class PromotionEvent:
    """Record of a knowledge promotion/demotion."""

    node_id: str = ""
    from_stage: str = ""
    to_stage: str = ""
    reason: str = ""
    promoted_by: str = ""  # agent or system
    timestamp: float = field(default_factory=time.time)


@dataclass
class PromotionCriteria:
    """Criteria for automatic stage promotion."""

    min_quality_for_embedding: float = 0.2
    min_quality_for_evaluation: float = 0.4
    min_quality_for_verification: float = 0.7
    min_confidence_for_verification: float = 0.6
    min_validators_for_verification: int = 2
    max_age_hours_for_orphan: float = 168  # 7 days unused → orphan


class PromotionPipeline:
    """Manages knowledge through the promotion lifecycle."""

    def __init__(self, criteria: PromotionCriteria | None = None):
        self.criteria = criteria or PromotionCriteria()
        self._stages: dict[str, PromotionStage] = {}
        self._history: list[PromotionEvent] = []
        self._last_used: dict[str, float] = {}

    def register(self, node_id: str, stage: PromotionStage = PromotionStage.CANDIDATE) -> None:
        self._stages[node_id] = stage
        self._last_used[node_id] = time.time()

    def promote(
        self, node_id: str, to_stage: PromotionStage, reason: str = "", promoted_by: str = "system"
    ) -> bool:
        """Attempt to promote knowledge to a new stage."""
        current = self._stages.get(node_id, PromotionStage.CANDIDATE)
        valid = VALID_PROMOTIONS.get(current, set())

        if to_stage not in valid:
            logger.warning("invalid_promotion %s: %s → %s", node_id, current.value, to_stage.value)
            return False

        event = PromotionEvent(
            node_id=node_id,
            from_stage=current.value,
            to_stage=to_stage.value,
            reason=reason,
            promoted_by=promoted_by,
        )
        self._stages[node_id] = to_stage
        self._history.append(event)
        logger.info("promoted %s: %s → %s (%s)", node_id, current.value, to_stage.value, reason)
        return True

    def auto_evaluate(
        self,
        node_id: str,
        quality_score: float,
        confidence_score: float = 0.0,
        validator_count: int = 0,
    ) -> PromotionStage:
        """Automatically determine and apply the appropriate promotion."""
        current = self._stages.get(node_id, PromotionStage.CANDIDATE)

        if current == PromotionStage.CANDIDATE:
            if quality_score >= self.criteria.min_quality_for_embedding:
                self.promote(node_id, PromotionStage.EMBEDDED, "quality_threshold_met")
                return PromotionStage.EMBEDDED

        elif current == PromotionStage.EMBEDDED:
            if quality_score >= self.criteria.min_quality_for_evaluation:
                self.promote(node_id, PromotionStage.EVALUATED, "evaluation_threshold_met")
                return PromotionStage.EVALUATED

        elif current == PromotionStage.EVALUATED:
            if (
                quality_score >= self.criteria.min_quality_for_verification
                and confidence_score >= self.criteria.min_confidence_for_verification
                and validator_count >= self.criteria.min_validators_for_verification
            ):
                self.promote(node_id, PromotionStage.VERIFIED, "verification_criteria_met")
                return PromotionStage.VERIFIED

        # Demotion check
        if quality_score < 0.1 and current not in (
            PromotionStage.DEPRECATED,
            PromotionStage.MERGED,
        ):
            self.promote(node_id, PromotionStage.DEPRECATED, "quality_too_low")
            return PromotionStage.DEPRECATED

        return current

    def record_usage(self, node_id: str) -> None:
        """Record that knowledge was used by a task."""
        self._last_used[node_id] = time.time()
        current = self._stages.get(node_id)
        if current == PromotionStage.VERIFIED:
            self.promote(node_id, PromotionStage.ACTIVE, "used_by_task")
        elif current == PromotionStage.ORPHANED:
            self.promote(node_id, PromotionStage.ACTIVE, "reactivated_by_task")

    def detect_orphans(self) -> list[str]:
        """Find knowledge that hasn't been used within the orphan threshold."""
        cutoff = time.time() - self.criteria.max_age_hours_for_orphan * 3600
        orphans: list[str] = []
        for node_id, stage in self._stages.items():
            if stage in (PromotionStage.ACTIVE, PromotionStage.VERIFIED):
                last = self._last_used.get(node_id, 0)
                if last < cutoff:
                    self.promote(node_id, PromotionStage.ORPHANED, "no_recent_usage")
                    orphans.append(node_id)
        return orphans

    def get_stage(self, node_id: str) -> PromotionStage:
        return self._stages.get(node_id, PromotionStage.CANDIDATE)

    def get_by_stage(self, stage: PromotionStage) -> list[str]:
        return [nid for nid, s in self._stages.items() if s == stage]

    def get_pipeline_summary(self) -> dict:
        by_stage: dict[str, int] = {}
        for s in self._stages.values():
            by_stage[s.value] = by_stage.get(s.value, 0) + 1
        return {
            "total_tracked": len(self._stages),
            "by_stage": by_stage,
            "total_promotions": len(self._history),
        }

    def get_recent_events(self, limit: int = 20) -> list[dict]:
        return [
            {"node": e.node_id, "from": e.from_stage, "to": e.to_stage, "reason": e.reason}
            for e in self._history[-limit:]
        ]

    def get_stats(self) -> dict:
        return self.get_pipeline_summary()
