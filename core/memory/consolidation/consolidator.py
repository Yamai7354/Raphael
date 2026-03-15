import asyncio
import logging
from ..episodic.postgres_store import PostgresEpisodicStore
from graph.graph_api import Neo4jGraphStore
from ..procedural.procedural_store import ProceduralMemoryStore
from ..contracts.memory_contract import MemoryPayload, MemoryType, MemoryMetadata

logger = logging.getLogger("consolidation_worker")


class ConsolidationWorker:
    """MEM-6: Background worker for memory consolidation.
    Converts Episodic (raw experiences) -> Semantic (distilled knowledge) + Procedural (heuristics).
    """

    def __init__(
        self,
        episodic: PostgresEpisodicStore,
        semantic: Neo4jGraphStore,
        procedural: ProceduralMemoryStore,
    ):
        from .distiller import LLMDistiller
        from .governance_layer import GovernanceLayer

        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.distiller = LLMDistiller()

        # Instantiate the Governance Layer
        self.governance = GovernanceLayer(
            episodic=self.episodic,
            semantic=self.semantic,
            procedural=self.procedural,
            distiller=self.distiller,
        )

        self._running = False

    async def run_once(self):
        """Perform a single pass of consolidation using the Governance Layer."""
        logger.info("Starting consolidation pass via GovernanceLayer...")
        await self.governance.run_governance_cycle()

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
