"""
Embedding Router — routes embedding workloads to the correct node.

Layer 1 (ROUTING):   text-embedding-bge-small-en-v1.5  → desktop-node (LM Studio)
Layer 2 (KNOWLEDGE): text-embedding-bge-large-en-v1.5  → desktop-node (LM Studio)
Layer 3 (CODE):      vishalraj/nomic-embed-code:latest  → mac-node     (Ollama)
"""

import logging
import os
from enum import Enum

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node URLs (read from environment, matching .env)
# ---------------------------------------------------------------------------
DESKTOP_URL = os.getenv("OLLAMA_DESKTOP_URL", "http://100.125.58.22:5000").rstrip("/")
MAC_URL = os.getenv("OLLAMA_MAC_URL", "http://localhost:11434").rstrip("/")


class EmbeddingLayer(str, Enum):
    ROUTING = "routing"  # text-embedding-bge-small-en-v1.5
    KNOWLEDGE = "knowledge"  # text-embedding-bge-large-en-v1.5
    CODE = "code"  # vishalraj/nomic-embed-code:latest


class EmbeddingModelConfig(BaseModel):
    model_name: str
    host_url: str
    dimension: int
    registry_type: str  # "lmstudio" or "ollama" — determines API shape


class EmbeddingRouter:
    """
    Directs semantic embedding workloads across three specialized layers:
    - Layer 1 (ROUTING): Fast swarm routing caching           → desktop-node
    - Layer 2 (KNOWLEDGE): Deep long-term memory + Neo4j Graph → desktop-node
    - Layer 3 (CODE): Technical intelligence, syntax matching  → mac-node
    """

    # Config-driven mappings — BGE on Desktop, nomic on Mac
    LAYER_MAPPINGS: dict[EmbeddingLayer, EmbeddingModelConfig] = {
        EmbeddingLayer.ROUTING: EmbeddingModelConfig(
            model_name="text-embedding-bge-small-en-v1.5",
            host_url=DESKTOP_URL,
            dimension=384,
            registry_type="lmstudio",
        ),
        EmbeddingLayer.KNOWLEDGE: EmbeddingModelConfig(
            model_name="text-embedding-bge-large-en-v1.5",
            host_url=DESKTOP_URL,
            dimension=1024,
            registry_type="lmstudio",
        ),
        EmbeddingLayer.CODE: EmbeddingModelConfig(
            model_name="vishalraj/nomic-embed-code:latest",
            host_url=MAC_URL,
            dimension=768,
            registry_type="ollama",
        ),
    }

    def __init__(self, default_batch_size: int = 50):
        self.default_batch_size = default_batch_size

    def get_layer_config(self, layer: EmbeddingLayer) -> EmbeddingModelConfig:
        return self.LAYER_MAPPINGS[layer]

    async def embed(
        self, text: str | list[str], layer: EmbeddingLayer
    ) -> list[float] | list[list[float]]:
        """
        Embed text(s) using the specified semantic layer model and host.
        Automatically batches large lists.
        Routes to the correct node based on registry type.
        """
        config = self.get_layer_config(layer)

        # Build the correct API URL based on registry type
        if config.registry_type == "ollama":
            # Ollama native batch endpoint
            api_url = f"{config.host_url}/api/embed"
        else:
            # LM Studio — also supports /api/embed (Ollama-compat)
            api_url = f"{config.host_url}/api/embed"

        # Normalize to list for batch processing
        is_single = isinstance(text, str)
        texts_to_embed = [text] if is_single else text

        if not texts_to_embed:
            return []

        # Process in batches
        all_embeddings = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Create batches
            batches = [
                texts_to_embed[i : i + self.default_batch_size]
                for i in range(0, len(texts_to_embed), self.default_batch_size)
            ]

            # Process batches sequentially to avoid overwhelming the host
            for batch in batches:
                batch_embeddings = await self._process_batch(
                    client, api_url, config.model_name, batch
                )
                all_embeddings.extend(batch_embeddings)

        if is_single:
            return all_embeddings[0] if all_embeddings else []
        return all_embeddings

    async def _process_batch(
        self, client: httpx.AsyncClient, api_url: str, model_name: str, batch: list[str]
    ) -> list[list[float]]:

        embeddings: list[list[float]] = []
        payload = {"model": model_name, "input": batch}

        try:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            data = response.json()

            if "embeddings" in data:
                return data["embeddings"]  # type: ignore[no-any-return]

        except httpx.HTTPError as e:
            logger.error(f"HTTP Error querying embedding layer {model_name} at {api_url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error formatting embedding query for {model_name}: {e}")
            raise

        return embeddings
