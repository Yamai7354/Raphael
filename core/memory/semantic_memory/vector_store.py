import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import lancedb

    print(f"DEBUG: VectorStore imported lancedb: {lancedb}")
except ImportError as e:
    lancedb = None
    print(f"DEBUG: VectorStore lancedb import failed: {e}")

from .base import SemanticMemory
from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)

logger = logging.getLogger("semantic_memory")


class VectorStore(MemoryContract):
    """Semantic Memory layer for vector storage and RAG using LanceDB."""

    def __init__(self, uri: str = "data/lancedb", table_name: str = "knowledge"):
        self.uri = uri
        self.table_name = table_name
        self._db = None
        self._table = None
        if lancedb:
            self._init_db()

    def _init_db(self):
        try:
            self._db = lancedb.connect(self.uri)
            if self.table_name not in self._db.table_names():
                # Schema placeholder: vector, text, id, metadata
                # Note: Schema is usually defined when the first data is added or explicitly
                logger.info(f"Creating new table '{self.table_name}' in LanceDB")
            else:
                self._table = self._db.open_table(self.table_name)
            logger.info(f"Connected to LanceDB at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB: {e}")

    async def add(self, text: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None):
        """Add a semantic entry to the store."""
        if self._db is None:
            logger.warning("LanceDB not available")
            return

        # Handle datetime serialization in metadata
        def serialize_meta(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, (Dict, list)):
                return obj  # json.dumps handles nesting
            return str(obj)

        safe_metadata = {}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, datetime):
                    safe_metadata[k] = v.isoformat()
                else:
                    safe_metadata[k] = v

        data = [
            {
                "vector": vector,
                "text": text,
                "metadata": json.dumps(safe_metadata),
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

        if self.table_name not in self._db.table_names():
            self._table = self._db.create_table(self.table_name, data=data)
        else:
            self._table.add(data)

    async def search(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar entries."""
        if self._table is None:
            return []

        results = self._table.search(vector).limit(limit).to_list()
        for res in results:
            if "metadata" in res:
                res["metadata"] = json.loads(res["metadata"])
        return results

    async def store(self, payload: MemoryPayload):
        """Cross-project storage contract (MEM-1)."""
        # Assume payload.content is text for semantic store
        from raphael.ai_router.embedding_client import EmbeddingClient

        client = EmbeddingClient()

        # Real implementation using the EmbeddingClient KNOWLEDGE layer
        vector = await client.embed(str(payload.content), layer="knowledge")

        # Use pydantic's mode='json' if available, else manual
        meta_dict = payload.metadata.model_dump()
        await self.add(str(payload.content), vector, meta_dict)

    async def retrieve(self, query: str, filters: Dict[str, Any]) -> List[MemoryPayload]:
        """Cross-project retrieval contract (MEM-1)."""
        from raphael.ai_router.embedding_client import EmbeddingClient

        client = EmbeddingClient()

        # Real implementation embedding the query using the KNOWLEDGE layer
        query_vector = await client.embed(query, layer="knowledge")
        results = await self.search(query_vector, limit=filters.get("limit", 5))

        payloads = []
        for res in results:
            meta = res.get("metadata", {})
            payloads.append(
                MemoryPayload(
                    memory_type=MemoryType.SEMANTIC,
                    content=res["text"],
                    metadata=MemoryMetadata(
                        source_agent=meta.get("source_agent", "vector_store"),
                        confidence=meta.get("confidence", 0.9),
                        tags=meta.get("tags", []),
                        # ... other fields if needed ...
                    ),
                )
            )
        return payloads

    async def forget(self, policy: Dict[str, Any]):
        """Sanitization and pruning contract (MEM-1)."""
        # LanceDB pruning logic would go here
        pass
