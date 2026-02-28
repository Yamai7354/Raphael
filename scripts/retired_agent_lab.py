import argparse
import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DESKTOP = Path.home() / "Desktop"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


def prefix_bucket(name: str) -> str:
    parts = [p for p in name.split("_") if p]
    if len(parts) >= 2:
        return "_".join(parts[:2])
    return parts[0] if parts else "misc"


def tokenize(name: str) -> set[str]:
    return {p.lower() for p in name.replace("-", "_").split("_") if p}


def load_retired_agents() -> list[dict[str, Any]]:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (a:Agent)
                WHERE a.status = 'Retired'
                RETURN a.name AS name,
                       coalesce(a.role, 'unknown') AS role,
                       coalesce(a.fitness, 45.0) AS fitness,
                       coalesce(a.retired_reason, 'retired') AS retired_reason
                ORDER BY a.name
                """
            ).data()
    finally:
        driver.close()

    out = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "role": str(row.get("role") or "unknown"),
                "fitness": float(row.get("fitness") or 45.0),
                "retired_reason": str(row.get("retired_reason") or "retired"),
            }
        )
    return out


def build_social_edges(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: dict[tuple[str, str], float] = {}
    by_role: defaultdict[str, list[str]] = defaultdict(list)
    by_prefix: defaultdict[str, list[str]] = defaultdict(list)

    for a in agents:
        by_role[a["role"]].append(a["name"])
        by_prefix[prefix_bucket(a["name"])].append(a["name"])

    def add_edge(a: str, b: str, weight: float):
        if a == b:
            return
        key = (a, b) if a < b else (b, a)
        edges[key] = max(edges.get(key, 0.0), weight)

    for group in by_prefix.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                add_edge(group[i], group[j], 0.88)

    for group in by_role.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                add_edge(group[i], group[j], 0.62)

    names = [a["name"] for a in agents]
    tokens = {name: tokenize(name) for name in names}
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            overlap = len(tokens[a].intersection(tokens[b]))
            if overlap >= 2:
                add_edge(a, b, min(0.95, 0.45 + overlap * 0.1))

    return [
        {"source": k[0], "target": k[1], "weight": round(v, 3)}
        for k, v in sorted(edges.items(), key=lambda item: item[1], reverse=True)
    ]


def run_evolution(agents: list[dict[str, Any]], edges: list[dict[str, Any]], rounds: int = 24) -> dict[str, Any]:
    rng = random.Random(42)
    states = {
        a["name"]: {
            "adaptability": rng.uniform(0.35, 0.75),
            "cooperation": rng.uniform(0.3, 0.8),
            "novelty": rng.uniform(0.25, 0.85),
            "fitness": max(10.0, min(100.0, float(a["fitness"]))),
            "role": a["role"],
        }
        for a in agents
    }

    neighbors: defaultdict[str, list[tuple[str, float]]] = defaultdict(list)
    for e in edges:
        s, t, w = e["source"], e["target"], float(e["weight"])
        neighbors[s].append((t, w))
        neighbors[t].append((s, w))

    timeline = []
    for step in range(1, rounds + 1):
        for name, st in states.items():
            cohort = neighbors.get(name, [])
            if cohort:
                peer_score = sum(states[n]["fitness"] * w for n, w in cohort) / max(1e-6, sum(w for _, w in cohort))
            else:
                peer_score = st["fitness"]

            drift = rng.uniform(-1.6, 2.3)
            cooperation_boost = st["cooperation"] * 1.8
            novelty_risk = (st["novelty"] - 0.5) * rng.uniform(-2.5, 2.5)
            adaptation = (peer_score - st["fitness"]) * 0.06 * st["adaptability"]

            st["fitness"] = max(1.0, min(100.0, st["fitness"] + drift + cooperation_boost + novelty_risk + adaptation))
            st["adaptability"] = max(0.05, min(0.99, st["adaptability"] + rng.uniform(-0.03, 0.04)))
            st["cooperation"] = max(0.05, min(0.99, st["cooperation"] + rng.uniform(-0.03, 0.03)))
            st["novelty"] = max(0.05, min(0.99, st["novelty"] + rng.uniform(-0.05, 0.04)))

        avg_fitness = sum(s["fitness"] for s in states.values()) / max(1, len(states))
        timeline.append({"step": step, "avg_fitness": round(avg_fitness, 2)})

    ranked = sorted(
        [
            {
                "name": name,
                "role": st["role"],
                "fitness": round(st["fitness"], 2),
                "adaptability": round(st["adaptability"], 3),
                "cooperation": round(st["cooperation"], 3),
                "novelty": round(st["novelty"], 3),
            }
            for name, st in states.items()
        ],
        key=lambda x: x["fitness"],
        reverse=True,
    )

    return {"timeline": timeline, "ranked": ranked, "rounds": rounds}


def build_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload)
    template = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Retired Agent Lab</title>
  <style>
    body {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background:#0b1020; color:#e5ecff; margin:0; }}
    .wrap {{ display:grid; grid-template-columns: 1.4fr 1fr; gap:12px; padding:12px; }}
    .card {{ background:#121a33; border:1px solid #24325d; border-radius:12px; padding:12px; }}
    #graph {{ width:100%; height:72vh; border-radius:10px; background:#0a132b; }}
    h1,h2 {{ margin:0 0 8px; font-size:14px; letter-spacing:0.08em; text-transform:uppercase; }}
    .small {{ font-size:11px; opacity:0.8; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    th,td {{ border-bottom:1px solid #24325d; padding:6px; text-align:left; }}
    .pill {{ display:inline-block; padding:3px 7px; border:1px solid #4461b2; border-radius:999px; font-size:11px; margin-right:6px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <h1>Retired Agent Society Graph</h1>
      <div id=\"graph\"></div>
    </div>
    <div class=\"card\">
      <h2>Evolution Snapshot</h2>
      <div id=\"summary\" class=\"small\"></div>
      <h2 style=\"margin-top:10px\">Top Emergent Agents</h2>
      <table><thead><tr><th>Agent</th><th>Role</th><th>Fitness</th></tr></thead><tbody id=\"rows\"></tbody></table>
      <h2 style=\"margin-top:10px\">Role Clusters</h2>
      <div id=\"roles\" class=\"small\"></div>
    </div>
  </div>
  <script>
  const DATA = __DATA__;
  const canvas = document.createElement('canvas');
  const holder = document.getElementById('graph');
  holder.appendChild(canvas);
  canvas.width = holder.clientWidth; canvas.height = holder.clientHeight;
  const ctx = canvas.getContext('2d');
  const nodes = DATA.nodes.map((n,i)=>({{...n, x:(Math.cos(i*0.7)*220)+canvas.width/2, y:(Math.sin(i*0.7)*220)+canvas.height/2}}));
  const nodeById = Object.fromEntries(nodes.map(n=>[n.id,n]));
  const edges = DATA.edges;
  function draw() {{
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.globalAlpha = 0.35;
    ctx.strokeStyle = '#7ea1ff';
    edges.forEach(e=>{{
      const a=nodeById[e.source], b=nodeById[e.target]; if(!a||!b) return;
      ctx.lineWidth = Math.max(0.5, e.weight*2.2);
      ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
    }});
    ctx.globalAlpha = 1;
    nodes.forEach(n=>{{
      const rad = 6 + Math.max(0, (n.fitness||40)-40)/18;
      ctx.fillStyle = n.status==='Retired' ? '#f59e0b' : '#6ee7b7';
      ctx.beginPath(); ctx.arc(n.x,n.y,rad,0,Math.PI*2); ctx.fill();
      ctx.fillStyle = '#dbe7ff';
      ctx.font = '10px ui-monospace';
      ctx.fillText(n.label, n.x + rad + 2, n.y + 3);
    }});
  }}
  draw();

  const top = DATA.evolution.ranked.slice(0,12);
  document.getElementById('summary').innerHTML = `
    <span class=\"pill\">Agents: ${DATA.nodes.length}</span>
    <span class=\"pill\">Links: ${DATA.edges.length}</span>
    <span class=\"pill\">Rounds: ${DATA.evolution.rounds}</span>
    <span class=\"pill\">Avg Fitness End: ${DATA.evolution.timeline.at(-1)?.avg_fitness ?? 'n/a'}</span>
  `;
  document.getElementById('rows').innerHTML = top.map(t=>`<tr><td>${t.name}</td><td>${t.role}</td><td>${t.fitness}</td></tr>`).join('');
  const roleCounts = DATA.nodes.reduce((acc,n)=>{{acc[n.role]=(acc[n.role]||0)+1; return acc;}},{{}});
  document.getElementById('roles').innerHTML = Object.entries(roleCounts).map(([k,v])=>`<div>${k}: ${v}</div>`).join('');
  </script>
</body>
</html>
"""
    return template.replace("__DATA__", data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build lightweight retired-agent lab outputs")
    parser.add_argument("--rounds", type=int, default=24)
    parser.add_argument("--desktop-dir", default=str(DEFAULT_DESKTOP))
    args = parser.parse_args()

    agents = load_retired_agents()
    if not agents:
        print(json.dumps({"ok": False, "error": "No retired agents found in Neo4j"}, indent=2))
        return

    edges = build_social_edges(agents)
    evolution = run_evolution(agents, edges, rounds=max(4, args.rounds))

    nodes = [
        {
            "id": a["name"],
            "label": a["name"],
            "role": a["role"],
            "fitness": a["fitness"],
            "status": "Retired",
            "retired_reason": a["retired_reason"],
            "bucket": prefix_bucket(a["name"]),
        }
        for a in agents
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
        "evolution": evolution,
        "stats": {
            "agent_count": len(nodes),
            "edge_count": len(edges),
            "role_distribution": Counter(n["role"] for n in nodes),
            "bucket_distribution": Counter(n["bucket"] for n in nodes),
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lab_json = DATA_DIR / "retired_agent_lab.json"
    lab_report = DATA_DIR / "retired_agent_lab_report.json"
    lab_json.write_text(json.dumps(payload, indent=2))

    report = {
        "ok": True,
        "generated_at": payload["generated_at"],
        "agent_count": payload["stats"]["agent_count"],
        "edge_count": payload["stats"]["edge_count"],
        "top_emergent": evolution["ranked"][:10],
        "ending_avg_fitness": evolution["timeline"][-1]["avg_fitness"],
        "notes": [
            "This lab is file-backed and CPU-light; no persistent simulation process is running.",
            "Use this export to prototype relationships before promoting changes to the primary graph.",
        ],
    }
    lab_report.write_text(json.dumps(report, indent=2))

    desktop_dir = Path(args.desktop_dir).expanduser().resolve()
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop_html = desktop_dir / "retired-agent-lab.html"
    desktop_json = desktop_dir / "retired-agent-lab.json"
    desktop_html.write_text(build_html(payload))
    desktop_json.write_text(json.dumps(payload, indent=2))

    print(
        json.dumps(
            {
                "ok": True,
                "outputs": {
                    "lab_json": str(lab_json),
                    "lab_report": str(lab_report),
                    "desktop_html": str(desktop_html),
                    "desktop_json": str(desktop_json),
                },
                "summary": {
                    "retired_agents": len(nodes),
                    "edges": len(edges),
                    "ending_avg_fitness": evolution["timeline"][-1]["avg_fitness"],
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
