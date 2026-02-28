"""
Graph Optimizer — Analyze and optimize the AI Model Knowledge Graph.

Connects directly to Neo4j (or works with CSV exports) to:
1. Analyze graph structure and density
2. Detect suboptimal patterns
3. Suggest and apply relationship optimizations
4. Export optimized snapshots
"""

import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

logger = logging.getLogger("graph_optimizer")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "config.json",
)


class GraphOptimizer:
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.driver = GraphDatabase.driver(
            uri or NEO4J_URI,
            auth=(user or NEO4J_USER, password or NEO4J_PASSWORD),
        )

    def close(self):
        self.driver.close()

    # ──────────────────────────────────────────────
    # Analysis
    # ──────────────────────────────────────────────

    def analyze_structure(self) -> Dict[str, Any]:
        """Get a full structural analysis of the knowledge graph."""
        report: Dict[str, Any] = {"timestamp": datetime.now().isoformat()}

        with self.driver.session() as session:
            # Node counts by label
            result = session.run("""
                MATCH (n)
                WITH labels(n)[0] AS label, count(n) AS cnt
                RETURN label, cnt ORDER BY cnt DESC
            """)
            report["node_counts"] = {r["label"]: r["cnt"] for r in result}

            # Relationship counts by type
            result = session.run("""
                MATCH ()-[r]->()
                WITH type(r) AS rtype, count(r) AS cnt
                RETURN rtype, cnt ORDER BY cnt DESC
            """)
            report["relationship_counts"] = {r["rtype"]: r["cnt"] for r in result}

            # Connectivity density
            total_nodes = sum(report["node_counts"].values())
            total_rels = sum(report["relationship_counts"].values())
            report["density"] = {
                "total_nodes": total_nodes,
                "total_relationships": total_rels,
                "avg_degree": round(total_rels / max(total_nodes, 1), 2),
            }

            # Model capability coverage
            result = session.run("""
                MATCH (m:Model)
                OPTIONAL MATCH (m)-[:HAS_CAPABILITY]->(c:Capability)
                OPTIONAL MATCH (m)-[:FILLS_ROLE]->(r:SystemRole)
                OPTIONAL MATCH (m)-[:EXHIBITS_TRAIT]->(t:CognitiveTrait)
                RETURN m.name AS model,
                       count(DISTINCT c) AS capabilities,
                       count(DISTINCT r) AS roles,
                       count(DISTINCT t) AS traits
                ORDER BY capabilities DESC
            """)
            report["model_coverage"] = [
                {
                    "model": r["model"],
                    "capabilities": r["capabilities"],
                    "roles": r["roles"],
                    "traits": r["traits"],
                }
                for r in result
            ]

            # Task routing readiness
            result = session.run("""
                MATCH (tc:TaskCategory)-[:REQUIRES]->(c:Capability)
                OPTIONAL MATCH (m:Model)-[:HAS_CAPABILITY]->(c)
                RETURN tc.name AS task,
                       count(DISTINCT c) AS required_capabilities,
                       count(DISTINCT m) AS available_models
                ORDER BY available_models ASC
            """)
            report["task_readiness"] = [
                {
                    "task": r["task"],
                    "required_capabilities": r["required_capabilities"],
                    "available_models": r["available_models"],
                    "status": "ready" if r["available_models"] > 0 else "blocked",
                }
                for r in result
            ]

        return report

    def find_optimization_opportunities(self) -> List[Dict[str, str]]:
        """Identify suboptimal patterns and suggest improvements."""
        suggestions = []

        with self.driver.session() as session:
            # 1. Models with no capabilities
            result = session.run("""
                MATCH (m:Model)
                WHERE NOT (m)-[:HAS_CAPABILITY]->()
                RETURN m.name AS name
            """)
            bare_models = [r["name"] for r in result if r["name"] is not None]
            if bare_models:
                suggestions.append(
                    {
                        "type": "missing_relationships",
                        "priority": "high",
                        "target": "HAS_CAPABILITY",
                        "action": f"Add capability links for: {', '.join(str(m) for m in bare_models[:5])}",
                        "affected": len(bare_models),
                    }
                )

            # 2. Capabilities required by tasks but no model provides
            result = session.run("""
                MATCH (tc:TaskCategory)-[:REQUIRES]->(c:Capability)
                WHERE NOT (:Model)-[:HAS_CAPABILITY]->(c)
                RETURN c.name AS capability,
                       collect(tc.name) AS blocked_tasks
            """)
            for r in result:
                suggestions.append(
                    {
                        "type": "capability_gap",
                        "priority": "critical",
                        "target": r["capability"],
                        "action": f"No model provides '{r['capability']}' — blocks tasks: {r['blocked_tasks']}",
                        "affected": len(r["blocked_tasks"]),
                    }
                )

            # 3. Over-connected models (potential bottleneck)
            result = session.run("""
                MATCH (m:Model)-[r]-()
                WITH m.name AS name, count(r) AS degree
                WHERE degree > 15
                RETURN name, degree ORDER BY degree DESC LIMIT 5
            """)
            for r in result:
                suggestions.append(
                    {
                        "type": "high_degree_node",
                        "priority": "low",
                        "target": r["name"],
                        "action": f"Model '{r['name']}' has {r['degree']} connections — consider role specialization",
                        "affected": 1,
                    }
                )

            # 4. Isolated intelligence types
            result = session.run("""
                MATCH (i:IntelligenceType)
                WHERE NOT ()-[:TYPE_OF]->(i)
                RETURN i.name AS name
            """)
            isolated = [r["name"] for r in result]
            if isolated:
                suggestions.append(
                    {
                        "type": "orphan_nodes",
                        "priority": "medium",
                        "target": "IntelligenceType",
                        "action": f"Intelligence types with no linked traits: {', '.join(isolated)}",
                        "affected": len(isolated),
                    }
                )

            # 5. Models that could share compatibility links
            result = session.run("""
                MATCH (m1:Model)-[:FILLS_ROLE]->(r:SystemRole)<-[:FILLS_ROLE]-(m2:Model)
                WHERE m1 <> m2
                  AND NOT (m1)-[:WORKS_WITH]-(m2)
                RETURN m1.name AS a, m2.name AS b, r.name AS shared_role
                LIMIT 10
            """)
            pairs = [(r["a"], r["b"], r["shared_role"]) for r in result]
            if pairs:
                suggestions.append(
                    {
                        "type": "missing_compatibility",
                        "priority": "medium",
                        "target": "WORKS_WITH",
                        "action": f"Models sharing roles but no WORKS_WITH link: {pairs[:3]}",
                        "affected": len(pairs),
                    }
                )

        return suggestions

    # ──────────────────────────────────────────────
    # Auto-Enrich from config.json
    # ──────────────────────────────────────────────

    def enrich_from_config(self) -> Dict[str, Any]:
        """Auto-create Model nodes and infer capabilities from config.json model_mappings."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error("Cannot load config.json: %s", e)
            return {"error": str(e)}

        created_models = []
        created_rels = []

        with self.driver.session() as session:
            # Get all models from all nodes
            all_models = set()
            for node in config.get("nodes", []):
                all_models.update(node.get("capabilities", {}).get("models", []))

            # Create Model nodes
            from raphael.ai_router.embedding_client import EmbeddingClient
            import asyncio

            router = EmbeddingClient()

            for model_name in all_models:
                provider = _infer_provider(model_name)
                is_local = ":cloud" not in model_name

                # Fetch embedding via KNOWLEDGE layer
                try:
                    vector = asyncio.run(router.embed(model_name, layer=EmbeddingLayer.KNOWLEDGE))
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for {model_name}: {e}")
                    vector = []

                result = session.run(
                    """
                    MERGE (m:Model {name: $name})
                    ON CREATE SET m.provider = $provider,
                                  m.local = $local,
                                  m.embedding = $vector,
                                  m.synced_from_config = true,
                                  m.synced_at = datetime()
                    RETURN m.name AS name, m.synced_from_config AS was_created
                    """,
                    name=model_name,
                    provider=provider,
                    local=is_local,
                    vector=vector,
                )
                record = result.single()
                if record and record["was_created"]:
                    created_models.append(model_name)

            # Link models to roles via model_mappings
            for mapping in config.get("model_mappings", []):
                role_id = mapping["role_id"]

                # Ensure role exists
                session.run(
                    "MERGE (r:SystemRole {name: $name})",
                    name=role_id,
                )

                for model_info in mapping.get("models", []):
                    model_id = model_info["model_id"]
                    result = session.run(
                        """
                        MATCH (m:Model {name: $model})
                        MATCH (r:SystemRole {name: $role})
                        MERGE (m)-[rel:FILLS_ROLE]->(r)
                        ON CREATE SET rel.context_length = $ctx,
                                      rel.created_at = datetime()
                        RETURN type(rel) AS rtype
                        """,
                        model=model_id,
                        role=role_id,
                        ctx=model_info.get("context_length", 4096),
                    )
                    if result.single():
                        created_rels.append(f"{model_id} -[:FILLS_ROLE]-> {role_id}")

        return {
            "models_created": created_models,
            "relationships_created": created_rels,
        }

    # ──────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────

    def export_snapshot(self, output_dir: str = ".") -> Dict[str, str]:
        """Export the full graph as JSON for backup/migration."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "nodes": [],
            "relationships": [],
        }

        with self.driver.session() as session:
            # Export all nodes
            result = session.run("""
                MATCH (n)
                RETURN labels(n) AS labels, properties(n) AS props, elementId(n) AS id
            """)
            for r in result:
                snapshot["nodes"].append(
                    {
                        "id": r["id"],
                        "labels": r["labels"],
                        "properties": r["props"],
                    }
                )

            # Export all relationships
            result = session.run("""
                MATCH (a)-[r]->(b)
                RETURN type(r) AS type, properties(r) AS props,
                       elementId(a) AS start, elementId(b) AS end,
                       labels(a)[0] + '.' + coalesce(a.name, '') AS start_name,
                       labels(b)[0] + '.' + coalesce(b.name, '') AS end_name
            """)
            for r in result:
                snapshot["relationships"].append(
                    {
                        "type": r["type"],
                        "start": r["start_name"],
                        "end": r["end_name"],
                        "properties": r["props"],
                    }
                )

        # Write to file
        filename = f"graph_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)

        logger.info(
            "Exported %d nodes, %d rels to %s",
            len(snapshot["nodes"]),
            len(snapshot["relationships"]),
            filepath,
        )
        return {
            "file": filepath,
            "nodes": len(snapshot["nodes"]),
            "relationships": len(snapshot["relationships"]),
        }

    # ──────────────────────────────────────────────
    # Full Pipeline
    # ──────────────────────────────────────────────

    def optimize(self, auto_enrich: bool = True, export: bool = False) -> Dict:
        """Run the full optimization pipeline."""
        logger.info("=" * 60)
        logger.info("GRAPH OPTIMIZATION PIPELINE")
        logger.info("=" * 60)

        # 1. Structural analysis
        logger.info("Phase 1: Analyzing structure...")
        analysis = self.analyze_structure()
        logger.info(
            "  Nodes: %d | Relationships: %d | Avg degree: %.1f",
            analysis["density"]["total_nodes"],
            analysis["density"]["total_relationships"],
            analysis["density"]["avg_degree"],
        )

        # 2. Find optimization opportunities
        logger.info("Phase 2: Finding optimization opportunities...")
        suggestions = self.find_optimization_opportunities()
        for s in suggestions:
            icon = (
                "🔴" if s["priority"] == "critical" else "🟡" if s["priority"] == "high" else "🟢"
            )
            logger.info("  %s [%s] %s", icon, s["priority"], s["action"])

        # 3. Auto-enrich from config
        enrichment = {}
        if auto_enrich:
            logger.info("Phase 3: Enriching from config.json...")
            enrichment = self.enrich_from_config()
            if enrichment.get("models_created"):
                logger.info("  Created %d new model nodes", len(enrichment["models_created"]))
            if enrichment.get("relationships_created"):
                logger.info(
                    "  Created %d new relationships",
                    len(enrichment["relationships_created"]),
                )

        # 4. Export snapshot
        snapshot = {}
        if export:
            logger.info("Phase 4: Exporting snapshot...")
            snapshot = self.export_snapshot()

        result = {
            "analysis": analysis,
            "suggestions": suggestions,
            "enrichment": enrichment,
            "snapshot": snapshot,
        }

        logger.info("=" * 60)
        logger.info(
            "Done. %d suggestions, %d models enriched.",
            len(suggestions),
            len(enrichment.get("models_created", [])),
        )
        return result


def _infer_provider(model_name: str) -> str:
    """Guess the provider from model name."""
    name = model_name.lower()
    if "deepseek" in name:
        return "deepseek"
    if "qwen" in name:
        return "alibaba"
    if "llama" in name:
        return "meta"
    if "mistral" in name:
        return "mistral"
    if "gemma" in name:
        return "google"
    if "phi" in name:
        return "microsoft"
    if "glm" in name:
        return "zhipu"
    if "llava" in name or "moondream" in name:
        return "community"
    if "minilm" in name or "mxbai" in name or "nomic" in name:
        return "community"
    return "unknown"


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [OPTIMIZER] %(levelname)s: %(message)s",
    )

    optimizer = GraphOptimizer()
    try:
        result = optimizer.optimize(auto_enrich=True, export=False)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        logger.error("Fatal error: %s", e)
    finally:
        optimizer.close()


if __name__ == "__main__":
    main()
