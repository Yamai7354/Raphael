# swarm_telemetry_agent.py
# Reports machine + model metrics to Neo4j

import os
import time
import socket
import psutil
import requests
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

NODE_ID = socket.gethostname()
OLLAMA_URL = "http://100.125.58.22:5000"


driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def get_system_metrics():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_total": psutil.virtual_memory().total // (1024**3),
    }


def get_models():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags")
        return r.json().get("models", [])
    except:
        return []


def update_graph(metrics, models):
    with driver.session() as session:
        session.run(
            """
        MERGE (m:Machine {id:$node_id})
        SET m.last_seen = timestamp(),
            m.cpu_usage = $cpu,
            m.ram_usage = $ram
        """,
            node_id=NODE_ID,
            cpu=metrics["cpu_percent"],
            ram=metrics["ram_percent"],
        )

        for model in models:
            session.run(
                """
            MERGE (mod:Model {name:$model})
            MERGE (mach:Machine {id:$node})
            MERGE (mod)-[:RUNS_ON]->(mach)
            """,
                model=model["name"],
                node=NODE_ID,
            )


def main_loop():
    while True:
        metrics = get_system_metrics()
        models = get_models()

        update_graph(metrics, models)

        time.sleep(5)


if __name__ == "__main__":
    main_loop()
