"""
One-shot import fixer for Raphael.
Converts broken src.raphael.* and raphael.* imports to the correct flat paths.
Run from the project root:  python scripts/fix_imports.py
"""

import os
import re

# ── Translation table (order matters — specific before general) ───────────────
REPLACEMENTS = [
    # Special cases: src.raphael.core.* that don't live under core/
    ("event_bus.event_bus",    "event_bus.event_bus"),
    ("data.schemas",      "data.schemas"),

    # Special cases: src.raphael.memory.* with non-obvious locations
    ("core.memory.episodic_memory.episodic_memory",  "core.memory.episodic_memory.episodic_memory"),
    ("core.memory.knowledge_graph.operational_kg",   "core.memory.knowledge_graph.operational_kg"),
    ("core.research.research_kg",      "core.research.research_kg"),
    ("core.memory.semantic_memory.vector_store",     "core.memory.semantic_memory.vector_store"),
    ("ai_router.working_memory",   "ai_router.working_memory"),

    # src.raphael.X  →  actual top-level / core sub-package
    ("core.civilization",  "core.civilization"),
    ("core.cognitive",     "core.cognitive"),
    ("core.environment",   "core.environment"),
    ("core.evaluation",    "core.evaluation"),
    ("core.execution",     "core.execution"),
    ("core.learning",      "core.learning"),
    ("core.perception",    "core.perception"),
    ("core.research",      "core.research"),
    ("core.strategy",      "core.strategy"),
    ("core.understanding", "core.understanding"),
    ("agents",        "agents"),
    ("ai_router",     "ai_router"),
    ("spine",         "spine"),
    ("swarm",         "swarm"),

    # raphael.core.bus / models / planning (no such dirs exist)
    ("event_bus.event_bus",              "event_bus.event_bus"),
    ("event_bus.redis_bus",              "event_bus.redis_bus"),
    ("core.understanding.schemas",                "core.understanding.schemas"),
    ("core.planner.resource_manager",  "core.planner.resource_manager"),
    ("core.planner.sandbox",           "core.planner.sandbox"),

    # raphael.X  →  flat top-level packages
    ("agents",    "agents"),
    ("ai_router", "ai_router"),
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    ".git", ".venv", ".uv-venv", ".uv_cache", ".voice-venv", "venv",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".next", ".npm-cache",
}


def fix_content(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def process_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()
    fixed = fix_content(original)
    if fixed != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(fixed)
        return True
    return False


def main():
    changed = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".py"):
                fpath = os.path.join(dirpath, fname)
                if process_file(fpath):
                    changed.append(os.path.relpath(fpath, ROOT))

    print(f"Fixed imports in {len(changed)} files:")
    for p in sorted(changed):
        print(f"  {p}")


if __name__ == "__main__":
    main()
