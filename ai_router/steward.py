# ============================================================
# Knowledge Graph Steward Service
# Purpose: Validate, Repair, and Report AI Model Graph Health
# ============================================================

from neo4j import GraphDatabase
from datetime import datetime
import json
import os
import logging

# ----------------------------
# Configuration
# ----------------------------

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "config.json",
)

# ----------------------------
# Logging
# ----------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [STEWARD] %(levelname)s: %(message)s",
)
logger = logging.getLogger("graph_steward")

# ----------------------------
# Validation Queries
# ----------------------------

VALIDATION_QUERIES = {
    # --- Node Health ---
    "orphan_models": """
        MATCH (m:Model)
        WHERE NOT (m)-[:HAS_CAPABILITY]->() AND NOT (m)-[:FILLS_ROLE]->()
        RETURN count(m) AS count, collect(m.name) AS items
    """,
    "orphan_capabilities": """
        MATCH (c:Capability)
        WHERE NOT ()<-[:HAS_CAPABILITY]-(c) AND NOT ()-[:REQUIRES]->(c)
        RETURN count(c) AS count, collect(c.name) AS items
    """,
    "orphan_traits": """
        MATCH (t:CognitiveTrait)
        WHERE NOT ()-[:EXHIBITS_TRAIT]->(t)
        RETURN count(t) AS count, collect(t.name) AS items
    """,
    "orphan_roles": """
        MATCH (r:SystemRole)
        WHERE NOT ()-[:FILLS_ROLE]->(r)
        RETURN count(r) AS count, collect(r.name) AS items
    """,
    # --- Schema Integrity ---
    "models_without_capabilities": """
        MATCH (m:Model)
        WHERE NOT (m)-[:HAS_CAPABILITY]->()
        RETURN count(m) AS count, collect(m.name) AS items
    """,
    "models_without_roles": """
        MATCH (m:Model)
        WHERE NOT (m)-[:FILLS_ROLE]->()
        RETURN count(m) AS count, collect(m.name) AS items
    """,
    "tasks_without_requirements": """
        MATCH (t:TaskCategory)
        WHERE NOT (t)-[:REQUIRES]->()
        RETURN count(t) AS count, collect(t.name) AS items
    """,
    # --- Duplicates ---
    "duplicate_model_names": """
        MATCH (m:Model)
        WITH m.name AS name, count(m) AS c
        WHERE c > 1
        RETURN count(name) AS count, collect(name) AS items
    """,
    "duplicate_capability_names": """
        MATCH (c:Capability)
        WITH c.name AS name, count(c) AS c
        WHERE c > 1
        RETURN count(name) AS count, collect(name) AS items
    """,
    # --- Capability Gap Analysis ---
    "capability_gaps": """
        MATCH (tc:TaskCategory)-[:REQUIRES]->(c:Capability)
        WHERE NOT (:Model)-[:HAS_CAPABILITY]->(c)
        RETURN count(DISTINCT c) AS count, collect(DISTINCT c.name) AS items
    """,
    # --- Completeness ---
    "total_nodes": """
        MATCH (n)
        WITH labels(n)[0] AS label, count(n) AS c
        RETURN count(label) AS count, collect(label + ': ' + toString(c)) AS items
    """,
    "total_relationships": """
        MATCH ()-[r]->()
        WITH type(r) AS rtype, count(r) AS c
        RETURN count(rtype) AS count, collect(rtype + ': ' + toString(c)) AS items
    """,
}

THRESHOLDS = {
    "orphan_models": 0,
    "orphan_capabilities": 0,
    "orphan_traits": 0,
    "orphan_roles": 0,
    "models_without_capabilities": 0,
    "models_without_roles": 0,
    "tasks_without_requirements": 0,
    "duplicate_model_names": 0,
    "duplicate_capability_names": 0,
    "capability_gaps": 0,
}

# ----------------------------
# Repair Queries
# ----------------------------

REPAIR_QUERIES = [
    # 1. Deduplicate models by name
    """
    MATCH (m:Model)
    WITH m.name AS name, collect(m) AS nodes
    WHERE size(nodes) > 1
    WITH nodes[0] AS keep, nodes[1..] AS dupes
    UNWIND dupes AS d
    WITH keep, d
    CALL {
        WITH keep, d
        MATCH (d)-[r]->()
        WITH keep, d, collect(r) AS rels
        UNWIND rels AS r
        WITH keep, d, r, endNode(r) AS target, type(r) AS rtype
        CALL apoc.merge.relationship(keep, rtype, {}, {}, target) YIELD rel
        RETURN count(rel) AS merged
    }
    DETACH DELETE d
    RETURN count(d) AS removed
    """,
]

# Simpler dedup without APOC (fallback)
REPAIR_QUERIES_SIMPLE = [
    """
    MATCH (m:Model)
    WITH m.name AS name, collect(m) AS nodes
    WHERE size(nodes) > 1
    WITH name, nodes[0] AS keep, nodes[1..] AS dupes
    UNWIND dupes AS d
    DETACH DELETE d
    RETURN name, count(d) AS removed
    """,
]


# ----------------------------
# Main Logic
# ----------------------------


