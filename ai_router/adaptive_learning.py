"""
Adaptive Learning & Metrics for AI Router.

Collects execution metrics, calculates node scores, and analyzes trends
to enable adaptive scheduling decisions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ai_router.adaptive")


# =============================================================================
# METRICS STORAGE
# =============================================================================


@dataclass
class ExecutionMetric:
    """A single execution data point."""

    timestamp: datetime
    node_id: str
    role: str
    latency_ms: float
    success: bool
    queue_wait_ms: float

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "node_id": self.node_id,
            "role": self.role,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "queue_wait_ms": self.queue_wait_ms,
        }


# =============================================================================
# SCORING SYSTEM
# =============================================================================


@dataclass
class NodeScore:
    """Calculated score for a node in a specific role."""

    node_id: str
    role: str
    score: float = 0.5  # 0.0 to 1.0
    confidence: float = 0.0  # Based on sample size
    updated_at: datetime = field(default_factory=datetime.now)

    # Component scores
    latency_score: float = 0.0
    reliability_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 2),
            "updated_at": self.updated_at.isoformat(),
            "details": {
                "latency": round(self.latency_score, 3),
                "reliability": round(self.reliability_score, 3),
            },
        }


class AdaptiveLearning:
    """
    Core module for metrics collection, scoring, and analysis.
    """

    def __init__(self, history_window_hours: int = 24):
        self.history_window = timedelta(hours=history_window_hours)
        self._metrics: List[ExecutionMetric] = []
        self._scores: Dict[str, Dict[str, NodeScore]] = {}  # role -> node -> score

        # Configuration
        self.min_samples = 5
        self.latency_weight = 0.4
        self.reliability_weight = 0.6
        self.decay_factor = 0.95  # Decay for older metrics

    def record_execution(
        self,
        node_id: str,
        role: str,
        latency_ms: float,
        success: bool,
        queue_wait_ms: float = 0.0,
    ) -> None:
        """Record an execution metric."""
        metric = ExecutionMetric(
            timestamp=datetime.now(),
            node_id=node_id,
            role=role,
            latency_ms=latency_ms,
            success=success,
            queue_wait_ms=queue_wait_ms,
        )
        self._metrics.append(metric)

        # Prune old metrics occasionally
        if len(self._metrics) > 10000:
            cutoff = datetime.now() - self.history_window
            self._metrics = [m for m in self._metrics if m.timestamp > cutoff]

        # Update score incrementally
        self._update_score(node_id, role)

        logger.debug(
            "metric_recorded node=%s role=%s latency=%.1f success=%s",
            node_id,
            role,
            latency_ms,
            success,
        )

    def get_score(self, node_id: str, role: str) -> Optional[NodeScore]:
        """Get current score for a node/role."""
        return self._scores.get(role, {}).get(node_id)

    def get_all_scores(self) -> Dict[str, Dict[str, float]]:
        """Get flat map of scores: role -> node -> score."""
        result = {}
        for role, nodes in self._scores.items():
            result[role] = {nid: score.to_dict() for nid, score in nodes.items()}
        return result

    def _update_score(self, node_id: str, role: str) -> None:
        """Recalculate score for a node/role."""
        # Get relevant metrics
        relevant = [m for m in self._metrics if m.node_id == node_id and m.role == role]

        count = len(relevant)
        if count < self.min_samples:
            return  # Not enough data yet

        # 1. Reliability Score (Success Rate)
        recent_success = [1.0 if m.success else 0.0 for m in relevant[-20:]]
        reliability = mean(recent_success)

        # 2. Latency Score (Normalized against average)
        # Lower is better, so we invert
        avg_latency = mean([m.latency_ms for m in relevant[-20:]])
        # Use simple baseline of 1000ms for normalization for now
        # In real system, would normalize against role average
        normalized_latency = min(avg_latency / 5000.0, 1.0)
        latency_score = 1.0 - normalized_latency

        # Combined Score
        final_score = (reliability * self.reliability_weight) + (
            latency_score * self.latency_weight
        )

        # Update storage
        if role not in self._scores:
            self._scores[role] = {}

        self._scores[role][node_id] = NodeScore(
            node_id=node_id,
            role=role,
            score=final_score,
            confidence=min(count / 20.0, 1.0),
            latency_score=latency_score,
            reliability_score=reliability,
        )

    def analyze_trends(self) -> Dict[str, Any]:
        """
        Analyze recent trends for dashboard.
        Returns aggregate stats per role.
        """
        trends = {}
        unique_roles = set(m.role for m in self._metrics)

        for role in unique_roles:
            role_metrics = [m for m in self._metrics if m.role == role]
            if not role_metrics:
                continue

            latencies = [m.latency_ms for m in role_metrics]
            successes = [m.success for m in role_metrics]

            trends[role] = {
                "sample_count": len(role_metrics),
                "avg_latency": round(mean(latencies), 2),
                "p95_latency": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
                "success_rate": round(
                    mean([1 if s else 0 for s in successes]) * 100, 1
                ),
                "top_performing_node": self._get_top_node(role),
            }

        return trends

    def _get_top_node(self, role: str) -> Optional[str]:
        """Get best node for a role based on score."""
        nodes = self._scores.get(role, {})
        if not nodes:
            return None
        return max(nodes.items(), key=lambda x: x[1].score)[0]


# Global singleton
adaptive_learning = AdaptiveLearning()
