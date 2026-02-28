"""
WORLD-409 — External Knowledge Source Integration.

Represents external data sources: documentation systems,
research databases, repositories, and datasets.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.world_model.external_sources")


class SourceType(str, Enum):
    DOCUMENTATION = "documentation"
    DATABASE = "database"
    REPOSITORY = "repository"
    DATASET = "dataset"
    API = "api"
    WIKI = "wiki"


@dataclass
class ExternalSource:
    """An external knowledge source."""

    source_id: str = field(default_factory=lambda: f"src_{uuid.uuid4().hex[:8]}")
    name: str = ""
    source_type: SourceType = SourceType.DOCUMENTATION
    url: str = ""
    description: str = ""
    access_method: str = "http"  # http, ssh, file, api
    auth_required: bool = False
    refresh_interval_hours: int = 24
    last_synced_at: float = 0
    available: bool = True
    tags: list[str] = field(default_factory=list)
    registered_at: float = field(default_factory=time.time)

    def needs_refresh(self) -> bool:
        if self.refresh_interval_hours <= 0:
            return False
        return time.time() - self.last_synced_at > self.refresh_interval_hours * 3600

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "type": self.source_type.value,
            "url": self.url,
            "access": self.access_method,
            "available": self.available,
            "needs_refresh": self.needs_refresh(),
            "tags": self.tags,
        }


class ExternalSourceRegistry:
    """Registry of external knowledge sources."""

    def __init__(self):
        self._sources: dict[str, ExternalSource] = {}
        self._by_name: dict[str, str] = {}

    def register(
        self, name: str, source_type: SourceType, url: str = "", description: str = "", **kwargs
    ) -> ExternalSource:
        if name in self._by_name:
            return self._sources[self._by_name[name]]

        src = ExternalSource(
            name=name,
            source_type=source_type,
            url=url,
            description=description,
            **kwargs,
        )
        self._sources[src.source_id] = src
        self._by_name[name] = src.source_id
        logger.info("source_registered name=%s type=%s", name, source_type.value)
        return src

    def mark_synced(self, name: str) -> None:
        sid = self._by_name.get(name)
        if sid and sid in self._sources:
            self._sources[sid].last_synced_at = time.time()

    def discover_by_tag(self, tag: str) -> list[ExternalSource]:
        t = tag.lower()
        return [
            s for s in self._sources.values() if s.available and t in [x.lower() for x in s.tags]
        ]

    def discover_by_type(self, source_type: SourceType) -> list[ExternalSource]:
        return [s for s in self._sources.values() if s.source_type == source_type and s.available]

    def get_needing_refresh(self) -> list[ExternalSource]:
        return [s for s in self._sources.values() if s.available and s.needs_refresh()]

    def get_all(self) -> list[dict]:
        return [s.to_dict() for s in self._sources.values()]

    def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        for s in self._sources.values():
            by_type[s.source_type.value] = by_type.get(s.source_type.value, 0) + 1
        return {
            "total_sources": len(self._sources),
            "needing_refresh": len(self.get_needing_refresh()),
            "by_type": by_type,
        }
