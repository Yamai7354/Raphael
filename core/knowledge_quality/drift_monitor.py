"""
KQ-613 — Knowledge Drift Monitoring.

Detects when knowledge becomes outdated or invalid:
tracks evidence changes, identifies outdated conclusions,
triggers revalidation.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.drift")


@dataclass
class DriftEvent:
    node_id: str = ""
    drift_type: str = ""  # evidence_change, contradiction_found, stale, superseded
    description: str = ""
    severity: float = 0.5
    action: str = ""  # revalidate, archive, review
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "node": self.node_id,
            "type": self.drift_type,
            "severity": round(self.severity, 3),
            "action": self.action,
        }


class DriftMonitor:
    """Monitors for knowledge drift and staleness."""

    def __init__(
        self,
        stale_threshold_hours: float = 336,  # 14 days
        evidence_change_threshold: int = 2,
    ):
        self.stale_hours = stale_threshold_hours
        self.evidence_change_threshold = evidence_change_threshold
        self._node_metadata: dict[
            str, dict
        ] = {}  # node_id -> {created_at, evidence_count, last_checked}
        self._events: list[DriftEvent] = []

    def register_node(self, node_id: str, created_at: float, evidence_count: int = 0) -> None:
        self._node_metadata[node_id] = {
            "created_at": created_at,
            "evidence_count": evidence_count,
            "last_checked": time.time(),
        }

    def check_drift(
        self, node_id: str, current_evidence_count: int = 0, has_contradiction: bool = False
    ) -> list[DriftEvent]:
        """Check a single node for drift."""
        events: list[DriftEvent] = []
        meta = self._node_metadata.get(node_id)
        if not meta:
            return events

        # Staleness check
        age_hours = (time.time() - meta["created_at"]) / 3600
        if age_hours > self.stale_hours:
            events.append(
                DriftEvent(
                    node_id=node_id,
                    drift_type="stale",
                    description=f"Node is {age_hours:.0f}h old (threshold: {self.stale_hours}h)",
                    severity=min(1.0, age_hours / (self.stale_hours * 2)),
                    action="revalidate",
                )
            )

        # Evidence change
        old_count = meta.get("evidence_count", 0)
        delta = abs(current_evidence_count - old_count)
        if delta >= self.evidence_change_threshold:
            events.append(
                DriftEvent(
                    node_id=node_id,
                    drift_type="evidence_change",
                    description=f"Evidence count changed: {old_count} -> {current_evidence_count}",
                    severity=min(1.0, delta / 5),
                    action="review",
                )
            )
            meta["evidence_count"] = current_evidence_count

        # Contradiction
        if has_contradiction:
            events.append(
                DriftEvent(
                    node_id=node_id,
                    drift_type="contradiction_found",
                    description="Node has active contradictions",
                    severity=0.7,
                    action="review",
                )
            )

        meta["last_checked"] = time.time()
        self._events.extend(events)
        return events

    def scan_all(
        self,
        evidence_counts: dict[str, int] | None = None,
        contradicted_nodes: set[str] | None = None,
    ) -> list[DriftEvent]:
        """Scan all registered nodes for drift."""
        ev_counts = evidence_counts or {}
        contradicted = contradicted_nodes or set()
        all_events: list[DriftEvent] = []
        for node_id in list(self._node_metadata.keys()):
            events = self.check_drift(
                node_id,
                current_evidence_count=ev_counts.get(node_id, 0),
                has_contradiction=node_id in contradicted,
            )
            all_events.extend(events)
        return all_events

    def get_events(self, limit: int = 30) -> list[dict]:
        return [e.to_dict() for e in self._events[-limit:]]

    def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        for e in self._events:
            by_type[e.drift_type] = by_type.get(e.drift_type, 0) + 1
        return {
            "monitored_nodes": len(self._node_metadata),
            "total_events": len(self._events),
            "by_type": by_type,
        }
