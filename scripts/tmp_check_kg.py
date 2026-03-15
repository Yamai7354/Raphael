import os
import asyncio
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase


async def check_kg():
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Zr65oJYpg")

    try:
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        print("--- Neo4j KG Analysis ---")

        async with driver.session() as session:
            # Check Nodes
            result = await session.run("MATCH (n) RETURN labels(n) AS label, count(n) AS count")
            nodes = await result.data()
            print("\nNodes:")
            for no in nodes:
                # labels(n) returns a list, format it nicely
                lbl = no["label"][0] if no["label"] else "NoLabel"
                print(f"- {lbl}: {no['count']}")

            # Check Edges
            result = await session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count")
            edges = await result.data()
            print("\nRelationships:")
            for ed in edges:
                print(f"- {ed['type']}: {ed['count']}")

            # Look for legacy un-constrained nodes (missing uuid)
            result = await session.run(
                "MATCH (n) WHERE n.uuid IS NULL RETURN count(n) AS missing_uuid"
            )
            missing_uuid = await result.single()
            print(
                f"\nNodes missing 'uuid' property: {missing_uuid['missing_uuid'] if missing_uuid else 0}"
            )

        await driver.close()
    except Exception as e:
        print(f"Failed to connect or query Neo4j: {e}")


if __name__ == "__main__":
    asyncio.run(check_kg())
