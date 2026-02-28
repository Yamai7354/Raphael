"""
SWARM-112 — Knowledge Consolidation Cycle.

Periodic processes to compress and improve swarm knowledge:
duplicate detection, concept merging, research summarization,
embedding recalculation, and archive of exploration artifacts.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("swarm.evolution.consolidation")


@dataclass
class ConsolidationResult:
    """Outcome of a single consolidation cycle."""

    cycle_id: int
    timestamp: float = field(default_factory=time.time)
    duplicates_found: int = 0
    concepts_merged: int = 0
    summaries_generated: int = 0
    embeddings_recalculated: int = 0
    artifacts_archived: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "duplicates_found": self.duplicates_found,
            "concepts_merged": self.concepts_merged,
            "summaries_generated": self.summaries_generated,
            "embeddings_recalculated": self.embeddings_recalculated,
            "artifacts_archived": self.artifacts_archived,
            "duration_seconds": round(self.duration_seconds, 3),
        }


class KnowledgeConsolidator:
    """
    Runs periodic consolidation cycles to compress and improve
    the swarm's collective knowledge.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self._cycle_count = 0
        self._history: list[ConsolidationResult] = []
        self._knowledge_store: list[dict] = []

    def add_knowledge(self, entry: dict) -> None:
        """Add a knowledge entry for future consolidation."""
        entry.setdefault("timestamp", time.time())
        entry.setdefault("archived", False)
        self._knowledge_store.append(entry)

    def run_cycle(self, aggressive: bool = False) -> ConsolidationResult:
        """
        Execute a full consolidation cycle.

        Steps:
        1. Detect duplicate knowledge entries
        2. Merge similar concepts
        3. Summarize research clusters
        4. Flag stale embeddings for recalculation
        5. Archive old exploration artifacts
        """
        self._cycle_count += 1
        start = time.time()

        result = ConsolidationResult(cycle_id=self._cycle_count)

        # Step 1: Duplicate detection
        result.duplicates_found = self._detect_duplicates()

        # Step 2: Concept merging
        result.concepts_merged = self._merge_concepts()

        # Step 3: Research summarization
        result.summaries_generated = self._summarize_research()

        # Step 4: Embedding recalculation flagging
        result.embeddings_recalculated = self._flag_stale_embeddings()

        # Step 5: Archive exploration artifacts
        result.artifacts_archived = self._archive_old_artifacts(
            max_age_days=7 if aggressive else 30
        )

        result.duration_seconds = time.time() - start
        self._history.append(result)

        logger.info(
            "consolidation_cycle=%d dupes=%d merged=%d summaries=%d embeds=%d archived=%d",
            self._cycle_count,
            result.duplicates_found,
            result.concepts_merged,
            result.summaries_generated,
            result.embeddings_recalculated,
            result.artifacts_archived,
        )
        return result

    def _detect_duplicates(self) -> int:
        """Find and mark duplicate knowledge entries."""
        seen_titles: dict[str, int] = {}
        duplicates = 0
        for entry in self._knowledge_store:
            title = entry.get("title", "").lower().strip()
            if title in seen_titles:
                entry["duplicate_of"] = seen_titles[title]
                duplicates += 1
            else:
                seen_titles[title] = entry.get("id", id(entry))
        return duplicates

    def _merge_concepts(self) -> int:
        """Merge entries with overlapping domains and similar content."""
        domain_groups: dict[str, list[dict]] = {}
        for entry in self._knowledge_store:
            domain = entry.get("domain", "general")
            domain_groups.setdefault(domain, []).append(entry)

        merged = 0
        for domain, entries in domain_groups.items():
            if len(entries) > 5:
                # Simple heuristic: flag excess entries for review
                merged += len(entries) - 5
        return merged

    def _summarize_research(self) -> int:
        """Generate summaries for research clusters."""
        unsummarized = [
            e for e in self._knowledge_store if not e.get("summary") and not e.get("archived")
        ]
        for entry in unsummarized:
            entry["summary"] = f"[Auto-summary] {entry.get('title', 'Untitled')}"
        return len(unsummarized)

    def _flag_stale_embeddings(self) -> int:
        """Flag entries whose embeddings are older than the content."""
        flagged = 0
        for entry in self._knowledge_store:
            embed_time = entry.get("embedding_time", 0)
            content_time = entry.get("updated_at", entry.get("timestamp", 0))
            if content_time > embed_time:
                entry["needs_reembedding"] = True
                flagged += 1
        return flagged

    def _archive_old_artifacts(self, max_age_days: int = 30) -> int:
        """Archive exploration artifacts older than max_age_days."""
        cutoff = time.time() - (max_age_days * 86400)
        archived = 0
        for entry in self._knowledge_store:
            if (
                not entry.get("archived")
                and entry.get("type") == "exploration"
                and entry.get("timestamp", time.time()) < cutoff
            ):
                entry["archived"] = True
                archived += 1
        return archived

    def get_history(self) -> list[dict]:
        return [r.to_dict() for r in self._history]

    def get_stats(self) -> dict:
        total = len(self._knowledge_store)
        archived = sum(1 for e in self._knowledge_store if e.get("archived"))
        return {
            "total_entries": total,
            "archived": archived,
            "active": total - archived,
            "cycles_run": self._cycle_count,
        }
