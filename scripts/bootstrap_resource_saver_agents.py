import json
import os
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = PROJECT_ROOT / "public" / "stats.json"
REGISTRY_PATH = PROJECT_ROOT / "data" / "agents.json"


RESOURCE_SAVER_AGENTS = [
    {
        "name": "EcoOptimizer",
        "role": "Resource Saver",
        "culture": "System",
        "status": "Executing",
        "model": "deepseek-r1:8b",
        "fitness": 91.2,
        "task_success_rate": 96.0,
        "knowledge_contrib": 14,
        "skills": [
            "CPU Throttling",
            "Process Prioritization",
            "Energy-Aware Scheduling",
        ],
        "tools": ["Terminal", "Profiler", "Scheduler"],
    },
    {
        "name": "CacheGuardian",
        "role": "Resource Saver",
        "culture": "System",
        "status": "Executing",
        "model": "deepseek-r1:8b",
        "fitness": 88.7,
        "task_success_rate": 93.5,
        "knowledge_contrib": 11,
        "skills": [
            "Cache Warmup",
            "Memory Compaction",
            "Request Coalescing",
        ],
        "tools": ["Cache Monitor", "Redis CLI", "Terminal"],
    },
    {
        "name": "CostSentinel",
        "role": "Resource Saver",
        "culture": "System",
        "status": "Executing",
        "model": "deepseek-r1:8b",
        "fitness": 90.4,
        "task_success_rate": 94.8,
        "knowledge_contrib": 12,
        "skills": [
            "Cost Anomaly Detection",
            "Budget Enforcement",
            "Usage Forecasting",
        ],
        "tools": ["Metrics API", "Alert Manager", "Terminal"],
    },
]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def save_json(path: Path, payload) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2))


def upsert_neo4j(agents):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        for agent in agents:
            session.run(
                """
                MERGE (a:Agent {name: $name})
                SET a.role = $role,
                    a.culture = $culture,
                    a.status = $status,
                    a.model = $model,
                    a.fitness = $fitness,
                    a.task_success_rate = $task_success_rate,
                    a.knowledge_contrib = $knowledge_contrib,
                    a.updated_at = datetime()
                """,
                **agent,
            )
            session.run(
                """
                MERGE (r:Role {name: $role})
                WITH r
                MATCH (a:Agent {name: $name})
                MERGE (a)-[:PLAYS_ROLE]->(r)
                """,
                name=agent["name"],
                role=agent["role"],
            )
            for skill in agent["skills"]:
                session.run(
                    """
                    MERGE (s:Skill {name: $skill})
                    WITH s
                    MATCH (a:Agent {name: $name})
                    MERGE (a)-[:HAS_SKILL]->(s)
                    """,
                    name=agent["name"],
                    skill=skill,
                )
            for tool in agent["tools"]:
                session.run(
                    """
                    MERGE (t:Tool {name: $tool})
                    WITH t
                    MATCH (a:Agent {name: $name})
                    MERGE (a)-[:USES_TOOL]->(t)
                    """,
                    name=agent["name"],
                    tool=tool,
                )
    driver.close()


def upsert_registry(agents):
    payload = load_json(REGISTRY_PATH, {"agents": []})
    existing = payload.get("agents", [])
    by_name = {a.get("name"): a for a in existing if isinstance(a, dict)}

    for agent in agents:
        by_name[agent["name"]] = {
            "name": agent["name"],
            "role": agent["role"],
            "culture": agent["culture"],
            "status": agent["status"],
            "model": agent["model"],
            "fitness": agent["fitness"],
            "task_success_rate": agent["task_success_rate"],
            "knowledge_contrib": agent["knowledge_contrib"],
            "source": "registry",
        }

    payload["agents"] = sorted(by_name.values(), key=lambda x: x["name"])
    save_json(REGISTRY_PATH, payload)


def upsert_stats(agents):
    payload = load_json(STATS_PATH, {"timestamp": 0, "resources": [], "agents": [], "feed": []})
    if not isinstance(payload, dict):
        payload = {"timestamp": 0, "resources": [], "agents": [], "feed": []}

    current_agents = payload.get("agents", [])
    by_name = {a.get("name"): a for a in current_agents if isinstance(a, dict)}

    for agent in agents:
        by_name[agent["name"]] = {
            "name": agent["name"],
            "role": agent["role"],
            "culture": agent["culture"],
            "status": "Executing",
            "model": agent["model"],
            "fitness": agent["fitness"],
            "task_success_rate": agent["task_success_rate"],
            "knowledge_contrib": agent["knowledge_contrib"],
        }

    payload["agents"] = sorted(by_name.values(), key=lambda x: x["name"])
    payload["timestamp"] = datetime.now().timestamp()
    feed = payload.get("feed", [])
    if not isinstance(feed, list):
        feed = []
    now = datetime.now().strftime("%H:%M:%S")
    feed.append(
        {
            "time": now,
            "type": "Manual Override",
            "summary": "RESOURCE SAVER AGENTS BOOTSTRAPPED: EcoOptimizer, CacheGuardian, CostSentinel",
        }
    )
    payload["feed"] = feed[-50:]
    if "resources" not in payload or not isinstance(payload["resources"], list):
        payload["resources"] = []
    save_json(STATS_PATH, payload)


def main():
    upsert_neo4j(RESOURCE_SAVER_AGENTS)
    upsert_registry(RESOURCE_SAVER_AGENTS)
    upsert_stats(RESOURCE_SAVER_AGENTS)
    print("Resource saver agents bootstrapped, added to Neo4j, and marked as Executing.")


if __name__ == "__main__":
    main()
