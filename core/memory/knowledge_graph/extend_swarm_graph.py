import os
from neo4j import GraphDatabase
from pathlib import Path

# Connection Details
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASS = os.getenv("NEO4J_PASSWORD", "")


class SwarmGraphExtender:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def execute_schema(self, cypher_file):
        print(f"Applying schema from {cypher_file}...")
        with open(cypher_file, "r") as f:
            content = f.read()

        statements = []
        current_stmt = []
        for line in content.splitlines():
            # Basic comment stripping
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
        print("Implementing Agent Hierarchy & Delegation...")
        with self._driver.session() as session:
            # 1. Project Sorter Hierarchy
            session.run("""
            MATCH (director:Agent {name: "project_sorter_director_agent"})
            MATCH (worker:Agent)
            WHERE worker.name STARTS WITH "project_sorter_" AND worker.name <> "project_sorter_director_agent"
            MERGE (director)-[:MANAGES]->(worker)
            MERGE (director)-[:DELEGATES_TO]->(worker)
            """)

            # 2. Portfolio Hierarchy
            session.run("""
            MATCH (director:Agent {name: "portfolio_agent"})
            MATCH (worker:Agent)
            WHERE worker.name STARTS WITH "portfolio_" AND worker.name <> "portfolio_agent"
            MERGE (director)-[:MANAGES]->(worker)
            """)

            # 3. Router Delegation (Generic)
            session.run("""
            MATCH (router:Agent {name: "router_agent"})
            MATCH (other:Agent)
            WHERE other <> router
            MERGE (router)-[:DELEGATES_TO]->(other)
            """)

    def implement_network_topology(self):
        print("Implementing Network Topology...")
        with self._driver.session() as session:
            # Connect Mac to Desktop (Tailscale linkage)
            session.run("""
            MATCH (mac:Machine {id: "macbook"})
            MATCH (pc:Machine {id: "desktop"})
            MERGE (mac)-[:CONNECTED_TO {type: "Tailscale", latency_ms: 15}]->(pc)
            MERGE (pc)-[:CONNECTED_TO {type: "Tailscale", latency_ms: 15}]->(mac)
            """)

    def implement_skill_tool_links(self):
        print("Linking Skills to required Tools...")
        with self._driver.session() as session:
            # Code Gen skill requires terminal and git tools
            session.run("""
            MATCH (s:Skill {name: "code_generation"})
            MATCH (t:Tool)
            WHERE t.name CONTAINS "terminal" OR t.name CONTAINS "git" OR t.name CONTAINS "file"
            MERGE (s)-[:REQUIRES_TOOL]->(t)
            """)

            # Search Documents skill requires ripgrep/search tools
            session.run("""
            MATCH (s:Skill {name: "search_documents"})
            MATCH (t:Tool)
            WHERE t.name CONTAINS "search" OR t.name CONTAINS "grep" OR t.name CONTAINS "read"
            MERGE (s)-[:REQUIRES_TOOL]->(t)
            """)

    def implement_cognitive_pathways(self):
        print("Implementing Cognitive Pathways (Agent -> Model Preferences)...")
        with self._driver.session() as session:
            # Preference: Portfolio Agent prefers high-reasoning models
            session.run("""
            MATCH (a:Agent {name: "portfolio_agent"})
            MATCH (m:Model)
            WHERE m.name CONTAINS "deepseek" OR m.name CONTAINS "llama-3-70b"
            MERGE (a)-[:PREFERS_MODEL]->(m)
            """)

    def add_mock_learning_data(self):
        print("Adding Mock Learning & Evolution data...")
        with self._driver.session() as session:
            # Create a Task and a resulting Observation
            session.run("""
            MERGE (t:Task {id: "t-101", type: "refactoring", description: "Optimize imports"})
            MERGE (o:Observation {id: "obs-1", result: "Reduced latency by 200ms", timestamp: datetime()})
            MERGE (t)-[:GENERATED]->(o)
            
            WITH o
            MATCH (p:PerformanceProfile)
            WHERE p.latency_ms > 0
            MERGE (o)-[:UPDATES]->(p)
            """)

            # Create an Experiment
            session.run("""
            MERGE (e:Experiment {id: "exp-02", name: "Llama 3.1 vs 3.2 for Planning"})
            WITH e
            MATCH (m:Model) WHERE m.name CONTAINS "llama"
            MERGE (e)-[:TESTED_MODEL]->(m)
            """)

            # Create a Failure -> Improvement loop
            session.run("""
            MERGE (f:Failure {id: "fail-99", reason: "Context window exceeded", severity: "High"})
            MERGE (rp:RoutingPolicy {id: "p-01", strategy: "ContextAware"})
            MERGE (i:Improvement {id: "imp-01", change: "Add token chunking layer"})
            MERGE (f)-[:IMPROVES]->(rp)
            MERGE (i)-[:RESOLVES]->(f)
            """)


if __name__ == "__main__":
    extender = SwarmGraphExtender(DB_URI, DB_USER, DB_PASS)
    schema_path = "/Users/yamai/ai/Raphael/evolution_schema.cypher"

    extender.execute_schema(schema_path)
    extender.implement_hierarchy()
    extender.implement_network_topology()
    extender.implement_skill_tool_links()
    extender.implement_cognitive_pathways()
    extender.add_mock_learning_data()

    extender.close()
    print("Knowledge Graph extension completed successfully!")
