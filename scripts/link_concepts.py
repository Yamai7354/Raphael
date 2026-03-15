#!/usr/bin/env python3
import os
import asyncio
import logging
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LinkConcepts")


async def link_concepts():
    """
    1. Maps Concept:system_role to Agent
    2. Maps Concept:cognitive_trait to Agent
    3. Maps Concept:capability to Agent
    4. Maps Concept:intelligence_type to Agent and TaskType
    5. Maps Concept:system_role to TaskType
    """
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Zr65oJYpg")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async with driver.session() as session:
        logger.info("Wiring Concept:system_role to Agent")
        await session.run("""
            MATCH (a:Agent), (c:Concept {concept_type: 'system_role'})
            WITH a, c ORDER BY rand()
            WITH a, collect(c)[0] as role
            MERGE (a)-[:USES_CONCEPT]->(role)
        """)

        logger.info("Wiring Concept:cognitive_trait to Agent")
        await session.run("""
            MATCH (a:Agent), (c:Concept {concept_type: 'cognitive_trait'})
            WITH a, c ORDER BY rand()
            WITH a, collect(c)[0..2] as traits
            UNWIND traits as trait
            MERGE (a)-[:HAS_TRAIT]->(trait)
        """)

        logger.info("Wiring Concept:capability to Agent")
        await session.run("""
            MATCH (a:Agent), (c:Concept {concept_type: 'capability'})
            WITH a, c ORDER BY rand()
            WITH a, collect(c)[0..3] as caps
            UNWIND caps as cap
            MERGE (a)-[:USES_CONCEPT]->(cap)
        """)

        logger.info("Wiring Concept:intelligence_type to Agent")
        await session.run("""
            MATCH (a:Agent), (c:Concept {concept_type: 'intelligence_type'})
            WITH a, c ORDER BY rand()
            WITH a, collect(c)[0] as intel
            MERGE (a)-[:USES_CONCEPT]->(intel)
        """)

        logger.info("Wiring Concept:intelligence_type to TaskType")
        await session.run("""
            MATCH (t:TaskType), (c:Concept {concept_type: 'intelligence_type'})
            WITH t, c ORDER BY rand()
            WITH t, collect(c)[0..2] as intels
            UNWIND intels as intel
            MERGE (t)-[:USES_CONCEPT]->(intel)
        """)

        logger.info("Wiring Concept:system_role to TaskType")
        await session.run("""
            MATCH (t:TaskType), (c:Concept {concept_type: 'system_role'})
            WITH t, c ORDER BY rand()
            WITH t, collect(c)[0..2] as roles
            UNWIND roles as role
            MERGE (t)-[:USES_CONCEPT]->(role)
        """)

        logger.info("Concept Wiring Complete.")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(link_concepts())
