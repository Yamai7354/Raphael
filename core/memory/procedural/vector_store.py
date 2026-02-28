"""
Vector Store - Milvus backed semantic memory.

Provides scalable embedding storage and similarity search for arbitrary
text payloads allowing the agent to retrieve past experiences, documentation,
or code blocks by meaning rather than exact keywords.
"""

import os
import json
import uuid
import logging
from typing import Any, Dict, List, Optional
from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType

logger = logging.getLogger("raphael.memory.vector_store")

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "raphael_semantic_memory"
DIMENSION = 1536  # Default dimensionality for OpenAI text-embedding-3-small (adjustable)


class VectorStore:
    def __init__(
        self,
        host: str = None,
        port: str = None,
        collection_name: str = None,
    ):
        self.host = host or MILVUS_HOST
        self.port = port or MILVUS_PORT
        self.collection_name = collection_name or COLLECTION_NAME
        self.collection: Optional[Collection] = None

    async def start(self):
        """Connect to Milvus and initialize the collection."""
        try:
            connections.connect("default", host=self.host, port=self.port)
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
            self._ensure_collection()
            self.collection.load()
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    async def stop(self):
        """Disconnect from Milvus."""
        try:
            connections.disconnect("default")
            logger.info("Disconnected from Milvus.")
        except Exception as e:
            logger.error(f"Error disconnecting Milvus: {e}")

    def _ensure_collection(self):
        """Create the collection if it doesn't already exist."""
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            logger.debug(f"Milvus collection '{self.collection_name}' loaded.")
        else:
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(
                    name="metadata", dtype=DataType.VARCHAR, max_length=65535
                ),  # Stored as JSON string
            ]
            schema = CollectionSchema(fields, description="Raphael Semantic Memory")
            self.collection = Collection(self.collection_name, schema)

            # Create HNSW index for fast similarity search
            index_params = {
                "metric_type": "L2",
                "index_type": "HNSW",
                "params": {"M": 8, "efConstruction": 64},
            }
            self.collection.create_index(field_name="embedding", index_params=index_params)
            logger.info(f"Created new Milvus collection '{self.collection_name}'.")

    async def add_memory(
        self, text: str, embedding: List[float], metadata: Dict[str, Any] = None
    ) -> str:
        """Insert a vector embedding and its text into the store."""
        if not self.collection:
            raise RuntimeError("Milvus collection not initialized. Run start() first.")

        memory_id = str(uuid.uuid4())
        meta_str = json.dumps(metadata) if metadata else "{}"

        try:
            self.collection.insert([[memory_id], [embedding], [text], [meta_str]])
            logger.debug(f"Inserted memory {memory_id} into VectorStore.")
            return memory_id
        except Exception as e:
            logger.error(f"Failed to insert into Milvus: {e}")
            raise

    async def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Search the store for closest vectors."""
        if not self.collection:
            raise RuntimeError("Milvus collection not initialized. Run start() first.")

        search_params = {"metric_type": "L2", "params": {"ef": 64}}

        try:
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["text", "metadata"],
            )

            matches = []
            for hits in results:
                for hit in hits:
                    matches.append(
                        {
                            "id": hit.id,
                            "distance": hit.distance,
                            "text": hit.entity.get("text"),
                            "metadata": json.loads(hit.entity.get("metadata", "{}")),
                        }
                    )
            return matches
        except Exception as e:
            logger.error(f"Failed to search Milvus: {e}")
            return []


# Singleton
vector_store = VectorStore()
