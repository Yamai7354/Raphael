import asyncio
import logging
from ..episodic.sqlite_store import SQLiteEpisodicStore
from ..semantic.vector_store import VectorStore
from ..procedural.procedural_store import ProceduralMemoryStore
from ..contracts.memory_contract import MemoryPayload, MemoryType, MemoryMetadata

logger = logging.getLogger("consolidation_worker")


class ConsolidationWorker:
    """MEM-6: Background worker for memory consolidation.
    Converts Episodic (raw experiences) -> Semantic (distilled knowledge) + Procedural (heuristics).
    """

    def __init__(
        self,
        episodic: SQLiteEpisodicStore,
        semantic: VectorStore,
        procedural: ProceduralMemoryStore,
    ):
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        from .distiller import LLMDistiller

        self.distiller = LLMDistiller()
        self._running = False

    async def run_once(self):
        """Perform a single pass of consolidation."""
        logger.info("Starting consolidation pass...")

        # 1. Fetch completed tasks
        tasks = await self.episodic.query_tasks({"status": "completed"})

        for task in tasks:
            # 2. Distill knowledge from task history (NAR-1)
            # In a real scenario, we'd also fetch task logs
            task_dict = {
                "id": task.id,
                "title": task.title,
                "assigned_to": task.assigned_to,
                "priority": task.priority.value
                if hasattr(task.priority, "value")
                else str(task.priority),
                # Metadata might contain category
                "category": task.metadata.get("category", "general")
                if task.metadata
                else "general",
            }

            insights = await self.distiller.distill_task(task_dict)

            # 3. Store in Semantic Memory (MEM-4 / NAR-2)
            # We attribute the memory to the agent that did the work
            payload = MemoryPayload(
                memory_type=MemoryType.SEMANTIC,
                content=insights["summary"],
                metadata=MemoryMetadata(
                    source_agent=task.assigned_to or "unknown_agent",
                    tags=["distilled", task_dict["category"]],
                    # Link back to episodic source
                    correlation_id=str(task.id),
                ),
            )
            await self.semantic.store(payload)

            # 4. Store in Procedural Memory if a rule was generated (MEM-5 / NAR-3)
            if insights["rule"]:
                rule = insights["rule"]
                await self.procedural.add_heuristic(
                    condition=rule["condition"],
                    strategy=rule["strategy"],
                    confidence=rule["confidence"],
                )

            logger.info(f"Consolidated task {task.id}")

    async def start(self, interval: int = 3600):
        """Start the background consolidation loop."""
        self._running = True
        while self._running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Consolidation error: {e}")
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False
