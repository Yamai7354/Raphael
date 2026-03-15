#!/usr/bin/env python3
"""
seed_swarm_graph.py — Phase 1: Knowledge Graph Core

Seeds the Neo4j database with:
  - Schema constraints for all Swarm Director node types
  - Base Capability nodes (code_generation, research, video_generation, gpu_inference)
  - Base AgentType nodes (planner, coding_agent, search_agent, test_runner, embedding_worker)
  - Base Service nodes (vector_memory, repo_service, model_cache)

Usage:
  python scripts/seed_swarm_graph.py

Requires NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD environment variables.
"""

import asyncio
import os
import sys
import uuid

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.graph_api import Neo4jGraphStore


# ─── Base data ────────────────────────────────────────────────────────
BASE_CAPABILITIES = [
    {"name": "code_generation", "description": "Ability to generate, refactor, and debug code"},
    {"name": "research", "description": "Ability to search, summarize, and synthesize information"},
    {"name": "video_generation", "description": "Ability to generate and edit video content"},
    {"name": "gpu_inference", "description": "Ability to run GPU-accelerated model inference"},
]

BASE_AGENT_TYPES = [
    {"name": "planner", "description": "Orchestrates task decomposition and agent coordination"},
    {"name": "coding_agent", "description": "Writes, reviews, and tests code"},
    {"name": "search_agent", "description": "Performs web and knowledge base searches"},
    {"name": "test_runner", "description": "Executes test suites and reports results"},
    {
        "name": "embedding_worker",
        "description": "Generates vector embeddings for documents and queries",
    },
]

BASE_SERVICES = [
    {"name": "vector_memory", "description": "Persistent vector database for semantic search"},
    {"name": "repo_service", "description": "Git repository management and code operations"},
    {"name": "model_cache", "description": "Caches downloaded model weights for fast loading"},
]

# AgentType → Capability mappings
AGENT_CAPABILITIES = {
    "planner": ["research"],
    "coding_agent": ["code_generation"],
    "search_agent": ["research"],
    "test_runner": ["code_generation"],
    "embedding_worker": ["gpu_inference"],
}


async def seed(store: Neo4jGraphStore):
    """Seed the graph with base swarm ontology data."""

    # 1. Initialize constraints
    print("🔒 Initializing schema constraints...")
    await store.initialize_constraints()
    print("   ✓ Constraints created")

    # 2. Seed Capabilities
    print("\n📦 Seeding base capabilities...")
    for cap in BASE_CAPABILITIES:
        await store.store_node(
            label="Capability",
            uuid=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"capability.{cap['name']}")),
            memory_type="infrastructure",
            properties={**cap, "promotion_score": 1.0},
        )
        print(f"   ✓ Capability: {cap['name']}")

    # 3. Seed AgentTypes
    print("\n🤖 Seeding base agent types...")
    for agent in BASE_AGENT_TYPES:
        await store.store_node(
            label="AgentType",
            uuid=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"agenttype.{agent['name']}")),
            memory_type="infrastructure",
            properties={**agent, "promotion_score": 1.0},
        )
        print(f"   ✓ AgentType: {agent['name']}")

    # 4. Seed Services
    print("\n⚙️  Seeding base services...")
    for svc in BASE_SERVICES:
        await store.store_node(
            label="Service",
            uuid=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"service.{svc['name']}")),
            memory_type="infrastructure",
            properties={**svc, "promotion_score": 1.0},
        )
        print(f"   ✓ Service: {svc['name']}")

    # 5. Create AgentType → Capability relationships
    print("\n🔗 Linking agent types to capabilities...")
    for agent_name, cap_names in AGENT_CAPABILITIES.items():
        agent_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"agenttype.{agent_name}"))
        for cap_name in cap_names:
            cap_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"capability.{cap_name}"))
            await store.create_relationship(
                from_uuid=agent_uuid,
                to_uuid=cap_uuid,
                relation_type="HAS_CAPABILITY",
                properties={"source": "seed_script"},
            )
            print(f"   ✓ {agent_name} -[HAS_CAPABILITY]→ {cap_name}")

    # 6. Verify
    print("\n🔍 Verification:")
    counts = await store.execute_cypher(
        "MATCH (n) WHERE n:Capability OR n:AgentType OR n:Service "
        "RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"
    )
    for row in counts:
        print(f"   {row['label']}: {row['count']} nodes")

    rels = await store.execute_cypher("MATCH ()-[r:HAS_CAPABILITY]->() RETURN count(r) as count")
    print(f"   HAS_CAPABILITY relationships: {rels[0]['count']}")

    print("\n✅ Phase 1 seed complete!")


async def main():
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    if not password:
        print("❌ NEO4J_PASSWORD not set. Export it and retry.")
        sys.exit(1)

    print(f"Connecting to Neo4j at {uri}...")
    store = Neo4jGraphStore(uri=uri, auth=(user, password))

    try:
        connected = await store.verify_connectivity()
        if not connected:
            print("❌ Cannot connect to Neo4j. Check URI and credentials.")
            sys.exit(1)
        print("✓ Connected\n")

        await seed(store)
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
