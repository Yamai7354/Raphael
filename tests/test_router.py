import asyncio
from typing import List
from raphael.ai_router.embedding_client import EmbeddingClient
import logging

logging.basicConfig(level=logging.INFO)


async def test_embed():
    client = EmbeddingClient()

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


if __name__ == "__main__":
    asyncio.run(test_embed())
