# swarm_optimizer_agent.py
# Improves routing decisions in the knowledge graph

import os
import random
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def update_model_performance():
    with driver.session() as session:
        results = session.run("""
        MATCH (m:Model)-[:RUNS_ON]->(machine:Machine)
        RETURN m.name AS model, machine.id AS machine
        """)

        for record in results:
            tokens_per_sec = random.randint(10, 80)

            session.run(
                """
            MERGE (p:PerformanceProfile {model:$model, machine:$machine})
            SET p.tokens_per_sec = $speed,
                p.last_updated = timestamp()
            """,
                model=record["model"],
                machine=record["machine"],
                speed=tokens_per_sec,
            )


def rebalance_cluster():
    with driver.session() as session:
        session.run("""
        MATCH (machine:Machine)
        WHERE machine.cpu_usage > 85
        SET machine.status = "overloaded"
        """)


def optimize_routing_scores():
    with driver.session() as session:
        session.run("""
        MATCH (m:Model)-[r:HAS_CAPABILITY]->(c:Capability)
        MATCH (p:PerformanceProfile {model:m.name})
        SET r.score = p.tokens_per_sec / 100.0
        """)


def main():
    update_model_performance()
    rebalance_cluster()
    optimize_routing_scores()


if __name__ == "__main__":
    main()
