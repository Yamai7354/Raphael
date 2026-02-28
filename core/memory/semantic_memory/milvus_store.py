"""
Milvus Vector Store — Connector for the Milvus vector database.

Implements MemoryContract for storing and retrieving embeddings
via Milvus. Complementary to Qdrant (used for high-throughput
batch embedding workloads).
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pymilvus import (
    MilvusClient,
    DataType,
    CollectionSchema,
    FieldSchema,
)

from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)

logger = logging.getLogger("milvus_vector_store")


class MilvusVectorStore(MemoryContract):
    """Milvus implementation of semantic memory storage.

    Used for high-throughput embedding workloads and batch operations.
    Configured via MILVUS_URI in .env (default: http://localhost:19530).
    """

    def __init__(
        self,
        uri: str = "http://localhost:19530",
        collection_name: str = "semantic_memory",
        dimension: int = 768,
    ):
        self.uri = uri
        self.collection_name = collection_name
        self.dimension = dimension
        self.client = MilvusClient(uri=uri)
        self._ensure_collection()
        logger.info("Initialized Milvus Vector Store at %s (collection: %s)", uri, collection_name)

    def _ensure_collection(self) -> None:
        """Create the collection if it doesn't exist."""
        if self.client.has_collection(self.collection_name):
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="memory_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="source_agent", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="confidence", dtype=DataType.FLOAT),
            FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=1024),
        ]
        schema = CollectionSchema(fields=fields, description="Semantic memory embeddings")
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
        )
        # Create vector index for fast search
        self.client.create_index(
            collection_name=self.collection_name,
            field_name="vector",
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 128},
            },
        )
        logger.info("Created Milvus collection: %s", self.collection_name)

    async def store(self, payload: MemoryPayload) -> None:
        """Store a memory payload as a vector in Milvus."""
        from ai_router.embedding_client import EmbeddingClient

        client = EmbeddingClient()
        content_str = str(payload.content)
        vector = await client.embed(content_str, layer="knowledge")

        data = [
            {
                "id": str(payload.id),
                "vector": vector,
                "content": content_str[:65535],
                "memory_type": payload.memory_type.value,
                "source_agent": payload.metadata.source_agent,
                "confidence": payload.metadata.confidence,
                "tags": ",".join(payload.metadata.tags),
            }
        ]

        self.client.insert(collection_name=self.collection_name, data=data)
        logger.debug("Stored vector %s in Milvus", payload.id)

    async def retrieve(self, query: str, filters: Dict[str, Any]) -> List[MemoryPayload]:
        """Retrieve similar memories via vector search."""
        from ai_router.embedding_client import EmbeddingClient

        client = EmbeddingClient()
        query_vector = await client.embed(query, layer="knowledge")
        limit = filters.get("limit", 5)

        # Build filter expression
        filter_expr = ""
        if "memory_type" in filters:
            filter_expr = f'memory_type == "{filters["memory_type"]}"'
        if "source_agent" in filters:
            agent_filter = f'source_agent == "{filters["source_agent"]}"'
            filter_expr = f"{filter_expr} and {agent_filter}" if filter_expr else agent_filter

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            limit=limit,
            output_fields=["content", "memory_type", "source_agent", "confidence", "tags"],
            search_params=search_params,
            filter=filter_expr or None,
        )

        payloads = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                tags_str = entity.get("tags", "")
                payloads.append(
                    MemoryPayload(
                        id=UUID(hit["id"]) if "-" in str(hit["id"]) else uuid4(),
                        memory_type=MemoryType(entity.get("memory_type", "semantic")),
                        content=entity.get("content", ""),
                        metadata=MemoryMetadata(
                            source_agent=entity.get("source_agent", "milvus"),
                            confidence=entity.get("confidence", hit.get("distance", 0.0)),
                            tags=tags_str.split(",") if tags_str else [],
                        ),
                    )
                )
        return payloads

    async def forget(self, policy: Dict[str, Any]) -> None:
        """Delete vectors by ID or filter."""
        if "id" in policy:
            self.client.delete(
                collection_name=self.collection_name,
                ids=[str(policy["id"])],
            )
        elif "filter" in policy:
            self.client.delete(
                collection_name=self.collection_name,
                filter=policy["filter"],
            )

    def count(self) -> int:
        """Return total number of vectors in the collection."""
        stats = self.client.get_collection_stats(self.collection_name)
        return stats.get("row_count", 0)

    def drop_collection(self) -> None:
        """Drop the entire collection (use with caution)."""
        self.client.drop_collection(self.collection_name)
        logger.warning("Dropped Milvus collection: %s", self.collection_name)
