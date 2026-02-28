import logging
from enum import Enum

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EmbeddingLayer(str, Enum):
    ROUTING = "routing"  # text-embedding-bge-small-en-v1.5
    KNOWLEDGE = "knowledge"  # text-embedding-bge-large-en-v1.5
    CODE = "code"  # text-embedding-bge-large-en-v1.5 (fallback)


class EmbeddingModelConfig(BaseModel):
    model_name: str
    host_url: str
    dimension: int


class EmbeddingRouter:
    """
    Directs semantic embedding workloads across three specialized layers:
    - Layer 1 (ROUTING): Fast swarm routing caching
    - Layer 2 (KNOWLEDGE): Deep long-term memory + Neo4j Graph
    - Layer 3 (CODE): Technical intelligence, syntax matching
    """

    # Static configuration matching user specifications
    LAYER_MAPPINGS: dict[EmbeddingLayer, EmbeddingModelConfig] = {
        EmbeddingLayer.ROUTING: EmbeddingModelConfig(
            model_name="text-embedding-bge-small-en-v1.5",
            host_url="http://100.125.58.22:5000",
            dimension=384,
        ),
        EmbeddingLayer.KNOWLEDGE: EmbeddingModelConfig(
            model_name="text-embedding-bge-large-en-v1.5", host_url="http://100.125.58.22:5000", dimension=1024
        ),
        EmbeddingLayer.CODE: EmbeddingModelConfig(
            model_name="text-embedding-bge-large-en-v1.5",
            host_url="http://100.125.58.22:5000",
            dimension=1024,
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
        """
        config = self.get_layer_config(layer)
        api_url = f"{config.host_url}/api/embeddings"

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

            # We process batches sequentially to avoid overwhelming the Ollama host,
            # but this could be parallelized with asyncio.gather if desired.
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
        # Ollama /api/embeddings endpoint accepts one prompt at a time
        # You could also use /api/embed which takes `input: list[str]` for native batching.
        # We'll use /api/embed for true batching if Ollama is >= 0.1.33

        payload = {"model": model_name, "input": batch}

        try:
            response = await client.post(
                f"{api_url.replace('/embeddings', '/embed')}",  # enforce native batching
                json=payload,
            )
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
