import logging
import json
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)

logger = logging.getLogger("qdrant_vector_store")


class QdrantVectorStore(MemoryContract):
    """MEM-9: Qdrant Implementation of Semantic Memory.
    Stores embeddings and metadata for semantic search.
    """

    def __init__(
        self,
        url: str,
        collection_name: str = "semantic_memory",
        api_key: Optional[str] = None,
    ):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
        self._ensure_collection()
        logger.info(f"Initialized Qdrant Vector Store at {url} (Collection: {collection_name})")

    def _ensure_collection(self):
        # Check if collection exists, create if not
        # Assume 768 dim for standard biomedical/text models (e.g. PubMedBERT or similar)
        # Update dimension based on actual embedding model used in the ecosystem
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=rest.VectorParams(size=768, distance=rest.Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")

    async def store(self, payload: MemoryPayload):
        """Store semantic memory as a vector."""
        from ai_router.embedding_client import EmbeddingClient

        client = EmbeddingClient()

        # If content is complex, serialize it
        content_str = str(payload.content)

        # Real embedding generation using the KNOWLEDGE layer (1024 dim defaults to bge-large)
        vector = await client.embed(content_str, layer="knowledge")

        point = rest.PointStruct(
            id=str(payload.id),
            vector=vector,
            payload={
                "content": content_str,
                "memory_type": payload.memory_type.value,
                "source_agent": payload.metadata.source_agent,
                "confidence": payload.metadata.confidence,
                "tags": payload.metadata.tags,
                "created_at": payload.metadata.created_at.isoformat(),
            },
        )

        self.client.upsert(collection_name=self.collection_name, points=[point])
        logger.debug(f"Stored vector {payload.id} in Qdrant")

    async def retrieve(self, query: str, filters: Dict[str, Any]) -> List[MemoryPayload]:
        """Retrieve using vector similarity."""
        from ai_router.embedding_client import EmbeddingClient

        client = EmbeddingClient()

        # Real embedding of the query using the KNOWLEDGE layer
        query_vector = await client.embed(query, layer="knowledge")

        # Build filter
        q_filter = None
        if filters:
            must_conditions = []
            for k, v in filters.items():
                # Handle list containment "in"
                if isinstance(v, list):
                    must_conditions.append(rest.FieldCondition(key=k, match=rest.MatchAny(any=v)))
                else:
                    must_conditions.append(
                        rest.FieldCondition(key=k, match=rest.MatchValue(value=v))
                    )

            if must_conditions:
                q_filter = rest.Filter(must=must_conditions)

        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=q_filter,
            limit=filters.get("limit", 5),
        )

        results = []
        for scored_point in search_result:
            p = scored_point.payload
            results.append(
                MemoryPayload(
                    id=UUID(scored_point.id),
                    memory_type=MemoryType(p.get("memory_type", MemoryType.SEMANTIC.value)),
                    content=p.get("content"),
                    metadata=MemoryMetadata(
                        source_agent=p.get("source_agent", "qdrant"),
                        confidence=p.get(
                            "confidence", scored_point.score
                        ),  # Use stored confidence or search score?
                        tags=p.get("tags", []),
                        # created_at handled by pydantic default or parsed
                    ),
                )
            )
        return results

    async def forget(self, policy: Dict[str, Any]):
        """Delete vectors."""
        if "id" in policy:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=rest.PointIdsList(points=[str(policy["id"])]),
            )
        elif "filter" in policy:
            # Delete by filter
            pass  # Implement if needed
