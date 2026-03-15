import asyncio
import httpx
import pytest
from ai_router.embedding_client import EmbeddingClient
import logging

logging.basicConfig(level=logging.INFO)


async def test_embed():
    client = EmbeddingClient()
    try:
        async with httpx.AsyncClient(timeout=2.0) as probe:
            await probe.get("http://localhost:9100/health")
            await probe.get("http://localhost:9200/health")
    except httpx.HTTPError:
        pytest.skip("Embedding services are not running on localhost:9100/9200")

    try:
        # 1. Swarm Routing
        print("\n--- Test Layer 1: Swarm Routing (bge-small-en-v1.5) ---")
        vec1 = await client.embed("Hello world", layer="routing")
        print(f"Dim: {len(vec1)}, Sample: {vec1[:3]}...")

        # 2. Knowledge
        print("\n--- Test Layer 2: Knowledge (bge-large) ---")
        vec2 = await client.embed("Long term memory", layer="knowledge")
        print(f"Dim: {len(vec2)}, Sample: {vec2[:3]}...")

        # 3. Intelligence
        print("\n--- Test Layer 3: Intelligence (nomic-embed-code) ---")
        vec3 = await client.embed("def foo(): pass", layer="code")
        print(f"Dim: {len(vec3)}, Sample: {vec3[:3]}...")

        # 4. Batch Processing
        print("\n--- Test Batch Processing (Layer 1) ---")
        batch = ["One", "Two", "Three"]
        vecs = await client.embed(batch, layer="routing")
        print(f"Batch returned {len(vecs)} vectors")
        if vecs:
            print(f"Dim 1: {len(vecs[0])}, Sample 1: {vecs[0][:3]}...")
    except httpx.HTTPError as exc:
        pytest.skip(f"Embedding backend not ready: {exc}")


if __name__ == "__main__":
    asyncio.run(test_embed())
