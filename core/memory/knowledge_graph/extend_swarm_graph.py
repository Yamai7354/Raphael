import os
import logging
from neo4j import GraphDatabase
from pathlib import Path

from core.knowledge_quality.intake_gate import (
    IntakeGate,
    NodeProposal,
    EdgeProposal,
    Provenance,
)

logger = logging.getLogger("knowledge_graph.extend")

# Connection Details
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASS = os.getenv("NEO4J_PASSWORD", "")


class SwarmGraphExtender:
    def __init__(self, uri, user, password, gate: IntakeGate = None):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._gate = gate

    def close(self):
        self._driver.close()

    def execute_schema(self, cypher_file):
        print(f"Applying schema from {cypher_file}...")
        with open(cypher_file, "r") as f:
            content = f.read()

        statements = []
        current_stmt = []
        for line in content.splitlines():
            if line.strip().startswith("//") or line.strip().startswith("/*"):
                continue
            if not line.strip():
                continue
            current_stmt.append(line)
            if ";" in line:
                stmt = "\n".join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

        with self._driver.session() as session:
            for stmt in statements:
                try:
                    if "CONSTRAINT" in stmt or "INDEX" in stmt:
                        session.run(stmt)
                        print(f"Executed constraint/index: {stmt[:50]}...")
                except Exception as e:
                    print(f"Error executing statement:\n{stmt}\n{e}")

    def implement_hierarchy(self):
        """Agent hierarchy: MANAGES / DELEGATES_TO edges."""
        print("Implementing Agent Hierarchy & Delegation...")
        hierarchy_prov = Provenance(
            source="swarm_topology", confidence=0.85, evidence="extend_swarm_graph"
        )

        if self._gate:
            # Project Sorter hierarchy
            for worker in [
                "project_sorter_analyzer_agent",
                "project_sorter_builder_agent",
                "project_sorter_tester_agent",
            ]:
                for rel in ["MANAGES", "DELEGATES_TO"]:
                    self._gate.submit_edge(EdgeProposal(
                        from_label="Agent",
                        from_keys={"name": "project_sorter_director_agent"},
                        rel_type=rel,
                        to_label="Agent",
                        to_keys={"name": worker},
                        provenance=hierarchy_prov,
                        submitted_by="SwarmGraphExtender",
                    ))

            # Portfolio hierarchy
            for worker in [
                "portfolio_report_agent",
                "portfolio_planner",
                "portfolio_memory",
            ]:
                self._gate.submit_edge(EdgeProposal(
                    from_label="Agent",
                    from_keys={"name": "portfolio_agent"},
                    rel_type="MANAGES",
                    to_label="Agent",
                    to_keys={"name": worker},
                    provenance=hierarchy_prov,
                    submitted_by="SwarmGraphExtender",
                ))
        else:
            with self._driver.session() as session:
                session.run("""
                MATCH (director:Agent {name: "project_sorter_director_agent"})
                MATCH (worker:Agent)
                WHERE worker.name STARTS WITH "project_sorter_" AND worker.name <> "project_sorter_director_agent"
                MERGE (director)-[:MANAGES]->(worker)
                MERGE (director)-[:DELEGATES_TO]->(worker)
                """)
                session.run("""
                MATCH (director:Agent {name: "portfolio_agent"})
                MATCH (worker:Agent)
                WHERE worker.name STARTS WITH "portfolio_" AND worker.name <> "portfolio_agent"
                MERGE (director)-[:MANAGES]->(worker)
                """)
                session.run("""
                MATCH (router:Agent {name: "router_agent"})
                MATCH (other:Agent)
                WHERE other <> router
                MERGE (router)-[:DELEGATES_TO]->(other)
                """)

    def implement_network_topology(self):
        """Machine CONNECTED_TO edges."""
        print("Implementing Network Topology...")
        net_prov = Provenance(
            source="network_config", confidence=0.9, evidence="tailscale"
        )

        if self._gate:
            self._gate.submit_edge(EdgeProposal(
                from_label="Machine",
                from_keys={"id": "macbook"},
                rel_type="CONNECTED_TO",
                to_label="Machine",
                to_keys={"id": "desktop"},
                properties={"type": "Tailscale", "latency_ms": 15},
                provenance=net_prov,
                submitted_by="SwarmGraphExtender",
            ))
            self._gate.submit_edge(EdgeProposal(
                from_label="Machine",
                from_keys={"id": "desktop"},
                rel_type="CONNECTED_TO",
                to_label="Machine",
                to_keys={"id": "macbook"},
                properties={"type": "Tailscale", "latency_ms": 15},
                provenance=net_prov,
                submitted_by="SwarmGraphExtender",
            ))
        else:
            with self._driver.session() as session:
                session.run("""
                MATCH (mac:Machine {id: "macbook"})
                MATCH (pc:Machine {id: "desktop"})
                MERGE (mac)-[:CONNECTED_TO {type: "Tailscale", latency_ms: 15}]->(pc)
                MERGE (pc)-[:CONNECTED_TO {type: "Tailscale", latency_ms: 15}]->(mac)
                """)

    def implement_skill_tool_links(self):
        """Skill REQUIRES_TOOL edges."""
        print("Linking Skills to required Tools...")
        link_prov = Provenance(
            source="skill_tool_mapping", confidence=0.8, evidence="extend_swarm_graph"
        )

        if self._gate:
            skill_tool_map = {
                "code_generation": ["shell_executor", "file_tool"],
                "web_research": ["web_browser", "web_search"],
            }
            for skill, tools in skill_tool_map.items():
                for tool in tools:
                    self._gate.submit_edge(EdgeProposal(
                        from_label="Skill",
                        from_keys={"name": skill},
                        rel_type="REQUIRES_TOOL",
                        to_label="Tool",
                        to_keys={"name": tool},
                        provenance=link_prov,
                        submitted_by="SwarmGraphExtender",
                    ))
        else:
            with self._driver.session() as session:
                session.run("""
                MATCH (s:Skill {name: "code_generation"})
                MATCH (t:Tool)
                WHERE t.name CONTAINS "terminal" OR t.name CONTAINS "git" OR t.name CONTAINS "file"
                MERGE (s)-[:REQUIRES_TOOL]->(t)
                """)
                session.run("""
                MATCH (s:Skill {name: "search_documents"})
                MATCH (t:Tool)
                WHERE t.name CONTAINS "search" OR t.name CONTAINS "grep" OR t.name CONTAINS "read"
                MERGE (s)-[:REQUIRES_TOOL]->(t)
                """)

    def implement_cognitive_pathways(self):
        """Agent PREFERS_MODEL edges."""
        print("Implementing Cognitive Pathways (Agent -> Model Preferences)...")
        pref_prov = Provenance(
            source="cognitive_config", confidence=0.7, evidence="extend_swarm_graph"
        )

        if self._gate:
            preferences = {
                "portfolio_agent": ["deepseek-r1:7b", "llama3.1:70b"],
            }
            for agent, models in preferences.items():
                for model in models:
                    self._gate.submit_edge(EdgeProposal(
                        from_label="Agent",
                        from_keys={"name": agent},
                        rel_type="PREFERS_MODEL",
                        to_label="Model",
                        to_keys={"name": model},
                        provenance=pref_prov,
                        submitted_by="SwarmGraphExtender",
                    ))
        else:
            with self._driver.session() as session:
                session.run("""
                MATCH (a:Agent {name: "portfolio_agent"})
                MATCH (m:Model)
                WHERE m.name CONTAINS "deepseek" OR m.name CONTAINS "llama-3-70b"
                MERGE (a)-[:PREFERS_MODEL]->(m)
                """)

    def add_mock_learning_data(self):
        """Add mock data — marked with low confidence."""
        print("Adding Mock Learning & Evolution data...")
        mock_prov = Provenance(
            source="mock_data", confidence=0.1, evidence="synthetic test data"
        )

        if self._gate:
            self._gate.submit_node(NodeProposal(
                label="Task",
                match_keys={"id": "t-101"},
                properties={"type": "refactoring", "description": "Optimize imports"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))
            self._gate.submit_node(NodeProposal(
                label="Observation",
                match_keys={"id": "obs-1"},
                properties={"result": "Reduced latency by 200ms"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))
            self._gate.submit_edge(EdgeProposal(
                from_label="Task",
                from_keys={"id": "t-101"},
                rel_type="GENERATED",
                to_label="Observation",
                to_keys={"id": "obs-1"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))

            self._gate.submit_node(NodeProposal(
                label="Experiment",
                match_keys={"id": "exp-02"},
                properties={"name": "Llama 3.1 vs 3.2 for Planning"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))

            self._gate.submit_node(NodeProposal(
                label="Failure",
                match_keys={"id": "fail-99"},
                properties={"reason": "Context window exceeded", "severity": "High"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))
            self._gate.submit_node(NodeProposal(
                label="RoutingPolicy",
                match_keys={"id": "p-01"},
                properties={"strategy": "ContextAware"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))
            self._gate.submit_node(NodeProposal(
                label="Improvement",
                match_keys={"id": "imp-01"},
                properties={"change": "Add token chunking layer"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))
            self._gate.submit_edge(EdgeProposal(
                from_label="Failure",
                from_keys={"id": "fail-99"},
                rel_type="IMPROVES",
                to_label="RoutingPolicy",
                to_keys={"id": "p-01"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))
            self._gate.submit_edge(EdgeProposal(
                from_label="Improvement",
                from_keys={"id": "imp-01"},
                rel_type="RESOLVES",
                to_label="Failure",
                to_keys={"id": "fail-99"},
                provenance=mock_prov,
                submitted_by="SwarmGraphExtender",
            ))
        else:
            with self._driver.session() as session:
                session.run("""
                MERGE (t:Task {id: "t-101", type: "refactoring", description: "Optimize imports"})
                MERGE (o:Observation {id: "obs-1", result: "Reduced latency by 200ms", timestamp: datetime()})
                MERGE (t)-[:GENERATED]->(o)
                WITH o
                MATCH (p:PerformanceProfile) WHERE p.latency_ms > 0
                MERGE (o)-[:UPDATES]->(p)
                """)
                session.run("""
                MERGE (e:Experiment {id: "exp-02", name: "Llama 3.1 vs 3.2 for Planning"})
                WITH e
                MATCH (m:Model) WHERE m.name CONTAINS "llama"
                MERGE (e)-[:TESTED_MODEL]->(m)
                """)
                session.run("""
                MERGE (f:Failure {id: "fail-99", reason: "Context window exceeded", severity: "High"})
                MERGE (rp:RoutingPolicy {id: "p-01", strategy: "ContextAware"})
                MERGE (i:Improvement {id: "imp-01", change: "Add token chunking layer"})
                MERGE (f)-[:IMPROVES]->(rp)
                MERGE (i)-[:RESOLVES]->(f)
                """)


if __name__ == "__main__":
    from core.knowledge_quality.skill_dictionary import SkillDictionary
    from core.knowledge_quality.tool_manifest_registry import ToolManifestRegistry

    driver = GraphDatabase.driver(DB_URI, auth=(DB_USER, DB_PASS))
    gate = IntakeGate(
        driver=driver,
        skill_dictionary=SkillDictionary(),
        tool_manifest_registry=ToolManifestRegistry(),
    )

    extender = SwarmGraphExtender(DB_URI, DB_USER, DB_PASS, gate=gate)
    schema_path = "/Users/yamai/ai/Raphael/core/memory/knowledge_graph/evolution_schema.cypher"

    extender.execute_schema(schema_path)
    extender.implement_hierarchy()
    extender.implement_network_topology()
    extender.implement_skill_tool_links()
    extender.implement_cognitive_pathways()
    extender.add_mock_learning_data()

    extender.close()
    driver.close()
    print("Knowledge Graph extension completed successfully!")
    print(f"Gate stats: {gate.get_stats()}")
