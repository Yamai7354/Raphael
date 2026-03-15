import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

from .distiller import LLMDistiller
from ..episodic.postgres_store import PostgresEpisodicStore
from graph.graph_api import Neo4jGraphStore
from ..procedural.procedural_store import ProceduralMemoryStore
from ..contracts.memory_contract import MemoryPayload, MemoryType, MemoryMetadata

logger = logging.getLogger("memory_governance")


class GovernanceLayer:
    """
    The Missing Brain: Memory Governance Layer
    Observes episodic memory, scores quality, tracks bloat, and triggers promotions:
    - 10+ similar successful episodes -> Promoted to Procedural strategy
    - 100+ episodes -> Promoted to Semantic summary
    - Prunes low-signal noise
    """

    def __init__(
        self,
        episodic: PostgresEpisodicStore,
        semantic: Neo4jGraphStore,
        procedural: ProceduralMemoryStore,
        distiller: LLMDistiller,
    ):
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.distiller = distiller

        # Thresholds (potentially loaded from config later)
        self.procedural_promotion_threshold = 10
        self.semantic_summarization_threshold = 100
        self.min_success_score_for_promotion = 0.8

        self._running = False

    async def run_governance_cycle(self):
        """Execute one pass of the governance rules engine."""
        logger.info("Starting Memory Governance Cycle...")
        if not self.episodic.pool:
            await self.episodic.connect()

        try:
            # 1. Procedural Promotion: Find repeated successful tasks
            await self._check_procedural_promotions()

            # 2. Semantic Summarization: Bulk summarize older episodes
            await self._check_semantic_summarizations()

            # 3. Pruning: Delete useless noise
            await self._prune_noise()

            # 4. Global Audit: Compute metrics and build a :MemoryAudit node
            await self._generate_audit_metrics()

        except Exception as e:
            logger.error(f"Governance cycle failed: {e}")

    async def _check_procedural_promotions(self):
        """If 10+ episodes of the same task_type have high success, distill a procedure."""
        query = """
            SELECT task_type, COUNT(*) as count, AVG(success_score) as avg_score
            FROM episodic_tasks
            WHERE success_score > 0
            GROUP BY task_type
            HAVING COUNT(*) >= $1 AND AVG(success_score) >= $2
        """
        async with self.episodic.pool.acquire() as conn:
            rows = await conn.fetch(
                query, self.procedural_promotion_threshold, self.min_success_score_for_promotion
            )

            for row in rows:
                task_type = row["task_type"]
                logger.info(
                    f"Promoting {task_type} (count={row['count']}, avg_score={row['avg_score']}) to Procedural Memory."
                )

                # Fetch recent examples to give the Distiller context
                examples = await conn.fetch(
                    "SELECT raw_data_ref FROM episodic_tasks WHERE task_type = $1 AND success_score > 0 LIMIT 5",
                    task_type,
                )

                task_examples = [ex["raw_data_ref"] for ex in examples if ex["raw_data_ref"]]

                # Call Distiller
                insights = await self.distiller.distill_task(
                    {"task_type": task_type, "is_bulk_promotion": True, "examples": task_examples}
                )

                if insights.get("rule"):
                    rule = insights["rule"]
                    await self.procedural.add_procedure(
                        name=rule.get("condition", task_type),
                        steps=[{"step": rule.get("strategy", "Unknown strategy")}],
                        success_rate=row["avg_score"],
                        avg_latency=1.0,  # Placeholder until we track latency in episodic
                    )

                    # Optional: tag the episodes so we don't promote them again
                    # await conn.execute("UPDATE episodic_tasks SET success_score = 0.1 WHERE task_type = $1", task_type)

    async def _check_semantic_summarizations(self):
        """Summarize chunks of 100 episodes into a single Semantic concept."""
        # A simpler implementation for now: just grab oldest 100 un-summarized episodes
        # In a real system, we'd add a 'summarized' boolean to `episodic_tasks`.
        pass

    async def _prune_noise(self):
        """Delete episodes with negative success scores or that are very old and unutilized."""
        async with self.episodic.pool.acquire() as conn:
            # Prune failed noise that hasn't led to anything
            result = await conn.execute(
                "DELETE FROM episodic_tasks WHERE success_score < 0 AND timestamp < NOW() - INTERVAL '7 days'"
            )
            logger.debug(f"Pruned noise: {result}")

    async def _generate_audit_metrics(self):
        """Calculates system memory metrics and pushes a MemoryAudit node to Neo4j."""
        import uuid
        from datetime import datetime

        async with self.episodic.pool.acquire() as conn:
            # Noise Score (fraction of bad experiences)
            total_cases = await conn.fetchval("SELECT COUNT(*) FROM episodic_tasks")
            if total_cases == 0:
                logger.debug("Skipping audit generation: 0 episodic tasks.")
                return

            bad_cases = await conn.fetchval(
                "SELECT COUNT(*) FROM episodic_tasks WHERE success_score <= 0"
            )
            noise_score = bad_cases / total_cases

            # Redundancy Score (how much duplication exists: count - distinct types / count)
            types_count = await conn.fetchval(
                "SELECT COUNT(DISTINCT task_type) FROM episodic_tasks"
            )
            redundancy_score = (total_cases - types_count) / total_cases if total_cases > 0 else 0.0

            # Compression Ratio (Procedures / Total Episodic)
            # Not a precise theoretical compression bound, but a pragmatic system metric.
            procedural_total = len(await self.procedural.retrieve({}, 10000))
            compression_ratio = procedural_total / total_cases if total_cases > 0 else 0.0

        audit_uuid = str(uuid.uuid4())
        audit_props = {
            "redundancy_score": float(redundancy_score),
            "noise_score": float(noise_score),
            "compression_ratio": float(compression_ratio),
            "last_run": datetime.utcnow().isoformat(),
            "memory_type": "audit",
            "promotion_score": 1.0,
        }

        # Use new explicit Swarm-Grade schema
        await self.semantic.store_node(
            label="MemoryAudit",
            uuid=audit_uuid,
            memory_type="audit",
            properties=audit_props,
        )
        logger.info(f"Published MemoryAudit node: {audit_uuid}")

    async def start(self, interval: int = 3600):
        """Start the background governance loop."""
        self._running = True
        while self._running:
            try:
                await self.run_governance_cycle()
            except Exception as e:
                logger.error(f"Governance error: {e}")
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False
