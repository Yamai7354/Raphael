"""
KQ-606 — Knowledge Lifecycle Manager.

Manages knowledge from creation to archival:
new → validated → widely_used → outdated → archived.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.knowledge_quality.lifecycle")


class KnowledgeState(str, Enum):
    NEW = "new"
    VALIDATED = "validated"
    WIDELY_USED = "widely_used"
    OUTDATED = "outdated"
    ARCHIVED = "archived"


@dataclass
class LifecycleRecord:
    node_id: str = ""
    state: KnowledgeState = KnowledgeState.NEW
    usage_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    transitions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "usage": self.usage_count,
            "transitions": len(self.transitions),
        }


class LifecycleManager:
    """Manages knowledge state transitions."""

    VALID_TRANSITIONS = {
        KnowledgeState.NEW: {KnowledgeState.VALIDATED, KnowledgeState.ARCHIVED},
        KnowledgeState.VALIDATED: {
            KnowledgeState.WIDELY_USED,
            KnowledgeState.OUTDATED,
            KnowledgeState.ARCHIVED,
        },
        KnowledgeState.WIDELY_USED: {KnowledgeState.OUTDATED, KnowledgeState.ARCHIVED},
        KnowledgeState.OUTDATED: {KnowledgeState.VALIDATED, KnowledgeState.ARCHIVED},
        KnowledgeState.ARCHIVED: {KnowledgeState.NEW},  # can be restored
    }

    def __init__(self, widely_used_threshold: int = 10, outdated_age_hours: float = 720):  # 30 days
        self.widely_used_threshold = widely_used_threshold
        self.outdated_age_hours = outdated_age_hours
        self._records: dict[str, LifecycleRecord] = {}

    def register(self, node_id: str) -> LifecycleRecord:
        if node_id in self._records:
            return self._records[node_id]
        record = LifecycleRecord(node_id=node_id)
        self._records[node_id] = record
        return record

    def transition(self, node_id: str, new_state: KnowledgeState, reason: str = "") -> bool:
        record = self._records.get(node_id)
        if not record:
            return False
        valid = self.VALID_TRANSITIONS.get(record.state, set())
        if new_state not in valid:
            logger.warning(
                "invalid_transition node=%s %s -> %s", node_id, record.state.value, new_state.value
            )
            return False
        old = record.state
        record.state = new_state
        record.transitions.append(
            {
                "from": old.value,
                "to": new_state.value,
                "reason": reason,
                "at": time.time(),
            }
        )
        logger.info(
            "lifecycle_transition node=%s %s -> %s: %s", node_id, old.value, new_state.value, reason
        )
        return True

    def record_access(self, node_id: str) -> None:
        record = self._records.get(node_id)
        if record:
            record.usage_count += 1
            record.last_accessed = time.time()
            # Auto-promote to widely_used
            if (
                record.state == KnowledgeState.VALIDATED
                and record.usage_count >= self.widely_used_threshold
            ):
                self.transition(node_id, KnowledgeState.WIDELY_USED, "usage_threshold_reached")

    def check_outdated(self) -> list[str]:
        """Find nodes that should be marked outdated."""
        cutoff = time.time() - self.outdated_age_hours * 3600
        outdated: list[str] = []
        for nid, record in self._records.items():
            if record.state in (KnowledgeState.VALIDATED, KnowledgeState.WIDELY_USED):
                if record.last_accessed < cutoff:
                    if self.transition(nid, KnowledgeState.OUTDATED, "no_recent_access"):
                        outdated.append(nid)
        return outdated

    def get_state(self, node_id: str) -> KnowledgeState | None:
        r = self._records.get(node_id)
        return r.state if r else None

    def get_by_state(self, state: KnowledgeState) -> list[str]:
        return [nid for nid, r in self._records.items() if r.state == state]

    def get_stats(self) -> dict:
        by_state: dict[str, int] = {}
        for r in self._records.values():
            by_state[r.state.value] = by_state.get(r.state.value, 0) + 1
        return {"total": len(self._records), "by_state": by_state}
