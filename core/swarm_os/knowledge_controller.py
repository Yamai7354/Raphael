"""
SOS-507 — Knowledge Integration Controller.

Validates, deduplicates, and tracks knowledge across
memory, embeddings, and the world model. Provides query APIs.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.knowledge_controller")


@dataclass
class KnowledgeEntry:
    """A validated knowledge item."""

    entry_id: str = field(default_factory=lambda: f"ke_{uuid.uuid4().hex[:8]}")
    content: str = ""
    source: str = ""
    confidence: float = 0.5
    usage_count: int = 0
    last_used_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    embedded: bool = False
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.entry_id,
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "usage_count": self.usage_count,
            "embedded": self.embedded,
            "content_preview": self.content[:80],
        }


class KnowledgeController:
    """Central knowledge management and validation."""

    def __init__(
        self,
        min_content_length: int = 20,
        min_confidence: float = 0.3,
        dedup_threshold: float = 0.92,
    ):
        self.min_content_length = min_content_length
        self.min_confidence = min_confidence
        self.dedup_threshold = dedup_threshold
        self._entries: dict[str, KnowledgeEntry] = {}
        self._rejected: list[dict] = []
        self._merged: int = 0

    def validate_and_store(
        self, content: str, source: str = "", confidence: float = 0.5, tags: list[str] | None = None
    ) -> KnowledgeEntry | None:
        """Validate content quality and store if it passes."""
        # Quality gate: min length
        if len(content.strip()) < self.min_content_length:
            self._rejected.append({"reason": "too_short", "source": source, "length": len(content)})
            return None

        # Quality gate: min confidence
        if confidence < self.min_confidence:
            self._rejected.append(
                {"reason": "low_confidence", "source": source, "confidence": confidence}
            )
            return None

        # Dedup: check for near-duplicates
        for existing in self._entries.values():
            similarity = self._quick_similarity(content, existing.content)
            if similarity >= self.dedup_threshold:
                # Merge: update existing instead of creating new
                existing.confidence = max(existing.confidence, confidence)
                existing.usage_count += 1
                existing.last_used_at = time.time()
                self._merged += 1
                return existing

        entry = KnowledgeEntry(
            content=content,
            source=source,
            confidence=confidence,
            tags=tags or [],
        )
        self._entries[entry.entry_id] = entry
        logger.info(
            "knowledge_stored id=%s source=%s confidence=%.2f", entry.entry_id, source, confidence
        )
        return entry

    def query(self, keyword: str, min_confidence: float = 0) -> list[KnowledgeEntry]:
        """Search knowledge entries by keyword."""
        kw = keyword.lower()
        results = [
            e
            for e in self._entries.values()
            if kw in e.content.lower() and e.confidence >= min_confidence
        ]
        # Mark as used
        for r in results:
            r.usage_count += 1
            r.last_used_at = time.time()
        return sorted(results, key=lambda e: e.confidence, reverse=True)

    def query_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        t = tag.lower()
        return [e for e in self._entries.values() if t in [x.lower() for x in e.tags]]

    def get_stale(self, max_age_hours: float = 168) -> list[KnowledgeEntry]:
        """Find knowledge not used in a while."""
        cutoff = time.time() - max_age_hours * 3600
        return [e for e in self._entries.values() if e.last_used_at < cutoff]

    def compress(self) -> int:
        """Remove low-confidence, unused entries."""
        to_remove = [
            eid for eid, e in self._entries.items() if e.confidence < 0.3 and e.usage_count == 0
        ]
        for eid in to_remove:
            del self._entries[eid]
        return len(to_remove)

    def _quick_similarity(self, a: str, b: str) -> float:
        """Fast character-level Jaccard similarity."""
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union else 0.0

    def get_all(self, limit: int = 50) -> list[dict]:
        entries = sorted(self._entries.values(), key=lambda e: e.confidence, reverse=True)
        return [e.to_dict() for e in entries[:limit]]

    def get_stats(self) -> dict:
        return {
            "total_entries": len(self._entries),
            "rejected": len(self._rejected),
            "merged": self._merged,
            "avg_confidence": round(
                sum(e.confidence for e in self._entries.values()) / max(1, len(self._entries)), 3
            ),
        }
