#!/usr/bin/env python3
"""
Router Agent — Map capabilities from agents.yaml to capabilities.json.
Run this to refresh the capability map after editing config/agents.yaml.
Output: data/capabilities.json (by_agent, by_capability).
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
AGENTS_YAML = ROOT / "config" / "agents.yaml"
OUTPUT_JSON = ROOT / "data" / "capabilities.json"


def main():
    try:
        import yaml
    except ImportError:
        print("PyYAML required: pip install pyyaml")
        return 1
    if not AGENTS_YAML.exists():
        print(f"Registry not found: {AGENTS_YAML}")
        return 1
    with open(AGENTS_YAML) as f:
        data = yaml.safe_load(f) or {}
    agents = data.get("agents", {})
    by_agent: dict[str, list[str]] = {}
    by_capability: dict[str, list[str]] = {}
    for agent_id, spec in agents.items():
        if not isinstance(spec, dict):
            continue
        caps = list(spec.get("capabilities") or [])
        caps = [c for c in caps if c]
        by_agent[agent_id] = caps
        for c in caps:
            by_capability.setdefault(c, []).append(agent_id)
    out = {
        "_comment": "Router Agent capability map. Generated from config/agents.yaml.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "by_agent": by_agent,
        "by_capability": by_capability,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(by_agent)} agents, {len(by_capability)} capabilities -> {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
