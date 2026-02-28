"""
Cross-Task State Store for AI Router.

Provides immutable, auditable state sharing between tasks and subtasks.
References are explicit and validated.
"""

import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from enum import Enum

logger = logging.getLogger("ai_router.shared_state")


# =============================================================================
# STATE ENTRY
# =============================================================================


@dataclass
class StateEntry:
    """An immutable state entry."""

    key: str  # Unique key (task_id:subtask_id:output_key)
    value: Any  # The stored value
    created_at: datetime
    created_by: str  # subtask_id that created this
    task_id: str  # Owning task

    # Immutability tracking
    version: int = 1
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute hash of value for integrity."""
        import json

        try:
            content = json.dumps(self.value, sort_keys=True, default=str)
        except Exception:
            content = str(self.value)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "task_id": self.task_id,
            "version": self.version,
            "content_hash": self.content_hash,
        }


# =============================================================================
# STATE REFERENCE
# =============================================================================


@dataclass
class StateRef:
    """A reference to a state entry."""

    task_id: str
    subtask_id: str
    output_key: str

    @property
    def key(self) -> str:
        return f"{self.task_id}:{self.subtask_id}:{self.output_key}"

    @classmethod
    def parse(cls, key: str) -> "StateRef":
        """Parse key string into StateRef."""
        parts = key.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid state key format: {key}")
        return cls(task_id=parts[0], subtask_id=parts[1], output_key=parts[2])

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "subtask_id": self.subtask_id,
            "output_key": self.output_key,
            "key": self.key,
        }


# =============================================================================
# SHARED STATE STORE
# =============================================================================


class SharedStateStore:
    """
    Immutable state store for cross-task/subtask references.

    Once written, entries cannot be modified (append-only).
    """

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._store: Dict[str, StateEntry] = {}
        self._by_task: Dict[str, Set[str]] = {}  # task_id -> keys
        self._access_log: List[Dict] = []

    def put(
        self,
        task_id: str,
        subtask_id: str,
        output_key: str,
        value: Any,
    ) -> StateEntry:
        """
        Store a value. Creates immutable entry.
        Raises ValueError if key already exists.
        """
        ref = StateRef(task_id, subtask_id, output_key)
        key = ref.key

        if key in self._store:
            raise ValueError(f"State key already exists (immutable): {key}")

        entry = StateEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            created_by=subtask_id,
            task_id=task_id,
        )

        self._store[key] = entry

        # Track by task
        if task_id not in self._by_task:
            self._by_task[task_id] = set()
        self._by_task[task_id].add(key)

        # Enforce max entries
        if len(self._store) > self.max_entries:
            self._evict_oldest()

        # Log
        self._log_access("put", key, subtask_id)
        logger.info(
            "state_stored key=%s task=%s subtask=%s hash=%s",
            key,
            task_id,
            subtask_id,
            entry.content_hash,
        )

        return entry

    def get(
        self,
        ref: StateRef,
        accessor: str = "unknown",
    ) -> Optional[Any]:
        """
        Get value by reference.
        Returns None if not found.
        """
        key = ref.key
        entry = self._store.get(key)

        # Log access
        self._log_access("get", key, accessor)

        if entry:
            return entry.value

        logger.warning("state_not_found key=%s accessor=%s", key, accessor)
        return None

    def get_by_key(
        self,
        key: str,
        accessor: str = "unknown",
    ) -> Optional[Any]:
        """Get value by string key."""
        try:
            ref = StateRef.parse(key)
            return self.get(ref, accessor)
        except ValueError:
            return None

    def exists(self, ref: StateRef) -> bool:
        """Check if state entry exists."""
        return ref.key in self._store

    def get_entry(self, ref: StateRef) -> Optional[StateEntry]:
        """Get full entry (not just value)."""
        return self._store.get(ref.key)

    def get_task_outputs(self, task_id: str) -> Dict[str, Any]:
        """Get all outputs for a task."""
        keys = self._by_task.get(task_id, set())
        return {key: self._store[key].value for key in keys if key in self._store}

    def validate_references(
        self,
        refs: List[StateRef],
    ) -> tuple[bool, List[str]]:
        """
        Validate that all references exist.
        Returns (all_valid, missing_keys).
        """
        missing = []
        for ref in refs:
            if not self.exists(ref):
                missing.append(ref.key)
        return len(missing) == 0, missing

    def _log_access(self, action: str, key: str, accessor: str) -> None:
        """Log state access."""
        self._access_log.append(
            {
                "action": action,
                "key": key,
                "accessor": accessor,
                "timestamp": datetime.now().isoformat(),
            }
        )
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-500:]

    def _evict_oldest(self) -> None:
        """Evict oldest entries when over limit."""
        sorted_entries = sorted(self._store.values(), key=lambda e: e.created_at)
        to_remove = len(self._store) - self.max_entries
        for entry in sorted_entries[:to_remove]:
            del self._store[entry.key]
            if entry.task_id in self._by_task:
                self._by_task[entry.task_id].discard(entry.key)

    def get_stats(self) -> Dict:
        """Get store statistics."""
        return {
            "total_entries": len(self._store),
            "tasks_tracked": len(self._by_task),
            "access_log_size": len(self._access_log),
            "max_entries": self.max_entries,
        }

    def get_recent_accesses(self, limit: int = 20) -> List[Dict]:
        """Get recent access log entries."""
        return self._access_log[-limit:]


# Global singleton
shared_state_store = SharedStateStore()
