"""
Knowledge Graph — Full Wipe & Rebuild

Drops all data from the neo4j and memory databases, then repopulates
through the Intake Gate to produce a clean, provenance-tagged graph.

Usage:
    python -m scripts.rebuild_kg              # interactive confirmation
    python -m scripts.rebuild_kg --yes        # skip confirmation
    python -m scripts.rebuild_kg --dry-run    # show what would happen
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [REBUILD] %(levelname)s: %(message)s",
)
logger = logging.getLogger("rebuild_kg")

# ── Connection ──────────────────────────────────────────────
URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")

ROOT_DIR = Path(__file__).resolve().parent.parent  # Raphael/

# Databases to wipe (system is read-only, skip it)
DATABASES_TO_WIPE = ["neo4j", "memory"]


def count_nodes(driver, database="neo4j"):
    with driver.session(database=database) as s:
        result = s.run("MATCH (n) RETURN count(n) AS c")
        return result.single()["c"]


def count_relationships(driver, database="neo4j"):
    with driver.session(database=database) as s:
        result = s.run("MATCH ()-[r]->() RETURN count(r) AS c")
        return result.single()["c"]


def wipe_database(driver, database="neo4j"):
    """Recreate the database using CREATE OR REPLACE (Enterprise instant wipe)."""
    logger.info("Recreating database '%s' (CREATE OR REPLACE)...", database)
    with driver.session(database="system") as s:
        s.run(f"CREATE OR REPLACE DATABASE `{database}`")
    # Wait for the database to come online
    import time
    for _ in range(30):
        try:
            with driver.session(database="system") as s:
                result = s.run(
                    "SHOW DATABASE $db YIELD currentStatus RETURN currentStatus",
                    db=database,
                )
                status = result.single()["currentStatus"]
                if status == "online":
                    logger.info("Database '%s' is online.", database)
                    return
        except Exception:
            pass
        time.sleep(1)
    logger.warning("Database '%s' may not be fully online yet.", database)


def rebuild_graph(driver):
    """Run populate + extend through the Intake Gate."""
    from core.knowledge_quality.intake_gate import IntakeGate
    from core.knowledge_quality.skill_dictionary import SkillDictionary
    from core.knowledge_quality.tool_manifest_registry import ToolManifestRegistry
    from core.memory.knowledge_graph.populate_swarm_graph import SwarmGraphIngestor
    from core.memory.knowledge_graph.extend_swarm_graph import SwarmGraphExtender

    gate = IntakeGate(
        driver=driver,
        skill_dictionary=SkillDictionary(),
        tool_manifest_registry=ToolManifestRegistry(),
    )

    # ── Phase 1: Schema + Populate ──────────────────────────
    logger.info("=" * 60)
    logger.info("PHASE 1: Populate (schema, hardware, models, tools, skills)")
    logger.info("=" * 60)

    ingestor = SwarmGraphIngestor(URI, USER, PASSWORD, gate=gate)

    schema_path = ROOT_DIR / "core/memory/knowledge_graph/swarm_architecture_schem.cypher"
    if schema_path.exists():
        ingestor.execute_schema(schema_path)
    else:
        logger.warning("Schema file not found: %s — skipping", schema_path)

    ingestor.ingest_hardware()

    llm_macbook = ROOT_DIR.parent / "agent_ecosystem/local_llm_registry.json"
    llm_desktop = ROOT_DIR.parent / "agent_ecosystem/desktop_llm_registry.json"
    if llm_macbook.exists():
        ingestor.ingest_llm_registry(llm_macbook, "macbook")
    else:
        logger.warning("LLM registry not found: %s", llm_macbook)
    if llm_desktop.exists():
        ingestor.ingest_llm_registry(llm_desktop, "desktop")
    else:
        logger.warning("LLM registry not found: %s", llm_desktop)

    ingestor.discover_tools_and_agents()
    ingestor.discover_skills()
    ingestor.close()

    populate_stats = gate.get_stats()
    logger.info("Populate gate stats: %s", populate_stats)

    # ── Phase 2: Extend (relationships, hierarchy, topology) ──
    logger.info("=" * 60)
    logger.info("PHASE 2: Extend (hierarchy, topology, skill-tool links)")
    logger.info("=" * 60)

    extender = SwarmGraphExtender(URI, USER, PASSWORD, gate=gate)

    evolution_path = ROOT_DIR / "core/memory/knowledge_graph/evolution_schema.cypher"
    if evolution_path.exists():
        extender.execute_schema(evolution_path)
    else:
        logger.warning("Evolution schema not found: %s — skipping", evolution_path)

    extender.implement_hierarchy()
    extender.implement_network_topology()
    extender.implement_skill_tool_links()
    extender.implement_cognitive_pathways()
    # Skip mock learning data in a clean rebuild
    # extender.add_mock_learning_data()
    extender.close()

    final_stats = gate.get_stats()
    logger.info("Final gate stats: %s", final_stats)
    return final_stats


def main():
    parser = argparse.ArgumentParser(description="Wipe and rebuild the Knowledge Graph")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="Show counts without modifying")
    args = parser.parse_args()

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    # Show current state
    print("\n  Current Knowledge Graph State:")
    print("  " + "─" * 40)
    for db in DATABASES_TO_WIPE:
        try:
            nodes = count_nodes(driver, db)
            rels = count_relationships(driver, db)
            print(f"  {db:15s}  {nodes:>8,} nodes  {rels:>8,} relationships")
        except Exception as e:
            print(f"  {db:15s}  (error: {e})")
    print()

    if args.dry_run:
        print("  [dry-run] No changes made.")
        driver.close()
        return

    if not args.yes:
        answer = input("  This will DELETE ALL DATA and rebuild from scratch. Proceed? [y/N] ")
        if answer.lower() not in ("y", "yes"):
            print("  Aborted.")
            driver.close()
            return

    # Wipe
    print()
    for db in DATABASES_TO_WIPE:
        try:
            wipe_database(driver, db)
        except Exception as e:
            logger.error("Failed to wipe '%s': %s", db, e)

    # Rebuild
    print()
    stats = rebuild_graph(driver)

    # Final report
    print("\n  Rebuilt Knowledge Graph:")
    print("  " + "─" * 40)
    for db in DATABASES_TO_WIPE:
        try:
            nodes = count_nodes(driver, db)
            rels = count_relationships(driver, db)
            print(f"  {db:15s}  {nodes:>8,} nodes  {rels:>8,} relationships")
        except Exception:
            pass

    print(f"\n  Gate stats: {stats}")
    print()

    driver.close()


if __name__ == "__main__":
    main()
