import json
import os
import random
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "data" / "agents.json"
STATS_PATH = PROJECT_ROOT / "public" / "stats.json"
REPORT_PATH = PROJECT_ROOT / "data" / "model_sync_report.json"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
LMSTUDIO_BASE = os.getenv("OLLAMA_LOCAL_URL", "http://100.125.58.22:5000").rstrip("/")

TASK_MODEL_POLICY = {
    "exploration": ["l3-8b-stheno", "stheno", "ministral"],
    "validation": ["ministral", "l3-8b-stheno", "stheno"],
    "experiment": ["ministral", "l3-8b-stheno", "stheno"],
    "communication": ["l3-8b-stheno", "stheno", "ministral"],
}


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _dedupe_preserve(models: list[str]):
    seen = set()
    out = []
    for model in models:
        if model not in seen:
            seen.add(model)
            out.append(model)
    return out


def list_ollama_models():
    # Prefer LM Studio OpenAI-compatible model listing.
    try:
        response = httpx.get(f"{LMSTUDIO_BASE}/v1/models", timeout=8.0)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        models = [str(row.get("id", "")).strip() for row in rows if isinstance(row, dict)]
        models = [m for m in models if m]
        if models:
            return _dedupe_preserve(models)
    except Exception:
        pass

    # Fallback to local ollama CLI for compatibility.
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
    lines = [ln.rstrip() for ln in result.stdout.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return []
    models = []
    for line in lines[1:]:
        model = line.split()[0].strip()
        if model:
            models.append(model)
    return _dedupe_preserve(models)


def classify_model(name: str):
    n = name.lower()
    return {
        "is_embedding": "embed" in n or "embedding" in n or "bge-" in n,
        "is_cloud": ":cloud" in n,
        "is_vision": "moondream" in n,
        "is_speech": "whisper" in n,
        "is_coder": "coder" in n,
        "is_reasoning": "l3-8b-stheno" in n or "stheno" in n or "ministral" in n,
    }


def pick_model_for_role(role: str, candidates: list[str], fallback: str):
    role_lc = (role or "").lower()
    if not candidates:
        return fallback

    priority_patterns = []
    if "creative" in role_lc or "coder" in role_lc:
        priority_patterns = [r"ministral", r"stheno", r"l3-8b-stheno"]
    elif "research" in role_lc or "analyst" in role_lc or "explorer" in role_lc:
        priority_patterns = [r"stheno", r"l3-8b-stheno", r"ministral"]
    elif "communicator" in role_lc:
        priority_patterns = [r"stheno", r"l3-8b-stheno", r"ministral"]
    elif "graph" in role_lc or "database" in role_lc or "resource" in role_lc or "optimizer" in role_lc:
        priority_patterns = [r"ministral", r"stheno", r"l3-8b-stheno"]
    else:
        priority_patterns = [r"stheno", r"l3-8b-stheno", r"ministral"]

    for pat in priority_patterns:
        for model in candidates:
            if re.search(pat, model, re.IGNORECASE):
                return model

    return random.choice(candidates)


def pick_model_for_task(task_name: str, candidates: list[str], fallback: str):
    patterns = TASK_MODEL_POLICY.get(task_name, [])
    for pat in patterns:
        for model in candidates:
            if pat in model.lower():
                return model
    return fallback


def sync_models_to_neo4j(models: list[str], agent_assignments: dict[str, str], task_assignments: dict[str, str]):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    links = 0
    try:
        with driver.session() as session:
            for model in models:
                meta = classify_model(model)
                session.run(
                    """
                    MERGE (m:Model {name: $name})
                    SET m.is_embedding = $is_embedding,
                        m.is_cloud = $is_cloud,
                        m.is_vision = $is_vision,
                        m.is_speech = $is_speech,
                        m.is_coder = $is_coder,
                        m.is_reasoning = $is_reasoning,
                        m.updated_at = datetime()
                    """,
                    name=model,
                    **meta,
                )

            for agent, chosen in agent_assignments.items():
                session.run(
                    """
                    MATCH (a:Agent {name: $agent})
                    OPTIONAL MATCH (a)-[old:PREFERS_MODEL]->(:Model)
                    DELETE old
                    WITH a
                    MATCH (pref:Model {name: $chosen})
                    MERGE (a)-[:PREFERS_MODEL]->(pref)
                    """,
                    agent=agent,
                    chosen=chosen,
                )
                links += 1

                for model in models:
                    session.run(
                        """
                        MATCH (a:Agent {name: $agent}), (m:Model {name: $model})
                        MERGE (a)-[:CAN_USE_MODEL]->(m)
                        """,
                        agent=agent,
                        model=model,
                    )
                    links += 1

            for agent, chosen in agent_assignments.items():
                session.run(
                    """
                    MATCH (a:Agent {name: $agent})-[:PLAYS_ROLE]->(r:Role)
                    MATCH (m:Model {name: $chosen})
                    MERGE (r)-[:BEST_FOR]->(m)
                    """,
                    agent=agent,
                    chosen=chosen,
                )
            for task_name, chosen in task_assignments.items():
                session.run(
                    """
                    MERGE (t:TaskType {name: $task_name})
                    WITH t
                    MATCH (m:Model {name: $chosen})
                    MERGE (t)-[:BEST_FOR]->(m)
                    """,
                    task_name=task_name,
                    chosen=chosen,
                )
    finally:
        driver.close()

    return links


def apply_assignments_to_files(assignments: dict[str, str]):
    registry = load_json(REGISTRY_PATH, {"agents": []})
    stats = load_json(STATS_PATH, {"agents": [], "feed": [], "resources": []})

    changed_registry = 0
    changed_stats = 0

    for agent in registry.get("agents", []):
        name = str(agent.get("name", "")).strip()
        if name in assignments:
            agent["model"] = assignments[name]
            changed_registry += 1

    for agent in stats.get("agents", []):
        name = str(agent.get("name", "")).strip()
        if name in assignments:
            agent["model"] = assignments[name]
            changed_stats += 1

    save_json(REGISTRY_PATH, registry)
    save_json(STATS_PATH, stats)
    return changed_registry, changed_stats


def main():
    models = list_ollama_models()
    if not models:
        report = {"ok": False, "error": "No Ollama models found"}
        save_json(REPORT_PATH, report)
        print(json.dumps(report, indent=2))
        return

    # Non-embedding models for task agents.
    usable = [
        m
        for m in models
        if not classify_model(m)["is_embedding"]
        and not classify_model(m)["is_vision"]
        and not classify_model(m)["is_speech"]
    ]
    fallback = usable[0] if usable else models[0]

    registry = load_json(REGISTRY_PATH, {"agents": []})
    assignments = {}
    for agent in registry.get("agents", []):
        name = str(agent.get("name", "")).strip()
        role = str(agent.get("role", ""))
        if not name:
            continue
        assignments[name] = pick_model_for_role(role, usable, fallback)
    task_assignments = {
        task_name: pick_model_for_task(task_name, usable, fallback) for task_name in TASK_MODEL_POLICY
    }

    changed_registry, changed_stats = apply_assignments_to_files(assignments)
    neo_links = sync_models_to_neo4j(models, assignments, task_assignments)

    report = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_count": len(models),
        "usable_model_count": len(usable),
        "models": models,
        "assignments": assignments,
        "task_assignments": task_assignments,
        "task_policy": TASK_MODEL_POLICY,
        "changed_registry_agents": changed_registry,
        "changed_stats_agents": changed_stats,
        "neo4j_links_touched": neo_links,
    }

    save_json(REPORT_PATH, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
