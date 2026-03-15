"""
Sync models from multiple LLM nodes to the agent registry and Neo4j graph.

Supports two registry types:
  - desktop-node (LM Studio) at OLLAMA_DESKTOP_URL → OpenAI /v1/models
  - mac-node     (Ollama)     at OLLAMA_MAC_URL     → Ollama /api/tags

Pinned embedding models are never reassigned:
  Desktop: text-embedding-bge-large-en-v1.5, text-embedding-bge-small-en-v1.5
  Mac:     vishalraj/nomic-embed-code:latest
"""

import json
import os
import random
import re
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

# ---------------------------------------------------------------------------
# Per-node configuration
# ---------------------------------------------------------------------------
NODES = [
    {
        "id": "win-desktop",
        "name": "R9 Desktop (LM Studio)",
        "registry_type": "lmstudio",
        "base_url": os.getenv("OLLAMA_DESKTOP_URL", "http://100.125.58.22:5000").rstrip("/"),
        "pinned_models": [
            "text-embedding-bge-large-en-v1.5",
            "text-embedding-bge-small-en-v1.5",
        ],
    },
    {
        "id": "mac-local",
        "name": "M4 MacBook (Ollama)",
        "registry_type": "ollama",
        "base_url": os.getenv("OLLAMA_MAC_URL", "http://localhost:11434").rstrip("/"),
        "pinned_models": [
            "vishalraj/nomic-embed-code:latest",
        ],
    },
]

TASK_MODEL_POLICY = {
    "exploration": ["l3-8b-stheno", "stheno", "ministral"],
    "validation": ["ministral", "l3-8b-stheno", "stheno"],
    "experiment": ["ministral", "l3-8b-stheno", "stheno"],
    "communication": ["l3-8b-stheno", "stheno", "ministral"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Registry-specific model listing
# ---------------------------------------------------------------------------


def _list_lmstudio_models(base_url: str) -> list[str]:
    """LM Studio: OpenAI-compatible GET /v1/models."""
    try:
        response = httpx.get(f"{base_url}/v1/models", timeout=8.0)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        models = [str(row.get("id", "")).strip() for row in rows if isinstance(row, dict)]
        return [m for m in models if m]
    except Exception as e:
        print(f"  ⚠ Failed to list LM Studio models at {base_url}: {e}")
        return []


def _list_ollama_models(base_url: str) -> list[str]:
    """Ollama: GET /api/tags."""
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=8.0)
        response.raise_for_status()
        payload = response.json()
        model_list = payload.get("models", []) if isinstance(payload, dict) else []
        models = [str(m.get("name", "")).strip() for m in model_list if isinstance(m, dict)]
        return [m for m in models if m]
    except Exception as e:
        print(f"  ⚠ Failed to list Ollama models at {base_url}: {e}")
        return []


def list_node_models(node: dict) -> list[str]:
    """Query a single node using its native registry API."""
    if node["registry_type"] == "lmstudio":
        models = _list_lmstudio_models(node["base_url"])
    elif node["registry_type"] == "ollama":
        models = _list_ollama_models(node["base_url"])
    else:
        print(f"  ⚠ Unknown registry_type: {node['registry_type']}")
        models = []
    return _dedupe_preserve(models)


# ---------------------------------------------------------------------------
# Model classification & selection (unchanged logic)
# ---------------------------------------------------------------------------


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
    elif (
        "graph" in role_lc
        or "database" in role_lc
        or "resource" in role_lc
        or "optimizer" in role_lc
    ):
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


# ---------------------------------------------------------------------------
# Neo4j sync
# ---------------------------------------------------------------------------


def sync_models_to_neo4j(
    all_models: list[dict],
    agent_assignments: dict[str, str],
    task_assignments: dict[str, str],
):
    """Write model nodes and agent/task relationships into Neo4j."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    links = 0
    try:
        with driver.session() as session:
            # Create / update model nodes with source_node tag
            for entry in all_models:
                model = entry["model"]
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
                        m.source_node = $source_node,
                        m.registry_type = $registry_type,
                        m.updated_at = datetime()
                    """,
                    name=model,
                    source_node=entry["source_node"],
                    registry_type=entry["registry_type"],
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

                for entry in all_models:
                    session.run(
                        """
                        MATCH (a:Agent {name: $agent}), (m:Model {name: $model})
                        MERGE (a)-[:CAN_USE_MODEL]->(m)
                        """,
                        agent=agent,
                        model=entry["model"],
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


# ---------------------------------------------------------------------------
# File sync (agents.json / stats.json)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 60)
    print("Multi-Node Model Sync")
    print("=" * 60)

    # 1. Discover models from each node (using the correct API per registry)
    all_models: list[dict] = []  # {"model": str, "source_node": str, "registry_type": str}
    all_pinned: set[str] = set()

    for node in NODES:
        print(f"\n→ Querying {node['name']} ({node['registry_type']}) at {node['base_url']}")
        models = list_node_models(node)
        print(f"  Found {len(models)} models: {models}")

        for m in models:
            all_models.append(
                {
                    "model": m,
                    "source_node": node["id"],
                    "registry_type": node["registry_type"],
                }
            )

        all_pinned.update(node["pinned_models"])

    if not all_models:
        report = {"ok": False, "error": "No models found on any node"}
        save_json(REPORT_PATH, report)
        print(json.dumps(report, indent=2))
        return

    # 2. Build usable model list (exclude embeddings, vision, speech, and pinned models)
    usable = [
        entry["model"]
        for entry in all_models
        if not classify_model(entry["model"])["is_embedding"]
        and not classify_model(entry["model"])["is_vision"]
        and not classify_model(entry["model"])["is_speech"]
        and entry["model"] not in all_pinned
    ]
    usable = _dedupe_preserve(usable)
    fallback = usable[0] if usable else all_models[0]["model"]

    print(f"\n✓ Usable (swappable) models: {usable}")
    print(f"  Pinned (never reassigned): {sorted(all_pinned)}")

    # 3. Assign models to agents
    registry = load_json(REGISTRY_PATH, {"agents": []})
    assignments = {}
    for agent in registry.get("agents", []):
        name = str(agent.get("name", "")).strip()
        role = str(agent.get("role", ""))
        if not name:
            continue
        assignments[name] = pick_model_for_role(role, usable, fallback)

    task_assignments = {
        task_name: pick_model_for_task(task_name, usable, fallback)
        for task_name in TASK_MODEL_POLICY
    }

    # 4. Apply
    changed_registry, changed_stats = apply_assignments_to_files(assignments)
    neo_links = sync_models_to_neo4j(all_models, assignments, task_assignments)

    report = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes_queried": [
            {
                "id": node["id"],
                "name": node["name"],
                "registry_type": node["registry_type"],
                "model_count": sum(1 for e in all_models if e["source_node"] == node["id"]),
            }
            for node in NODES
        ],
        "total_model_count": len(all_models),
        "usable_model_count": len(usable),
        "pinned_models": sorted(all_pinned),
        "models": [e["model"] for e in all_models],
        "model_sources": {e["model"]: e["source_node"] for e in all_models},
        "assignments": assignments,
        "task_assignments": task_assignments,
        "task_policy": TASK_MODEL_POLICY,
        "changed_registry_agents": changed_registry,
        "changed_stats_agents": changed_stats,
        "neo4j_links_touched": neo_links,
    }

    save_json(REPORT_PATH, report)
    print(f"\n{'=' * 60}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
