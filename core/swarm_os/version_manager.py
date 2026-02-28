"""
SOS-511 — Version & Change Management.

Tracks swarm config, agent evolution, system changes.
Supports rollback to previous states and experiment reproducibility.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.version_manager")


@dataclass
class VersionRecord:
    """A versioned snapshot of swarm state."""

    version_id: str = field(default_factory=lambda: f"v_{uuid.uuid4().hex[:8]}")
    version_num: int = 0
    change_type: str = ""  # config_update, agent_evolution, prototype_integration, memory_update
    description: str = ""
    snapshot: dict = field(default_factory=dict)
    author: str = "system"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "version": self.version_num,
            "type": self.change_type,
            "description": self.description,
            "author": self.author,
        }


class VersionManager:
    """Tracks and manages swarm version history."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._versions: list[VersionRecord] = []
        self._current_version = 0

    def record(
        self,
        change_type: str,
        description: str,
        snapshot: dict | None = None,
        author: str = "system",
    ) -> VersionRecord:
        """Record a new version."""
        self._current_version += 1
        record = VersionRecord(
            version_num=self._current_version,
            change_type=change_type,
            description=description,
            snapshot=snapshot or {},
            author=author,
        )
        self._versions.append(record)
        if len(self._versions) > self.max_history:
            self._versions = self._versions[-self.max_history :]
        logger.info(
            "version_recorded v%d type=%s: %s", self._current_version, change_type, description
        )
        return record

    def get_current_version(self) -> int:
        return self._current_version

    def get_version(self, version_num: int) -> VersionRecord | None:
        for v in self._versions:
            if v.version_num == version_num:
                return v
        return None

    def get_rollback_target(self, version_num: int) -> dict | None:
        """Get the snapshot at a given version for rollback."""
        record = self.get_version(version_num)
        return record.snapshot if record else None

    def get_history(self, limit: int = 20) -> list[dict]:
        return [v.to_dict() for v in self._versions[-limit:]]

    def get_changes_since(self, version_num: int) -> list[dict]:
        return [v.to_dict() for v in self._versions if v.version_num > version_num]

    def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        for v in self._versions:
            by_type[v.change_type] = by_type.get(v.change_type, 0) + 1
        return {
            "current_version": self._current_version,
            "total_records": len(self._versions),
            "by_type": by_type,
        }
