import json
import logging
import os
import time
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stats_exporter")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")
OUTPUT_PATH = "/Users/yamai/ai/Raphael/swarm-dashboard/public/stats.json"


def get_stats():
    data = {"timestamp": time.time(), "resources": [], "agents": [], "feed": []}

    try:
        with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS)) as driver:
            with driver.session() as session:
                # 1. Get Resources
                resource_query = """
                MATCH (m:Machine)
                OPTIONAL MATCH (m)-[:HAS_HARDWARE]->(h:Hardware {type: 'GPU'})
                RETURN m.name AS name, m.cpu_usage AS cpu, m.ram_usage AS ram, h.utilization AS vram
                """
                res = session.run(resource_query)
                for record in res:
                    data["resources"].append(record.data())

                # 2. Get Agents
                agent_query = """
                MATCH (a:Agent)
                OPTIONAL MATCH (a)-[:USES_MODEL]->(m:Model)
                RETURN a.name AS name, a.role AS role, a.status AS status, m.name AS model
                """
                res = session.run(agent_query)
                for record in res:
                    agent_data = record.data()
                    if not agent_data["status"]:
                        agent_data["status"] = "Idle"
                    data["agents"].append(agent_data)

                # 3. Get Cognitive Feed (Tasks/Observations)
                feed_query = """
                MATCH (o:Observation)
                RETURN o.timestamp AS time, o.summary AS summary, 'Observation' AS type
                ORDER BY o.timestamp DESC LIMIT 10
                UNION
                MATCH (t:Task)
                RETURN t.id AS time, t.description AS summary, 'Task' AS type
                ORDER BY time DESC LIMIT 10
                """
                res = session.run(feed_query)
                for record in res:
                    data["feed"].append(record.data())

    except Exception as e:
        logger.error(f"Failed to fetch stats from Neo4j: {e}")
        data["error"] = str(e)

    return data


def main():
    logger.info("Exporting swarm stats...")
    stats = get_stats()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(stats, f, indent=2)

    logger.info(f"Stats exported to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
