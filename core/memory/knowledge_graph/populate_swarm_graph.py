import json
import os
import sys
import argparse
import ast
import re
from pathlib import Path
from neo4j import GraphDatabase

# URIs
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASS = os.getenv("NEO4J_PASSWORD", "")

# Root path for relative files
ROOT_DIR = Path("/Users/yamai/ai")


class SwarmGraphIngestor:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def execute_schema(self, cypher_file):
        """Creates indexes and constraints from the setup file."""
        print(f"Applying schema from {cypher_file}...")
        with open(cypher_file, "r") as f:
            content = f.read()

        # Simple split by ';' avoiding comments.
        # This is a basic parser since the file is well-formed
        statements = []
        current_stmt = []
        for line in content.splitlines():
            # Skip comments
            if (
                line.strip().startswith("//")
                or line.strip().startswith("/*")
                or line.strip().startswith("*")
            ):
                continue

            current_stmt.append(line)
            if ";" in line:
                # Execute full statement
                stmt = "\n".join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

        with self._driver.session() as session:
            for i, stmt in enumerate(statements):
                try:
                    # Some schema creates are just samples, so we might want to only apply Constraints and Indexes
                    if "CONSTRAINT" in stmt or "INDEX" in stmt:
                        session.run(stmt)
                        print(f"Executed index/constraint {i + 1}")
                except Exception as e:
                    print(f"Error executing statement:\n{stmt}\n{e}")

    def ingest_hardware(self):
        """Ingests Hardware capabilities for Mac and Desktop"""
        mac_file = ROOT_DIR / "Raphael/mac_hardware_capabilities.json"
        desktop_file = ROOT_DIR / "Raphael/desktop_hardware_capabilities.json"

        # Using a direct cypher representation given the file contents provided by user
        # Note: The JSON provided actually had Cypher commands prefixed in the text, so we parse properly.
        print("Ingesting Hardware & Machines...")

        with self._driver.session() as session:
            # Recreate machines exactly mapped (using MERGE instead of CREATE to prevent duplicates)
            session.run("""
            MERGE (desktop:Machine {id: "desktop"})
            SET desktop.hostname = "ai-desktop", desktop.tailscale_ip = "100.125.58.22", desktop.status = "online", desktop.ram_gb = 16
            """)

            session.run("""
            MERGE (macbook:Machine {id: "macbook"})
            SET macbook.hostname = "ai-macbook", macbook.tailscale_ip = "100.66.48.16", macbook.status = "online", macbook.ram_gb = 16
            """)

            # Extracting from malformed JSON via robust regex
            def process_hw_file(filepath, machine_id):
                try:
                    with open(filepath, "r") as f:
                        text = f.read()

                    gpu_blocks = re.findall(r'"gpuInfo"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                    total_gpus_found = 0

                    for block in gpu_blocks:
                        parts = block.split('"name":')
                        for part in parts[1:]:
                            name_match = re.search(r'^\s*"([^"]+)"', part)
                            mem_match = re.search(
                                r'"dedicatedMemoryCapacityBytes"\s*:\s*(\d+)', part
                            )
                            dev_match = re.search(r'"deviceId"\s*:\s*(\d+)', part)

                            if name_match and mem_match:
                                name = name_match.group(1)
                                vram = int(mem_match.group(1)) / (1024**3)
                                dev_id = dev_match.group(1) if dev_match else "0"
                                type_name = f"{name}_{dev_id}"
                                total_gpus_found += 1

                                session.run(
                                    """
                                MERGE (h:Hardware {type: "GPU", name: $name})
                                ON CREATE SET h.vram_gb = $vram
                                WITH h
                                MATCH (m:Machine {id: $machine_id})
                                MERGE (m)-[:HAS_HARDWARE]->(h)
                                """,
                                    name=type_name,
                                    vram=vram,
                                    machine_id=machine_id,
                                )
                                print(
                                    f"Registered {type_name} on {machine_id} with {vram:.2f}GB VRAM"
                                )

                    if total_gpus_found == 0:
                        print(f"No GPUs found parsing hardware file for {machine_id}")

                except Exception as e:
                    print(f"Failed to process hardware file {filepath}: {e}")

            process_hw_file(desktop_file, "desktop")
            process_hw_file(mac_file, "macbook")

    def ingest_llm_registry(self, filepath, machine_id):
        """Ingest LLM instances from registry files"""
        print(f"Ingesting models from {filepath} onto {machine_id}...")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            models = data.get("models", {})

            with self._driver.session() as session:
                for full_name, details in models.items():
                    # Sanitize and extract
                    size_text = details.get("parameter_size", "0b").lower()
                    size_val = float(size_text.replace("b", "")) if "b" in size_text else 0.0

                    quant = details.get("quantization_level", "unknown")
                    family = details.get("family", "unknown")
                    model_type = details.get("type", "unknown")

                    session.run(
                        """
                    MERGE (model:Model {name: $name})
                    SET model.family = $family,
                        model.parameters_b = $size,
                        model.quantization = $quant,
                        model.type = $model_type
                    WITH model
                    MATCH (m:Machine {id: $machine_id})
                    MERGE (model)-[:RUNS_ON]->(m)
                    """,
                        name=full_name,
                        family=family,
                        size=size_val,
                        quant=quant,
                        model_type=model_type,
                        machine_id=machine_id,
                    )

                    # Process Capabilities / Roles
                    roles = details.get("role", [])
                    # Append type as a capability as well
                    if model_type:
                        roles.append(model_type)

                    # Remove duplicates
                    roles = list(set(roles))

                    for r in roles:
                        if not r:
                            continue
                        session.run(
                            """
                        MERGE (cap:Capability {name: $cap})
                        WITH cap
                        MATCH (model:Model {name: $model_name})
                        MERGE (model)-[:HAS_CAPABILITY]->(cap)
                        """,
                            cap=r,
                            model_name=full_name,
                        )

            print(f"Ingested {len(models)} models for {machine_id}.")

        except Exception as e:
            print(f"Failed to process model registry {filepath}: {e}")

    def discover_tools_and_agents(self):
        """Scrapes the _registry.py arrays to populate available agents & tools."""
        print("Discovering Agents and Tools...")
        tools_reg_path = ROOT_DIR / "agent_ecosystem/packages/tools/_registry.py"
        agents_reg_path = ROOT_DIR / "agent_ecosystem/packages/agents/_registry.py"

        def _extract_modules(filepath):
            if not filepath.exists():
                return []
            try:
                content = filepath.read_text()
                # Extremely lazy parse of the AVAILABLE_MODULES array since it's a python list
                match = re.search(r"AVAILABLE_MODULES\s*=\s*\[(.*?)\]", content, re.DOTALL)
                if match:
                    # eval the matched string to a python list
                    clean_str = "[" + match.group(1) + "]"
                    return ast.literal_eval(clean_str)
            except Exception as e:
                print(f"Parse error on {filepath}: {e}")
            return []

        agents = _extract_modules(agents_reg_path)
        tools = _extract_modules(tools_reg_path)

        with self._driver.session() as session:
            for a in agents:
                # Basic inference of role from name (e.g. planner_agent -> planner)
                role = a.split("_")[-1] if a else "unknown"
                session.run(
                    """
                MERGE (agent:Agent {name: $name})
                SET agent.role = $role
                """,
                    name=a,
                    role=role,
                )

            for t in tools:
                session.run(
                    """
                MERGE (tool:Tool {name: $name})
                SET tool.latency_ms = 0
                """,
                    name=t,
                )

            print(f"Ingested {len(agents)} agents and {len(tools)} tools.")

            # TODO: Future mapping of specific tools to agents via CAN_USE relationships
            # For now, give the planner_agent access to everything just as an example
            # if we wanted to populate relations, but we will leave them unconnected for precision.

    def discover_skills(self):
        """Scrapes the discovered_skills.md or skill builder script for skills"""
        print("Discovering Skills from agent_ecosystem...")

        # We will dynamically run the skill_builder script logic or read its output
        skill_builder_path = ROOT_DIR / "agent_ecosystem/projects/project_sorter/skill_builder.py"

        # Rather than running the script which requires network and LLM calls,
        # we will use the existing `discovered_skills.md` directory links as root points.
        discovered_path = ROOT_DIR / "agent_ecosystem/_project_summaries_v3/discovered_skills.md"

        skills_found = set()

        if discovered_path.exists():
            for line in discovered_path.read_text().splitlines():
                if line.startswith("-") and " at " in line:
                    folder = line.split(" at ")[-1].strip()
                    skills_found.add(Path(folder).name)

        # Fallback manual scan for any explicit SKILL.md
        for root, dirs, files in os.walk(ROOT_DIR / "agent_ecosystem"):
            if "SKILL.md" in files:
                skills_found.add(Path(root).name)

        # Also ingest from the known skills directory in Raphael
        for root, dirs, files in os.walk(ROOT_DIR / "Raphael/.agents/skills"):
            skills_found.add(Path(root).name)

        if not skills_found:
            skills_found = {"code_generation", "system_design", "research_analysis"}  # fallbacks

        with self._driver.session() as session:
            for s in skills_found:
                session.run(
                    """
                MERGE (skill:Skill {name: $name})
                """,
                    name=s,
                )

            # Create dummy links between agent -> skill -> model capability to test the query
            session.run("""
            MATCH (a:Agent)
            WHERE a.name CONTAINS "portfolio"
            MATCH (s:Skill)
            WHERE s.name CONTAINS "portfolio" OR s.name CONTAINS "doc"
            MERGE (a)-[:HAS_SKILL]->(s)
            """)
            print(f"Ingested {len(skills_found)} skills.")


if __name__ == "__main__":
    ingestor = SwarmGraphIngestor(DB_URI, DB_USER, DB_PASS)
    schema_path = ROOT_DIR / "Raphael/swarm_architecture_schema.cypher"

    ingestor.execute_schema(schema_path)
    ingestor.ingest_hardware()
    ingestor.ingest_llm_registry(ROOT_DIR / "agent_ecosystem/local_llm_registry.json", "macbook")
    ingestor.ingest_llm_registry(ROOT_DIR / "agent_ecosystem/desktop_llm_registry.json", "desktop")
    ingestor.discover_tools_and_agents()
    ingestor.discover_skills()
    ingestor.close()

    print("Graph ingestion completed successfully!")
