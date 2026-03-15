#!/usr/bin/env python3
import os
import csv
import uuid
import asyncio
import logging
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ImportSwarmCSVs")


def safe_read_csv(filepath):
    """Reads a CSV safely, skipping the first row if it's just a rogue filename header."""
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        return []

    # Detect if the first line is just the filename or missing commas
    first_line = lines[0].strip()
    if "," not in first_line and ".csv" in first_line:
        lines = lines[1:]  # skip the bad header

    reader = csv.DictReader(lines)
    return list(reader)


async def import_csvs():
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Zr65oJYpg")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    base_path = "/Users/yamai/Documents/neo4j/import/"

    # 1. Read files
    models_raw = safe_read_csv(os.path.join(base_path, "models.csv"))
    capabilities_raw = safe_read_csv(os.path.join(base_path, "capabilities.csv"))
    traits_raw = safe_read_csv(os.path.join(base_path, "cognitive_traits.csv"))
    roles_raw = safe_read_csv(os.path.join(base_path, "system_roles.csv"))
    intel_raw = safe_read_csv(os.path.join(base_path, "Intelligence_types.csv"))
    tasks_raw = safe_read_csv(os.path.join(base_path, "task_catagories.csv"))

    # Edges
    model_cap_raw = safe_read_csv(os.path.join(base_path, "model_capabilites.csv"))
    model_traits_raw = safe_read_csv(os.path.join(base_path, "model_traits.csv"))
    model_roles_raw = safe_read_csv(os.path.join(base_path, "model_roles.csv"))
    task_cap_raw = safe_read_csv(os.path.join(base_path, "task_capability_requirements.csv"))
    model_compat_raw = safe_read_csv(os.path.join(base_path, "model_compatibility.csv"))

    # ID translation dictionary (maps 'm1' -> Swarm-Grade UUID)
    id_map = {}

    logger.info("Generating proper UUIDs and validating Nodes...")

    async with driver.session() as session:
        # A. Insert Tool Nodes (from models.csv)
        for row in models_raw:
            old_id = row["modelId"]
            name = row.get("name", "")

            # Check if Tool already exists by name
            res = await session.run(
                "MATCH (t:Tool {name: $name}) RETURN t.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            if record and record["existing_uuid"]:
                new_uuid = record["existing_uuid"]
            else:
                new_uuid = str(uuid.uuid4())

            id_map[old_id] = new_uuid

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "name": name,
                "provider": row.get("provider", ""),
                "type": row.get("type", ""),
                "local": row.get("local", "false").lower() == "true",
                "sizeGB": float(row.get("sizeGB", 0.0)),
                "serverNode": row.get("serverNode", "mac"),
            }
            await session.run(
                "MERGE (t:Tool {name: $name}) SET t += $props", name=name, props=props
            )

        # B. Insert Concept Nodes (capabilities)
        for row in capabilities_raw:
            old_id = row.get("capabilityId", row.get("id"))
            name = row.get("name", "")
            if not old_id:
                continue

            res = await session.run(
                "MATCH (c:Concept {name: $name}) RETURN c.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            if record and record["existing_uuid"]:
                new_uuid = record["existing_uuid"]
            else:
                new_uuid = str(uuid.uuid4())

            id_map[old_id] = new_uuid

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "concept_type": "capability",
                "name": name,
            }
            await session.run(
                "MERGE (c:Concept {name: $name}) SET c += $props", name=name, props=props
            )

        # C. Insert Concept Nodes (traits)
        for row in traits_raw:
            old_id = row.get("traitId", row.get("id"))
            name = row.get("name", "")
            if not old_id:
                continue

            res = await session.run(
                "MATCH (c:Concept {name: $name}) RETURN c.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            if record and record["existing_uuid"]:
                new_uuid = record["existing_uuid"]
            else:
                new_uuid = str(uuid.uuid4())

            id_map[old_id] = new_uuid

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "concept_type": "cognitive_trait",
                "name": name,
            }
            await session.run(
                "MERGE (c:Concept {name: $name}) SET c += $props", name=name, props=props
            )

        # D. Insert Concept Nodes (roles)
        for row in roles_raw:
            old_id = row.get("roleId", row.get("id"))
            name = row.get("name", "")
            if not old_id:
                continue

            res = await session.run(
                "MATCH (c:Concept {name: $name}) RETURN c.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            if record and record["existing_uuid"]:
                new_uuid = record["existing_uuid"]
            else:
                new_uuid = str(uuid.uuid4())

            id_map[old_id] = new_uuid

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "concept_type": "system_role",
                "name": name,
            }
            await session.run(
                "MERGE (c:Concept {name: $name}) SET c += $props", name=name, props=props
            )

        # E. Insert Concept Nodes (intelligence types)
        for row in intel_raw:
            old_id = row.get("intelligenceId", row.get("id"))
            name = row.get("name", "")
            if not old_id:
                continue

            res = await session.run(
                "MATCH (c:Concept {name: $name}) RETURN c.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            if record and record["existing_uuid"]:
                new_uuid = record["existing_uuid"]
            else:
                new_uuid = str(uuid.uuid4())

            id_map[old_id] = new_uuid

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "concept_type": "intelligence_type",
                "name": name,
            }
            await session.run(
                "MERGE (c:Concept {name: $name}) SET c += $props", name=name, props=props
            )

        # F. Insert TaskType Nodes
        for row in tasks_raw:
            old_id = row.get("taskId", row.get("id"))
            name = row.get("name", "")
            if not old_id:
                continue

            res = await session.run(
                "MATCH (t:TaskType {name: $name}) RETURN t.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            if record and record["existing_uuid"]:
                new_uuid = record["existing_uuid"]
            else:
                new_uuid = str(uuid.uuid4())

            id_map[old_id] = new_uuid

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "name": name,
                "domain": row.get("domain", ""),
                "cognitiveLoad": row.get("cognitiveLoad", ""),
                "executionType": row.get("executionType", ""),
            }
            await session.run(
                "MERGE (t:TaskType {name: $name}) SET t += $props", name=name, props=props
            )
        logger.info("Nodes injected successfully. Building relationship mapping logic...")

        # LINK: Tool -> Capability (USES_CONCEPT)
        for row in model_cap_raw:
            m_uuid = id_map.get(row.get("modelId"))
            c_uuid = id_map.get(row.get("capabilityId"))
            if m_uuid and c_uuid:
                await session.run(
                    "MATCH (a:Tool), (b:Concept) WHERE a.uuid=$m_uuid AND b.uuid=$c_uuid MERGE (a)-[r:USES_CONCEPT]->(b)",
                    m_uuid=m_uuid,
                    c_uuid=c_uuid,
                )

        # LINK: Tool -> Trait (HAS_TRAIT)
        for row in model_traits_raw:
            m_uuid = id_map.get(row.get("modelId"))
            t_uuid = id_map.get(row.get("traitId"))
            if m_uuid and t_uuid:
                await session.run(
                    "MATCH (a:Tool), (b:Concept) WHERE a.uuid=$m_uuid AND b.uuid=$t_uuid MERGE (a)-[r:HAS_TRAIT]->(b)",
                    m_uuid=m_uuid,
                    t_uuid=t_uuid,
                )

        # LINK: Tool -> Role (USES_CONCEPT)
        for row in model_roles_raw:
            m_uuid = id_map.get(row.get("modelId"))
            r_uuid = id_map.get(row.get("roleId"))
            if m_uuid and r_uuid:
                await session.run(
                    "MATCH (a:Tool), (b:Concept) WHERE a.uuid=$m_uuid AND b.uuid=$r_uuid MERGE (a)-[r:USES_CONCEPT]->(b)",
                    m_uuid=m_uuid,
                    r_uuid=r_uuid,
                )

        # LINK: TaskType -> Capability (USES_CONCEPT)
        for row in task_cap_raw:
            t_uuid = id_map.get(row.get("taskId"))
            c_uuid = id_map.get(row.get("capabilityId"))
            if t_uuid and c_uuid:
                await session.run(
                    "MATCH (a:TaskType), (b:Concept) WHERE a.uuid=$t_uuid AND b.uuid=$c_uuid MERGE (a)-[r:USES_CONCEPT]->(b)",
                    t_uuid=t_uuid,
                    c_uuid=c_uuid,
                )

        # LINK: Tool -> Tool (WORKS_WITH)
        for row in model_compat_raw:
            m1_uuid = id_map.get(row.get("modelA"))
            m2_uuid = id_map.get(row.get("modelB"))
            rel_type = row.get("relationship", "compatible")
            if m1_uuid and m2_uuid:
                await session.run(
                    "MATCH (a:Tool), (b:Tool) WHERE a.uuid=$m1_uuid AND b.uuid=$m2_uuid MERGE (a)-[r:WORKS_WITH {type: $rel_type}]->(b)",
                    m1_uuid=m1_uuid,
                    m2_uuid=m2_uuid,
                    rel_type=rel_type,
                )

        logger.info("CSV Framework injection into Swarm-Grade Ontology is complete!")

        # Audit Check
        res = await session.run("MATCH (n) RETURN labels(n) AS label, count(n) AS count")
        print("\n🚨 FINAL GRAPH NODES AFTER INJECTION 🚨")
        for fn in await res.data():
            lbl = fn["label"][0] if fn["label"] else "NoLabel"
            print(f"- {lbl}: {fn['count']}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(import_csvs())
