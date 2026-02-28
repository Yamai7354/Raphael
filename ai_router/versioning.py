"""
Versioning System for AI Router.

Tracks versions of planner logic, role schemas, and router code.
Supports replay with historical versions.
"""

import logging
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("ai_router.versioning")


# =============================================================================
# VERSION INFO
# =============================================================================


# Router version - update on significant changes
ROUTER_VERSION = "1.0.0"
PLANNER_VERSION = "1.0.0"
ROLE_SCHEMA_VERSION = "1.0.0"


@dataclass
class VersionInfo:
    """Version information for the router."""

    router: str = ROUTER_VERSION
    planner: str = PLANNER_VERSION
    role_schema: str = ROLE_SCHEMA_VERSION
    config_hash: str = ""
    started_at: str = ""

    def combined_version(self) -> str:
        """Get combined version string."""
        return f"r{self.router}-p{self.planner}-s{self.role_schema}"

    def to_dict(self) -> Dict:
        return {
            "router_version": self.router,
            "planner_version": self.planner,
            "role_schema_version": self.role_schema,
            "config_hash": self.config_hash,
            "combined": self.combined_version(),
            "started_at": self.started_at,
        }


# =============================================================================
# VERSION REGISTRY
# =============================================================================


class VersionRegistry:
    """
    Tracks version history and provides version context for logs.
    """

    def __init__(self):
        self._current = VersionInfo(started_at=datetime.now().isoformat())
        self._history: list[VersionInfo] = []

    @property
    def current(self) -> VersionInfo:
        return self._current

    def set_config_hash(self, config_content: str) -> str:
        """Set config hash from content."""
        hash_val = hashlib.sha256(config_content.encode()).hexdigest()[:12]
        self._current.config_hash = hash_val
        logger.info("config_hash_set hash=%s", hash_val)
        return hash_val

    def update_planner_version(self, version: str) -> None:
        """Update planner version (e.g., after hot-reload)."""
        old_version = self._current.planner
        self._history.append(self._current)
        self._current = VersionInfo(
            router=self._current.router,
            planner=version,
            role_schema=self._current.role_schema,
            config_hash=self._current.config_hash,
            started_at=datetime.now().isoformat(),
        )
        logger.info("planner_version_updated old=%s new=%s", old_version, version)

    def update_role_schema_version(self, version: str) -> None:
        """Update role schema version."""
        old_version = self._current.role_schema
        self._history.append(self._current)
        self._current = VersionInfo(
            router=self._current.router,
            planner=self._current.planner,
            role_schema=version,
            config_hash=self._current.config_hash,
            started_at=datetime.now().isoformat(),
        )
        logger.info("role_schema_version_updated old=%s new=%s", old_version, version)

    def get_version_for_log(self) -> Dict[str, str]:
        """Get version info for log entries."""
        return {
            "version": self._current.combined_version(),
            "config_hash": self._current.config_hash,
        }

    def get_history(self) -> list[Dict]:
        """Get version history."""
        return [v.to_dict() for v in self._history]

    def rollback_to_previous(self) -> Optional[VersionInfo]:
        """Rollback to previous version (if any)."""
        if not self._history:
            logger.warning("rollback_failed no_previous_version")
            return None

        previous = self._history.pop()
        self._current = previous
        logger.info("version_rollback to=%s", previous.combined_version())
        return previous


# Global singleton
version_registry = VersionRegistry()


def get_current_version() -> Dict:
    """Get current version info."""
    return version_registry.current.to_dict()
