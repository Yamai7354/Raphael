"""
Self-Healing Knowledge Scheduler.

Runs periodic maintenance jobs on the knowledge graph:
  - Merge duplicates
  - Promote/demote based on quality
  - Auto-cluster
  - Detect orphans
  - Process research events

Designed to run in a background loop or be called periodically.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.self_healing")


@dataclass
class HealingJobResult:
    job_name: str = ""
    affected: int = 0
    duration_ms: float = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "job": self.job_name,
            "affected": self.affected,
            "duration_ms": round(self.duration_ms, 1),
        }


# Cypher queries for each healing job
HEALING_QUERIES = {
    "merge_duplicates": """
        MATCH (k1:Knowledge), (k2:Knowledge)
        WHERE k1 <> k2
        AND k1.name = k2.name
        AND k1.name IS NOT NULL
        WITH k1, collect(k2) AS dups
        WHERE size(dups) > 0
        WITH k1, dups[0] AS k2
        MERGE (k1)<-[:MERGED_INTO]-(k2)
        SET k2.status = 'merged'
        RETURN count(k2) AS cnt
    """,
    "promote_high_quality": """
        MATCH (k:Knowledge)
        WHERE k.quality_score > 0.8
        AND k.status <> 'verified'
        AND k.status <> 'merged'
        SET k.status = 'verified'
        RETURN count(k) AS cnt
    """,
    "demote_low_confidence": """
        MATCH (k:Knowledge)
        WHERE k.confidence_score < 0.2
        AND k.status <> 'merged'
        AND k.status <> 'deprecated'
        SET k.status = 'deprecated'
        RETURN count(k) AS cnt
    """,
    "auto_cluster": """
        MATCH (k:Knowledge)
        WHERE k.agent_origin IS NOT NULL
        AND NOT (k)-[:PART_OF]->(:KnowledgeCluster)
        MERGE (cluster:KnowledgeCluster {theme: k.agent_origin + '_research'})
        MERGE (k)-[:PART_OF]->(cluster)
        RETURN count(k) AS cnt
    """,
    "detect_orphans": """
        MATCH (k:Knowledge)
        WHERE NOT (k)<-[:USES]-(:Task)
        AND k.status <> 'merged'
        AND k.status <> 'deprecated'
        AND k.status <> 'orphaned'
        SET k.status = 'orphaned'
        RETURN count(k) AS cnt
    """,
}


class SelfHealingScheduler:
    """Runs periodic knowledge graph maintenance jobs."""

    def __init__(self, neo4j_driver=None, interval_minutes: float = 30):
        self._driver = neo4j_driver
        self.interval_minutes = interval_minutes
        self._results: list[HealingJobResult] = []
        self._last_run: float = 0
        self._enabled = True

    def set_driver(self, driver) -> None:
        self._driver = driver

    def run_all(self) -> list[HealingJobResult]:
        """Execute all healing jobs."""
        if not self._driver:
            logger.error("no Neo4j driver configured")
            return []

        results: list[HealingJobResult] = []
        with self._driver.session() as session:
            for job_name, query in HEALING_QUERIES.items():
                start = time.time()
                try:
                    result = session.run(query).single()
                    affected = result["cnt"] if result else 0
                except Exception as e:
                    logger.error("healing_job_failed job=%s error=%s", job_name, str(e)[:100])
                    affected = -1

                duration_ms = (time.time() - start) * 1000
                jr = HealingJobResult(
                    job_name=job_name,
                    affected=affected,
                    duration_ms=duration_ms,
                )
                results.append(jr)
                logger.info(
                    "healing_job job=%s affected=%d duration=%.1fms",
                    job_name,
                    affected,
                    duration_ms,
                )

        self._results.extend(results)
        self._last_run = time.time()
        return results

    def run_job(self, job_name: str) -> HealingJobResult | None:
        """Run a single healing job by name."""
        query = HEALING_QUERIES.get(job_name)
        if not query or not self._driver:
            return None

        start = time.time()
        with self._driver.session() as session:
            try:
                result = session.run(query).single()
                affected = result["cnt"] if result else 0
            except Exception as e:
                logger.error("healing_job_failed job=%s error=%s", job_name, str(e)[:100])
                affected = -1

        duration_ms = (time.time() - start) * 1000
        jr = HealingJobResult(
            job_name=job_name,
            affected=affected,
            duration_ms=duration_ms,
        )
        self._results.append(jr)
        return jr

    def should_run(self) -> bool:
        """Check if enough time has passed since last run."""
        if not self._enabled:
            return False
        return time.time() - self._last_run >= self.interval_minutes * 60

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def get_last_results(self, limit: int = 10) -> list[dict]:
        return [r.to_dict() for r in self._results[-limit:]]

    def get_stats(self) -> dict:
        return {
            "total_runs": len(self._results),
            "last_run": self._last_run,
            "enabled": self._enabled,
            "interval_minutes": self.interval_minutes,
            "jobs_available": list(HEALING_QUERIES.keys()),
        }