class GraphSteward:
    def __init__(self, uri=None, user=None, password=None):
        self.driver = GraphDatabase.driver(
            uri or NEO4J_URI,
            auth=(user or NEO4J_USER, password or NEO4J_PASSWORD),
        )
        self._config_models = None

    def close(self):
        self.driver.close()

    def _load_config_models(self):
        """Load model list from agent ecosystem config.json."""
        if self._config_models is not None:
            return self._config_models
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            models = []
            for node in config.get("nodes", []):
                models.extend(node.get("capabilities", {}).get("models", []))
            self._config_models = list(set(models))
            return self._config_models
        except Exception as e:
            logger.warning("Could not load config.json: %s", e)
            return []

    def run_validation(self):
        """Run all validation checks and return a health report."""
        logger.info("Starting graph validation...")
        report = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "issues": {},
            "summary": {"total_checks": 0, "passed": 0, "failed": 0},
        }

        with self.driver.session() as session:
            for check_name, query in VALIDATION_QUERIES.items():
                try:
                    result = session.run(query)
                    record = result.single()
                    count = record["count"] if record else 0
                    items = record["items"] if record else []

                    report["checks"][check_name] = {
                        "count": count,
                        "items": items[:10],  # cap for display
                    }

                    threshold = THRESHOLDS.get(check_name, -1)
                    if threshold >= 0 and count > threshold:
                        report["issues"][check_name] = count
                        report["summary"]["failed"] += 1
                        logger.warning("❌ %s: %d issues — %s", check_name, count, items[:5])
                    else:
                        report["summary"]["passed"] += 1
                        logger.info("✅ %s: %d", check_name, count)

                except Exception as e:
                    logger.error("Error running %s: %s", check_name, e)
                    report["checks"][check_name] = {"error": str(e)}
                    report["summary"]["failed"] += 1

                report["summary"]["total_checks"] += 1

        return report

    def check_config_sync(self):
        """Find models in config.json that are missing from Neo4j."""
        config_models = self._load_config_models()
        if not config_models:
            return {"missing_in_graph": [], "missing_in_config": []}

        with self.driver.session() as session:
            result = session.run("MATCH (m:Model) RETURN m.name AS name")
            graph_models = [r["name"] for r in result]

        missing_in_graph = [m for m in config_models if m not in graph_models]
        missing_in_config = [m for m in graph_models if m not in config_models]

        if missing_in_graph:
            logger.warning("Models in config.json but missing from Neo4j: %s", missing_in_graph)
        if missing_in_config:
            logger.info("Models in Neo4j but not in config.json: %s", missing_in_config)

        return {
            "missing_in_graph": missing_in_graph,
            "missing_in_config": missing_in_config,
        }

    def sync_models_from_config(self):
        """Create Model nodes for models in config.json that are missing from Neo4j."""
        sync = self.check_config_sync()
        missing = sync["missing_in_graph"]

        if not missing:
            logger.info("All config models are in Neo4j. Nothing to sync.")
            return []

        created = []
        with self.driver.session() as session:
            from raphael.ai_router.embedding_client import EmbeddingClient
            import asyncio

            router = EmbeddingClient()

            for model_name in missing:
                # Infer properties from the name
                is_local = ":cloud" not in model_name
                provider = (
                    model_name.split(":")[0].split("-")[0] if "-" in model_name else "unknown"
                )
                size_str = model_name.split(":")[-1] if ":" in model_name else ""

                # Fetch embedding via KNOWLEDGE layer
                try:
                    vector = asyncio.run(router.embed(model_name, layer="knowledge"))
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for {model_name}: {e}")
                    vector = []

                session.run(
                    """
                    MERGE (m:Model {name: $name})
                    SET m.provider = $provider,
                        m.local = $local,
                        m.embedding = $vector,
                        m.synced_from_config = true,
                        m.synced_at = datetime()
                    """,
                    name=model_name,
                    provider=provider,
                    local=is_local,
                    vector=vector,
                )
                created.append(model_name)
                logger.info("Created Model node: %s", model_name)

        return created

    def run_repairs(self):
        """Run repair queries to fix detected issues."""
        logger.info("Starting repairs...")
        with self.driver.session() as session:
            for i, query in enumerate(REPAIR_QUERIES_SIMPLE):
                try:
                    logger.info("Running repair %d...", i + 1)
                    result = session.run(query)
                    summary = result.consume()
                    logger.info("Repair %d complete. Counters: %s", i + 1, summary.counters)
                except Exception as e:
                    logger.error("Repair %d failed: %s", i + 1, e)

    def full_health_check(self):
        """Run complete health check: validate → sync → repair → re-validate."""
        logger.info("=" * 60)
        logger.info("FULL GRAPH HEALTH CHECK")
        logger.info("=" * 60)

        # 1. Validate
        report = self.run_validation()

        # 2. Check config sync
        sync = self.check_config_sync()
        report["config_sync"] = sync

        # 3. Auto-repair if issues found
        if report["issues"]:
            logger.warning("Issues found: %s — initiating repairs", report["issues"])
            self.run_repairs()

            # 4. Sync missing models
            if sync["missing_in_graph"]:
                created = self.sync_models_from_config()
                report["synced_models"] = created

            # 5. Re-validate
            logger.info("Re-validating after repairs...")
            post_report = self.run_validation()
            report["post_repair"] = post_report

            remaining = post_report["issues"]
            if remaining:
                logger.error("Issues persist: %s", remaining)
            else:
                logger.info("✅ Graph health restored!")
        else:
            logger.info("✅ Graph is healthy. No repairs needed.")

        logger.info("=" * 60)
        return report


def main():
    steward = GraphSteward()
    try:
        report = steward.full_health_check()
        print(json.dumps(report, indent=2, default=str))
    except Exception as e:
        logger.error("Fatal error: %s", e)
    finally:
        steward.close()


if __name__ == "__main__":
    main()
