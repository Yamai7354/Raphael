# swarm_self_healing_controller.py

import os
from neo4j import GraphDatabase
import time

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def detect_dead_nodes():
    with driver.session() as session:
        session.run("""
        MATCH (m:Machine)
        WHERE timestamp() - m.last_seen > 15000
        SET m.status = "offline"
        """)


def detect_gpu_overload():
    with driver.session() as session:
        session.run("""
        MATCH (g:Hardware)
        WHERE g.type = "GPU" AND g.utilization > 95
        SET g.overloaded = true
        """)


def rebalance_cluster():
    with driver.session() as session:
        session.run("""
        MATCH (m:Machine)
        WHERE m.cpu_usage < 30
        SET m.status = "available"
        """)


def main():
    while True:
        detect_dead_nodes()
        detect_gpu_overload()
        rebalance_cluster()
        time.sleep(10)


if __name__ == "__main__":
    main()
