#!/usr/bin/env python3
import os
import asyncio
import uuid
import logging
from dotenv import load_dotenv

from graph.graph_api import Neo4jGraphStore
from core.knowledge_quality.intake_gate import Provenance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WipeAndPopulate")


async def run_wipe_and_populate():
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Zr65oJYpg")

    store = Neo4jGraphStore(uri=uri, auth=(user, password))

    # 1. WIPE LEGACY GRAPH
    logger.info("Wiping entire Neo4j database...")
    destroy_query = "MATCH (n) DETACH DELETE n"
    await store.execute_cypher(destroy_query)
    logger.info("Database wiped.")

    # 2. INITIALIZE CONSTRAINTS
    logger.info("Creating Swarm-Grade Ontology Constraints...")
    await store.initialize_constraints()

    # 3. MOCK ORGANIC DATA POPULATION
    logger.info("Injecting Swarm-Grade Mock Data...")

    # Create Agent
    agent_id = str(uuid.uuid4())
    await store.store_node(
        label="Agent",
        uuid=agent_id,
        memory_type="semantic",
        properties={"name": "Rikka Planner", "role": "Orchestrator", "promotion_score": 0.95},
    )

    # Create Concept
    concept_id = str(uuid.uuid4())
    await store.store_node(
        label="Concept",
        uuid=concept_id,
        memory_type="semantic",
        properties={
            "name": "Neo4j Graph Constraints",
            "description": "Rules enforced to strictly prevent duplicate nodes and generic graph sprawl.",
            "promotion_score": 1.0,
        },
    )

    # Create Relationship (Agent -> Concept)
    await store.create_relationship(
        from_uuid=agent_id, to_uuid=concept_id, relation_type="USES_CONCEPT"
    )

    # Create Procedure
    proc_id = str(uuid.uuid4())
    await store.store_node(
        label="Procedure",
        uuid=proc_id,
        memory_type="procedural",
        properties={"name": "Wipe Legacy DB", "promotion_score": 0.88},
    )

    # Create Relationship (Agent -> Procedure)
    await store.create_relationship(
        from_uuid=agent_id, to_uuid=proc_id, relation_type="CREATED_PROCEDURE"
    )

    # Create Episode
    ep_id = str(uuid.uuid4())
    await store.store_node(
        label="Episode",
        uuid=ep_id,
        memory_type="episodic",
        properties={"name": "Executed script check_kg.py", "promotion_score": 0.1},
    )

    # Link Episode
    await store.create_relationship(
        from_uuid=ep_id, to_uuid=agent_id, relation_type="INVOLVED_AGENT"
    )
    await store.create_relationship(
        from_uuid=ep_id, to_uuid=concept_id, relation_type="AFFECTED_CONCEPT"
    )

    logger.info("Population complete! Checking the final counts...")

    results = await store.execute_cypher("MATCH (n) RETURN labels(n) AS label, count(n) AS count")
    print("\n--- Final Graph State ---")
    for no in results:
        lbl = no["label"][0] if no["label"] else "NoLabel"
        print(f"- {lbl}: {no['count']}")

    await store.close()


if __name__ == "__main__":
    asyncio.run(run_wipe_and_populate())
