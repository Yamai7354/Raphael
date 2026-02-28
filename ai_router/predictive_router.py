"""
Predictive Router & Pattern Analyzer for AI Router.

analyzes task history to predict future subtasks and dependencies.
Provides confidence-weighted predictions for prefetching.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, deque
from datetime import datetime

logger = logging.getLogger("ai_router.predictive")


# =============================================================================
# PREDICTION DATA MODELS
# =============================================================================


@dataclass
class Prediction:
    """A prediction for a future subtask."""

    source_role: str  # The role that just finished/is running
    predicted_role: str  # The likely next role
    confidence: float  # 0.0 to 1.0
    predicted_dependencies: List[str] = field(default_factory=list)
    reason: str = "pattern_match"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "source_role": self.source_role,
            "predicted_role": self.predicted_role,
            "confidence": round(self.confidence, 2),
            "predicted_dependencies": self.predicted_dependencies,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# PATTERN ANALYZER
# =============================================================================


class PatternAnalyzer:
    """
    Analyzes task sequences to build a transition probability model.
    A simple Markov chain implementation of order 1 (Current Role -> Next Role).
    """

    def __init__(self):
        # Maps current_role -> next_role -> frequency
        self._transitions: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._total_transitions: Dict[str, int] = defaultdict(int)

        # Dependency patterns: role -> commonly_dependent_on_roles
        self._dependency_patterns: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Threshold for high confidence
        self.confidence_threshold = 0.7

    def record_transition(
        self,
        from_role: str,
        to_role: str,
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """Record a completed transition between subtasks."""
        if not from_role or not to_role:
            return

        # Update transition counts
        self._transitions[from_role][to_role] += 1
        self._total_transitions[from_role] += 1

        # Update dependency patterns for the target role
        if dependencies:
            # We track which roles the 'to_role' commonly depends on
            # This is a simplification; ideally we'd track specific logic
            pass

        logger.debug(
            "pattern_recorded from=%s to=%s total_source=%d",
            from_role,
            to_role,
            self._total_transitions[from_role],
        )

    def predict_next(self, current_role: str) -> List[Prediction]:
        """
        Predict likely next roles based on current role.
        Returns list of predictions sorted by confidence.
        """
        if current_role not in self._transitions:
            return []

        total = self._total_transitions[current_role]
        if total < 5:  # Minimum sample size
            return []

        predictions = []
        for next_role, count in self._transitions[current_role].items():
            confidence = count / total

            # Simple dependency forecast (mock logic for now)
            # In a real system, we'd infer this from _dependency_patterns
            predicted_deps = []
            if next_role == "summarizer" and current_role == "chat":
                predicted_deps = ["chat_history"]

            predictions.append(
                Prediction(
                    source_role=current_role,
                    predicted_role=next_role,
                    confidence=confidence,
                    predicted_dependencies=predicted_deps,
                    reason=f"historical_freq_{confidence:.2f}",
                )
            )

        # Filter by threshold and sort
        valid_predictions = [
            p for p in predictions if p.confidence >= self.confidence_threshold
        ]
        valid_predictions.sort(key=lambda x: x.confidence, reverse=True)

        return valid_predictions

    def get_stats(self) -> Dict:
        """Get analyzer statistics."""
        return {
            "known_sources": len(self._transitions),
            "total_patterns": sum(len(t) for t in self._transitions.values()),
            "confidence_threshold": self.confidence_threshold,
        }


# =============================================================================
# PREDICTIVE ROUTER
# =============================================================================


class PredictiveRouter:
    """
    High-level interface for predictive planning.
    """

    def __init__(self):
        self.analyzer = PatternAnalyzer()
        self._predictions_history: deque = deque(maxlen=100)

    def update_model(self, task_id: str, sequence: List[Dict]) -> None:
        """
        Update model from a completed task execution sequence.
        sequence: list of {role: str, ...} in order
        """
        if len(sequence) < 2:
            return

        for i in range(len(sequence) - 1):
            from_role = sequence[i].get("role")
            to_role = sequence[i + 1].get("role")
            # deps = sequence[i+1].get("dependencies")
            self.analyzer.record_transition(from_role, to_role)

    def generate_predictions(self, current_subtask: Dict) -> List[Prediction]:
        """Generate predictions for a running subtask."""
        role = current_subtask.get("role")
        if not role:
            return []

        preds = self.analyzer.predict_next(role)

        # Log forecasts
        if preds:
            self._predictions_history.append(
                {
                    "source": role,
                    "preds": [p.to_dict() for p in preds],
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return preds

    def get_recent_predictions(self) -> List[Dict]:
        """Get recent prediction history."""
        return list(self._predictions_history)


# Global singleton
predictive_router = PredictiveRouter()

# Pre-seed with some common patterns for demonstration
# Chat -> Summarizer is very common
predictive_router.analyzer.record_transition("chat", "summarizer")
predictive_router.analyzer.record_transition("chat", "summarizer")
predictive_router.analyzer.record_transition("chat", "summarizer")
predictive_router.analyzer.record_transition("chat", "coder")
predictive_router.analyzer.record_transition("coder", "summarizer")
