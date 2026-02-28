import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
REGISTRY_PATH = PROJECT_ROOT / "data" / "agents.json"
STATS_PATH = PROJECT_ROOT / "public" / "stats.json"
REPORT_PATH = PROJECT_ROOT / "data" / "kg_reconcile_report.json"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

SKIP_DIRS = {
    ".git",
    ".next",
    "node_modules",
    ".venv",
    "venv",
    ".uv-venv",
    "__pycache__",
    "dist",
    "build",
    "coverage",
    ".npm-cache",
}


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def discover_agent_file_names(root: Path) -> set[str]:
    out: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            if filename.endswith("_agent.py") or filename in {
                "agent.py",
                "planner_agent.py",
                "evaluator_agent.py",
                "auditor_agent.py",
                "portfolio_agent.py",
            }:
                stem = filename[:-3]
                out.add(stem)
    return out


def discover_skill_names(root: Path) -> set[str]:
    skills_dir = root / ".agents" / "skills"
    if not skills_dir.exists():
        return set()
    return {p.parent.name for p in skills_dir.glob("*/SKILL.md")}


def discover_tool_names(root: Path) -> set[str]:
    tools = {
        "Terminal",
        "Profiler",
        "Scheduler",
        "Cypher",
        "Graph Metrics",
        "SQL Explain",
        "Metrics API",
        "Alert Manager",
        "Template Engine",
        "Graph Analyzer",
        "Embedding Matcher",
        "Backup Runner",
        "Redis CLI",
        "Cache Monitor",
    }

    pattern = re.compile(r'"tools?"\s*:\s*\[(.*?)\]', re.IGNORECASE | re.DOTALL)
    entry = re.compile(r'"([^\"]{2,60})"')

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if not filename.endswith((".py", ".json", ".ts", ".tsx")):
                continue
            if "tool" not in filename and filename not in {"package.json", "agents.json"}:
                continue
            fp = Path(dirpath) / filename
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for block in pattern.findall(text):
                for item in entry.findall(block):
                    if len(item.strip()) >= 2:
                        tools.add(item.strip())
            if filename in {"tools.py", "tool_router.py"}:
                tools.add(fp.stem)

    clean = {t for t in tools if t and len(t) <= 80}
    return clean


def retire_inefficient_from_files(registry: dict, stats: dict):
    retired = []

    def should_retire(agent: dict) -> bool:
        name = normalize_name(str(agent.get("name", "")))
        fitness = float(agent.get("fitness") or 0)
        if name.lower().startswith("test") and fitness < 60:
            return True
        return False

    for collection in (registry.get("agents", []), stats.get("agents", [])):
        for agent in collection:
            if not isinstance(agent, dict):
                continue
            agent["name"] = normalize_name(str(agent.get("name", "")))
            if should_retire(agent):
                agent["status"] = "Retired"
                agent["retired_reason"] = "Inefficient test profile"
                retired.append(agent["name"])

    return sorted(set(retired))


