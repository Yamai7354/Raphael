#!/usr/bin/env python3
import os
import asyncio
import uuid
import logging
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MigrateLegacyKG")


async def run_migration():
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Zr65oJYpg")

    logger.info(f"Connecting to {uri} to perform Swarm-Grade migration...")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    # Label mappings
    # Machine -> Tool
    # Hardware -> Tool
    # Model -> Tool
    # Capability -> Concept
    # Skill -> Procedure
    # Agent -> Agent

    LABEL_MAP = {
        "Machine": "Tool",
        "Hardware": "Tool",
        "Model": "Tool",
        "Capability": "Concept",
        "Skill": "Procedure",
        "Agent": "Agent",
    }

    EDGE_MAP = {
        "HAS_CAPABILITY": "USES_CONCEPT",
        "RUNS_ON": "USES_CONCEPT",  # Abstract models running on machines mapping conceptually
        "HAS_HARDWARE": "USES_CONCEPT",
        "MANAGES": "INVOLVED_AGENT",
        "CONNECTED_TO": "RELATES_TO",  # We will drop RELATES_TO soon but acceptable for bridging if needed. Actually we only allow USES_CONCEPT.
    }

    try:
        async with driver.session() as session:
            # 1. Fetch all nodes
            logger.info("Fetching all legacy nodes...")
            result = await session.run(
                "MATCH (n) RETURN id(n) AS internal_id, labels(n) AS label, properties(n) AS props"
            )
            nodes = await result.data()

            # Map internal Neo4j ID to our generated UUID so we can rewire edges
            id_to_uuid = {}
            new_nodes = []

            for n in nodes:
                internal_id = n["internal_id"]
                old_label = n["label"][0] if n["label"] else "Concept"
                props = dict(n["props"])

                # Generate a strict UUID if missing
                if "uuid" not in props or not props["uuid"]:
                    new_uuid = str(uuid.uuid4())
                    props["uuid"] = new_uuid
                else:
                    new_uuid = props["uuid"]

                id_to_uuid[internal_id] = new_uuid

                # Map the label
                new_label = LABEL_MAP.get(old_label, "Concept")

                # Enforce required Swarm-Grade properties
                if "memory_type" not in props:
                    props["memory_type"] = "semantic"
                if "promotion_score" not in props:
                    props["promotion_score"] = 1.0  # High baseline for imported static data

                new_nodes.append(
                    {"old_id": internal_id, "uuid": new_uuid, "label": new_label, "props": props}
                )

            logger.info(f"Prepared {len(new_nodes)} nodes for schema alignment.")

            # 2. Fetch all legacy edges
            result = await session.run(
                "MATCH (a)-[r]->(b) RETURN id(a) AS source, id(b) AS target, type(r) AS type, properties(r) AS props"
            )
            edges = await result.data()

            new_edges = []
            for e in edges:
                source_internal = e["source"]
                target_internal = e["target"]
                old_type = e["type"]

                new_type = EDGE_MAP.get(old_type, "USES_CONCEPT")

                # We need the generated UUIDs to link them
                source_uuid = id_to_uuid.get(source_internal)
                target_uuid = id_to_uuid.get(target_internal)

                if source_uuid and target_uuid:
                    new_edges.append(
                        {
                            "source_uuid": source_uuid,
                            "target_uuid": target_uuid,
                            "type": new_type,
                            "props": dict(e["props"]),
                        }
                    )

            logger.info(f"Prepared {len(new_edges)} edges for schema alignment.")

            # 3. DESTROY LEGACY GRAPH DESTRUCTIVELY
            logger.info("🔥 Wiping the legacy graph for a clean slate rebuild...")
            await session.run("MATCH (n) DETACH DELETE n")

            # 4. Initialize Constraints safely!
            logger.info("Setting up strict UUID constraints...")
            constraints = [
                "CREATE CONSTRAINT agent_uuid IF NOT EXISTS FOR (n:Agent) REQUIRE n.uuid IS UNIQUE",
                "CREATE CONSTRAINT concept_uuid IF NOT EXISTS FOR (n:Concept) REQUIRE n.uuid IS UNIQUE",
                "CREATE CONSTRAINT episode_uuid IF NOT EXISTS FOR (n:Episode) REQUIRE n.uuid IS UNIQUE",
                "CREATE CONSTRAINT procedure_uuid IF NOT EXISTS FOR (n:Procedure) REQUIRE n.uuid IS UNIQUE",
            ]
            for c in constraints:
                try:
                    await session.run(c)
                except Exception as e:
                    logger.warning(f"Constraint setup warning (may already exist): {e}")

            # 5. Insert compliant Nodes
            logger.info("Inserting Swarm-Grade compliant nodes...")
            for n in new_nodes:
                q = f"CREATE (node:{n['label']}) SET node = $props"
                await session.run(q, props=n["props"])

            # 6. Insert compliant Edges
            logger.info("Inserting Swarm-Grade compliant edges...")
            for e in new_edges:
                q = (
                    "MATCH (a), (b) WHERE a.uuid = $source_uuid AND b.uuid = $target_uuid "
                    f"CREATE (a)-[r:{e['type']}]->(b) "
                    "SET r = $props"
                )
                await session.run(
                    q, source_uuid=e["source_uuid"], target_uuid=e["target_uuid"], props=e["props"]
                )

            # 7. Final Sanity Check
            logger.info("Migration Complete. Verifying live graph status...")
            res = await session.run("MATCH (n) RETURN labels(n) AS label, count(n) AS count")
            final_nodes = await res.data()
            print("\n🚨 FINAL GRAPH NODES 🚨")
            for fn in final_nodes:
                lbl = fn["label"][0] if fn["label"] else "NoLabel"
                print(f"- {lbl}: {fn['count']}")

    except Exception as e:
        logger.error(f"Migration failed! Database may be in partial state: {e}")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
