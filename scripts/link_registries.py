#!/usr/bin/env python3
import os
import yaml
import uuid
import asyncio
import logging
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LinkRegistries")


async def remap_graph():
    """
    1. Renames all 'Tool' nodes with a 'provider' (the injected models) to 'Model'
    2. Injects 'Skill' nodes from data/skills.yaml
    3. Injects 'Tool' nodes from core/execution/tools.py instances
    4. Randomly links Agent -> Model -> Skill -> Tool -> TaskType
    """
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Zr65oJYpg")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    # -- SKILL DICTIONARY --
    skills_path = "/Users/yamai/ai/Raphael/data/skills.yaml"
    skills_data = []
    if os.path.exists(skills_path):
        with open(skills_path, "r") as f:
            yaml_content = yaml.safe_load(f)
            skills_data = yaml_content.get("skills", [])

    # -- TOOL REGISTRY --
    # From core/execution/tools.py we have BashExecutionTool and PythonExecutionTool
    # We will register them.
    tools_data = [
        {"name": "bash_execute", "description": "Executes a sterile bash command."},
        {
            "name": "python_execute",
            "description": "Executes a raw python string script in a sandbox.",
        },
        {"name": "search_web", "description": "Search the web for real-time information."},
        {"name": "read_file", "description": "Read contents of local files."},
    ]

    async with driver.session() as session:
        # STEP 1: Rename 'Tool' to 'Model' for the old models.csv injections
        logger.info("Migrating old 'Tool' nodes to 'Model' nodes...")
        await session.run("""
            MATCH (t:Tool) 
            WHERE t.provider IS NOT NULL OR t.sizeGB IS NOT NULL 
            SET t:Model 
            REMOVE t:Tool
        """)

        # STEP 2: Inject Skills from YAML
        logger.info("Injecting Skills from skills.yaml...")
        for s in skills_data:
            name = s.get("name")
            if not name:
                continue

            res = await session.run(
                "MATCH (sk:Skill {name: $name}) RETURN sk.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            new_uuid = (
                record["existing_uuid"]
                if (record and record["existing_uuid"])
                else str(uuid.uuid4())
            )

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "name": name,
                "category": s.get("category", ""),
                "description": s.get("description", ""),
            }
            await session.run(
                "MERGE (sk:Skill {name: $name}) SET sk += $props", name=name, props=props
            )

        # STEP 3: Inject Tools
        logger.info("Injecting Tool registry instances...")
        for t in tools_data:
            name = t["name"]
            res = await session.run(
                "MATCH (tool:Tool {name: $name}) RETURN tool.uuid AS existing_uuid", name=name
            )
            record = await res.single()
            new_uuid = (
                record["existing_uuid"]
                if (record and record["existing_uuid"])
                else str(uuid.uuid4())
            )

            props = {
                "uuid": new_uuid,
                "memory_type": "semantic",
                "promotion_score": 1.0,
                "name": name,
                "description": t["description"],
            }
            await session.run(
                "MERGE (tool:Tool {name: $name}) SET tool += $props", name=name, props=props
            )

        # STEP 4: Build The Reasoning Chain
        logger.info(
            "Building relational Reasoning Chains: (Agent)->(Model)->(Skill)->(Tool)->(TaskType)"
        )

        # A. Agent -> Model (Random 1:1 mapping for the 61 agents)
        # Using WITH and rand() to assign a model to every agent so they aren't floating.
        await session.run("""
            MATCH (a:Agent)
            MATCH (m:Model)
            WITH a, m ORDER BY rand()
            WITH a, collect(m)[0] AS selected_model
            MERGE (a)-[:USES_MODEL]->(selected_model)
        """)

        # B. Model -> Skill (Each model gets ~5 random skills)
        await session.run("""
            MATCH (m:Model)
            MATCH (s:Skill)
            WITH m, s ORDER BY rand()
            WITH m, collect(s)[0..5] AS skills
            UNWIND skills AS skill
            MERGE (m)-[:HAS_SKILL]->(skill)
        """)

        # C. Skill -> Tool (Each skill uses 1-2 random tools to accomplish its goal)
        await session.run("""
            MATCH (s:Skill)
            MATCH (t:Tool)
            WITH s, t ORDER BY rand()
            WITH s, collect(t)[0..2] AS tools
            UNWIND tools AS tool
            MERGE (s)-[:USES_TOOL]->(tool)
        """)

        # D. Tool -> TaskType (Each tool maps to a few Task Categories where it's useful)
        await session.run("""
            MATCH (t:Tool)
            MATCH (tt:TaskType)
            WITH t, tt ORDER BY rand()
            WITH t, collect(tt)[0..3] AS tasks
            UNWIND tasks AS task
            MERGE (t)-[:FOR_TASK]->(task)
        """)

        # E. Ensure Models also retain their Concept ties from earlier.
        # (Already exists because we only changed the Label to Model, the edges still exist).

        logger.info("Ontology Mapping Complete.")

        res = await session.run("MATCH (n) RETURN labels(n) AS label, count(n) AS count")
        print("\n🚨 FINAL GRAPH NODES AFTER CHAIN BUILDING 🚨")
        for fn in await res.data():
            lbl = fn["label"][0] if fn["label"] else "NoLabel"
            print(f"- {lbl}: {fn['count']}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(remap_graph())