def reconcile_graph(registry_agents, file_agents, skills, tools):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    all_agent_names = {normalize_name(a.get("name", "")) for a in registry_agents if isinstance(a, dict)}
    all_agent_names.update(file_agents)
    all_agent_names = {a for a in all_agent_names if a}

    role_counts = defaultdict(int)
    retired_graph = []

    with driver.session() as session:
        session.run(
            """
            MERGE (c:Catalog {name: 'Repo Inventory'})
            SET c.updated_at = datetime()
            """
        )

        for agent in registry_agents:
            if not isinstance(agent, dict):
                continue
            name = normalize_name(str(agent.get("name", "")))
            role = normalize_name(str(agent.get("role", "Generalist"))) or "Generalist"
            status = normalize_name(str(agent.get("status", "Cataloged"))) or "Cataloged"
            fitness = float(agent.get("fitness") or 0)
            role_counts[role] += 1

            session.run(
                """
                MERGE (a:Agent {name: $name})
                SET a.role = $role,
                    a.status = $status,
                    a.fitness = $fitness,
                    a.active = CASE WHEN $status = 'Retired' THEN false ELSE true END,
                    a.updated_at = datetime(),
                    a.source = 'registry'
                MERGE (r:Role {name: $role})
                MERGE (a)-[:PLAYS_ROLE]->(r)
                MERGE (c:Catalog {name: 'Repo Inventory'})
                MERGE (c)-[:HAS_AGENT]->(a)
                """,
                name=name,
                role=role,
                status=status,
                fitness=fitness,
            )

        for stem in sorted(file_agents):
            session.run(
                """
                MERGE (a:Agent {name: $name})
                ON CREATE SET a.status = 'Cataloged', a.source = 'repo_file', a.active = true, a.created_at = datetime()
                SET a.last_seen = datetime()
                MERGE (c:Catalog {name: 'Repo Inventory'})
                MERGE (c)-[:HAS_AGENT]->(a)
                """,
                name=stem,
            )

        for skill in sorted(skills):
            session.run(
                """
                MERGE (s:Skill {name: $name})
                SET s.source = 'skill_catalog', s.updated_at = datetime()
                MERGE (c:Catalog {name: 'Repo Inventory'})
                MERGE (c)-[:HAS_SKILL]->(s)
                """,
                name=skill,
            )

        for tool in sorted(tools):
            session.run(
                """
                MERGE (t:Tool {name: $name})
                SET t.source = 'tool_catalog', t.updated_at = datetime()
                MERGE (c:Catalog {name: 'Repo Inventory'})
                MERGE (c)-[:HAS_TOOL]->(t)
                """,
                name=tool,
            )

        for agent in registry_agents:
            if not isinstance(agent, dict):
                continue
            name = normalize_name(str(agent.get("name", "")))
            for skill in skills:
                session.run(
                    """
                    MATCH (a:Agent {name: $agent}), (s:Skill {name: $skill})
                    MERGE (a)-[:CAN_USE_SKILL]->(s)
                    """,
                    agent=name,
                    skill=skill,
                )

        rows = session.run(
            """
            MATCH (a:Agent)
            WITH a, COUNT { (a)--() } AS degree
            WHERE degree = 0 OR (a.name STARTS WITH 'project_sorter_' OR a.name STARTS WITH 'portfolio_')
            RETURN a.name AS name, degree
            """
        ).data()

        for row in rows:
            name = row["name"]
            if name in all_agent_names:
                continue
            session.run(
                """
                MATCH (a:Agent {name: $name})
                SET a.status = 'Retired',
                    a.active = false,
                    a.retired_reason = 'Stale or floating graph-only agent',
                    a.retired_at = datetime()
                """,
                name=name,
            )
            retired_graph.append(name)

        counts = {}
        for label in ("Agent", "Skill", "Tool", "Role"):
            counts[label.lower()] = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]

    driver.close()
    return counts, sorted(set(retired_graph)), dict(sorted(role_counts.items()))


def main():
    registry = load_json(REGISTRY_PATH, {"agents": []})
    stats = load_json(STATS_PATH, {"agents": [], "resources": [], "feed": []})

    retired_from_files = retire_inefficient_from_files(registry, stats)
    save_json(REGISTRY_PATH, registry)
    save_json(STATS_PATH, stats)

    file_agents = discover_agent_file_names(WORKSPACE_ROOT)
    skills = discover_skill_names(WORKSPACE_ROOT)
    tools = discover_tool_names(WORKSPACE_ROOT)

    counts, retired_graph, role_counts = reconcile_graph(registry.get("agents", []), file_agents, skills, tools)

    report = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inventory": {
            "registry_agents": len(registry.get("agents", [])),
            "repo_agent_files": len(file_agents),
            "skills": len(skills),
            "tools": len(tools),
        },
        "graph_counts": counts,
        "roles": role_counts,
        "retired": {
            "from_registry_or_stats": retired_from_files,
            "from_graph": retired_graph,
        },
    }

    save_json(REPORT_PATH, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
