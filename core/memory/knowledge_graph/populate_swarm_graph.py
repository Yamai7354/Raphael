import json
import os
import sys
import argparse
import ast
import logging
import re
from pathlib import Path
from neo4j import GraphDatabase

from core.knowledge_quality.intake_gate import (
    IntakeGate,
    NodeProposal,
    EdgeProposal,
    Provenance,
    ProposalVerdict,
)

logger = logging.getLogger("knowledge_graph.populate")

# URIs
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASS = os.getenv("NEO4J_PASSWORD", "")

# Root path for relative files
ROOT_DIR = Path("/Users/yamai/ai")


class SwarmGraphIngestor:
    def __init__(self, uri, user, password, gate: IntakeGate = None):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._gate = gate

    def close(self):
        self._driver.close()

    def execute_schema(self, cypher_file):
        """Creates indexes and constraints from the setup file."""
        print(f"Applying schema from {cypher_file}...")
        with open(cypher_file, "r") as f:
            content = f.read()

        statements = []
        current_stmt = []
        for line in content.splitlines():
            if (
                line.strip().startswith("//")
                or line.strip().startswith("/*")
                or line.strip().startswith("*")
            ):
                continue

            current_stmt.append(line)
            if ";" in line:
                stmt = "\n".join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

        with self._driver.session() as session:
            for i, stmt in enumerate(statements):
                try:
                    if "CONSTRAINT" in stmt or "INDEX" in stmt:
                        session.run(stmt)
                        print(f"Executed index/constraint {i + 1}")
                except Exception as e:
                    print(f"Error executing statement:\n{stmt}\n{e}")

    def ingest_hardware(self):
        """Ingests Hardware capabilities for Mac and Desktop."""
        mac_file = ROOT_DIR / "Raphael/mac_hardware_capabilities.json"
        desktop_file = ROOT_DIR / "Raphael/desktop_hardware_capabilities.json"
        print("Ingesting Hardware & Machines...")

        hw_provenance = Provenance(
            source="hardware_json", confidence=0.95, evidence="hardware_capabilities.json"
        )

        if self._gate:
            # Machine nodes
            for mid, hostname, ip in [
                ("desktop", "ai-desktop", "100.125.58.22"),
                ("macbook", "ai-macbook", "100.66.48.16"),
            ]:
                self._gate.submit_node(NodeProposal(
                    label="Machine",
                    match_keys={"id": mid},
                    properties={
                        "hostname": hostname,
                        "tailscale_ip": ip,
                        "status": "online",
                        "ram_gb": 16,
                    },
                    provenance=hw_provenance,
                    submitted_by="SwarmGraphIngestor",
                ))

            # GPU Hardware from files
            for filepath, machine_id in [(desktop_file, "desktop"), (mac_file, "macbook")]:
                self._ingest_gpus_via_gate(filepath, machine_id, hw_provenance)
        else:
            with self._driver.session() as session:
                session.run("""
                MERGE (desktop:Machine {id: "desktop"})
                SET desktop.hostname = "ai-desktop", desktop.tailscale_ip = "100.125.58.22", desktop.status = "online", desktop.ram_gb = 16
                """)
                session.run("""
                MERGE (macbook:Machine {id: "macbook"})
                SET macbook.hostname = "ai-macbook", macbook.tailscale_ip = "100.66.48.16", macbook.status = "online", macbook.ram_gb = 16
                """)

                def process_hw_file(filepath, machine_id):
                    try:
                        with open(filepath, "r") as f:
                            text = f.read()
                        gpu_blocks = re.findall(r'"gpuInfo"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                        for block in gpu_blocks:
                            parts = block.split('"name":')
                            for part in parts[1:]:
                                name_match = re.search(r'^\s*"([^"]+)"', part)
                                mem_match = re.search(r'"dedicatedMemoryCapacityBytes"\s*:\s*(\d+)', part)
                                dev_match = re.search(r'"deviceId"\s*:\s*(\d+)', part)
                                if name_match and mem_match:
                                    name = name_match.group(1)
                                    vram = int(mem_match.group(1)) / (1024**3)
                                    dev_id = dev_match.group(1) if dev_match else "0"
                                    type_name = f"{name}_{dev_id}"
                                    session.run("""
                                    MERGE (h:Hardware {type: "GPU", name: $name})
                                    ON CREATE SET h.vram_gb = $vram
                                    WITH h
                                    MATCH (m:Machine {id: $machine_id})
                                    MERGE (m)-[:HAS_HARDWARE]->(h)
                                    """, name=type_name, vram=vram, machine_id=machine_id)
                    except Exception as e:
                        print(f"Failed to process hardware file {filepath}: {e}")

                process_hw_file(desktop_file, "desktop")
                process_hw_file(mac_file, "macbook")

    def _ingest_gpus_via_gate(self, filepath, machine_id, provenance):
        """Parse GPU info from hardware JSON and submit through the gate."""
        try:
            with open(filepath, "r") as f:
                text = f.read()
            gpu_blocks = re.findall(r'"gpuInfo"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            for block in gpu_blocks:
                parts = block.split('"name":')
                for part in parts[1:]:
                    name_match = re.search(r'^\s*"([^"]+)"', part)
                    mem_match = re.search(r'"dedicatedMemoryCapacityBytes"\s*:\s*(\d+)', part)
                    dev_match = re.search(r'"deviceId"\s*:\s*(\d+)', part)
                    if name_match and mem_match:
                        name = name_match.group(1)
                        vram = int(mem_match.group(1)) / (1024**3)
                        dev_id = dev_match.group(1) if dev_match else "0"
                        type_name = f"{name}_{dev_id}"

                        self._gate.submit_node(NodeProposal(
                            label="Hardware",
                            match_keys={"type": "GPU", "name": type_name},
                            properties={"vram_gb": vram},
                            provenance=provenance,
                            submitted_by="SwarmGraphIngestor",
                        ))
                        self._gate.submit_edge(EdgeProposal(
                            from_label="Machine",
                            from_keys={"id": machine_id},
                            rel_type="HAS_HARDWARE",
                            to_label="Hardware",
                            to_keys={"type": "GPU", "name": type_name},
                            provenance=provenance,
                            submitted_by="SwarmGraphIngestor",
                        ))
                        print(f"Registered {type_name} on {machine_id} with {vram:.2f}GB VRAM")
        except Exception as e:
            print(f"Failed to process hardware file {filepath}: {e}")

    def ingest_llm_registry(self, filepath, machine_id):
        """Ingest LLM instances from registry files."""
        print(f"Ingesting models from {filepath} onto {machine_id}...")
        reg_provenance = Provenance(
            source="llm_registry", confidence=0.9, evidence=str(filepath)
        )

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            models = data.get("models", {})

            if self._gate:
                for full_name, details in models.items():
                    size_text = details.get("parameter_size", "0b").lower()
                    size_val = float(size_text.replace("b", "")) if "b" in size_text else 0.0
                    quant = details.get("quantization_level", "unknown")
                    family = details.get("family", "unknown")
                    model_type = details.get("type", "unknown")

                    self._gate.submit_node(NodeProposal(
                        label="Model",
                        match_keys={"name": full_name},
                        properties={
                            "family": family,
                            "parameters_b": size_val,
                            "quantization": quant,
                            "type": model_type,
                        },
                        provenance=reg_provenance,
                        submitted_by="SwarmGraphIngestor",
                    ))
                    self._gate.submit_edge(EdgeProposal(
                        from_label="Model",
                        from_keys={"name": full_name},
                        rel_type="RUNS_ON",
                        to_label="Machine",
                        to_keys={"id": machine_id},
                        provenance=reg_provenance,
                        submitted_by="SwarmGraphIngestor",
                    ))

                    roles = list(set(details.get("role", []) + ([model_type] if model_type else [])))
                    for r in roles:
                        if not r:
                            continue
                        self._gate.submit_node(NodeProposal(
                            label="Capability",
                            match_keys={"name": r},
                            provenance=reg_provenance,
                            submitted_by="SwarmGraphIngestor",
                        ))
                        self._gate.submit_edge(EdgeProposal(
                            from_label="Model",
                            from_keys={"name": full_name},
                            rel_type="HAS_CAPABILITY",
                            to_label="Capability",
                            to_keys={"name": r},
                            provenance=reg_provenance,
                            submitted_by="SwarmGraphIngestor",
                        ))
            else:
                with self._driver.session() as session:
                    for full_name, details in models.items():
                        size_text = details.get("parameter_size", "0b").lower()
                        size_val = float(size_text.replace("b", "")) if "b" in size_text else 0.0
                        quant = details.get("quantization_level", "unknown")
                        family = details.get("family", "unknown")
                        model_type = details.get("type", "unknown")
                        session.run("""
                        MERGE (model:Model {name: $name})
                        SET model.family = $family, model.parameters_b = $size,
                            model.quantization = $quant, model.type = $model_type
                        WITH model
                        MATCH (m:Machine {id: $machine_id})
                        MERGE (model)-[:RUNS_ON]->(m)
                        """, name=full_name, family=family, size=size_val,
                            quant=quant, model_type=model_type, machine_id=machine_id)

                        roles = list(set(details.get("role", []) + ([model_type] if model_type else [])))
                        for r in roles:
                            if not r:
                                continue
                            session.run("""
                            MERGE (cap:Capability {name: $cap})
                            WITH cap
                            MATCH (model:Model {name: $model_name})
                            MERGE (model)-[:HAS_CAPABILITY]->(cap)
                            """, cap=r, model_name=full_name)

            print(f"Ingested {len(models)} models for {machine_id}.")
        except Exception as e:
            print(f"Failed to process model registry {filepath}: {e}")

    def discover_tools_and_agents(self):
        """Discover agents and tools. Tools are gated by manifest registry."""
        print("Discovering Agents and Tools...")
        tools_reg_path = ROOT_DIR / "agent_ecosystem/packages/tools/_registry.py"
        agents_reg_path = ROOT_DIR / "agent_ecosystem/packages/agents/_registry.py"

        def _extract_modules(filepath):
            if not filepath.exists():
                return []
            try:
                content = filepath.read_text()
                match = re.search(r"AVAILABLE_MODULES\s*=\s*\[(.*?)\]", content, re.DOTALL)
                if match:
                    clean_str = "[" + match.group(1) + "]"
                    return ast.literal_eval(clean_str)
            except Exception as e:
                print(f"Parse error on {filepath}: {e}")
            return []

        agents = _extract_modules(agents_reg_path)
        tools = _extract_modules(tools_reg_path)

        registry_provenance = Provenance(
            source="registry_scrape", confidence=0.7, evidence=str(agents_reg_path)
        )

        if self._gate:
            for a in agents:
                role = a.split("_")[-1] if a else "unknown"
                self._gate.submit_node(NodeProposal(
                    label="Agent",
                    match_keys={"name": a},
                    properties={"role": role},
                    provenance=registry_provenance,
                    submitted_by="SwarmGraphIngestor",
                ))

            accepted, rejected = 0, 0
            for t in tools:
                result = self._gate.submit_node(NodeProposal(
                    label="Tool",
                    match_keys={"name": t},
                    provenance=Provenance(
                        source="registry_scrape", confidence=0.7, evidence=str(tools_reg_path)
                    ),
                    submitted_by="SwarmGraphIngestor",
                ))
                if result.verdict == ProposalVerdict.REJECTED:
                    logger.info("Tool '%s' rejected by gate: %s", t, result.reason)
                    rejected += 1
                else:
                    accepted += 1
            print(f"Agents: {len(agents)} ingested. Tools: {accepted} accepted, {rejected} rejected (no manifest).")
        else:
            with self._driver.session() as session:
                for a in agents:
                    role = a.split("_")[-1] if a else "unknown"
                    session.run("""
                    MERGE (agent:Agent {name: $name})
                    SET agent.role = $role
                    """, name=a, role=role)
                for t in tools:
                    session.run("""
                    MERGE (tool:Tool {name: $name})
                    SET tool.latency_ms = 0
                    """, name=t)
                print(f"Ingested {len(agents)} agents and {len(tools)} tools.")

    def discover_skills(self):
        """Ingest skills from the controlled dictionary ONLY.

        No more filesystem scraping — skills come from data/skills.yaml
        via the IntakeGate's SkillDictionary.
        """
        if not self._gate:
            logger.warning("No gate configured — skipping skill discovery (would scrape filesystem)")
            return

        skill_names = self._gate.skills.list_all()
        for skill_name in skill_names:
            self._gate.submit_node(NodeProposal(
                label="Skill",
                match_keys={"name": skill_name},
                provenance=Provenance(
                    source="skill_dictionary", confidence=1.0, evidence="data/skills.yaml"
                ),
                submitted_by="SwarmGraphIngestor",
            ))
        print(f"Ingested {len(skill_names)} skills from controlled dictionary.")

    def ingest_agents_from_registry(self, agents_yaml_path):
        """
        Ingest agent registry (config/agents.yaml) into Neo4j.
        Creates (:AGENT)-[:HAS_CAPABILITY]->(:CAPABILITY) and (:AGENT)-[:RUNS_ON]->(:MACHINE).
        """
        import yaml
        path = Path(agents_yaml_path)
        if not path.exists():
            print(f"Agent registry not found: {path}")
            return
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        agents = data.get("agents", {})
        if not agents:
            print("No agents in registry.")
            return
        prov = Provenance(
            source="agent_registry",
            confidence=0.95,
            evidence=str(path),
        )
        for agent_id, spec in agents.items():
            if not isinstance(spec, dict):
                continue
            role = spec.get("role", "worker")
            model = spec.get("model", "unknown")
            caps = spec.get("capabilities") or []
            machine_id = spec.get("machine_id")
            if self._gate:
                self._gate.submit_node(NodeProposal(
                    label="Agent",
                    match_keys={"name": agent_id},
                    properties={"role": role, "model": model},
                    provenance=prov,
                    submitted_by="SwarmGraphIngestor",
                ))
                for cap in caps:
                    if not cap:
                        continue
                    self._gate.submit_node(NodeProposal(
                        label="Capability",
                        match_keys={"name": cap},
                        provenance=prov,
                        submitted_by="SwarmGraphIngestor",
                    ))
                    self._gate.submit_edge(EdgeProposal(
                        from_label="Agent",
                        from_keys={"name": agent_id},
                        rel_type="HAS_CAPABILITY",
                        to_label="Capability",
                        to_keys={"name": cap},
                        provenance=prov,
                        submitted_by="SwarmGraphIngestor",
                    ))
                if machine_id:
                    self._gate.submit_edge(EdgeProposal(
                        from_label="Agent",
                        from_keys={"name": agent_id},
                        rel_type="RUNS_ON",
                        to_label="Machine",
                        to_keys={"id": machine_id},
                        provenance=prov,
                        submitted_by="SwarmGraphIngestor",
                    ))
            else:
                with self._driver.session() as session:
                    session.run(
                        """
                        MERGE (a:Agent {name: $name})
                        SET a.role = $role, a.model = $model
                        """,
                        name=agent_id,
                        role=role,
                        model=model,
                    )
                    for cap in caps:
                        if not cap:
                            continue
                        session.run(
                            """
                            MERGE (c:Capability {name: $cap})
                            WITH c
                            MATCH (a:Agent {name: $agent_id})
                            MERGE (a)-[:HAS_CAPABILITY]->(c)
                            """,
                            cap=cap,
                            agent_id=agent_id,
                        )
                    if machine_id:
                        session.run(
                            """
                            MATCH (a:Agent {name: $agent_id})
                            MATCH (m:Machine {id: $machine_id})
                            MERGE (a)-[:RUNS_ON]->(m)
                            """,
                            agent_id=agent_id,
                            machine_id=machine_id,
                        )
        print(f"Ingested {len(agents)} agents from registry ({path.name}).")


if __name__ == "__main__":
    from core.knowledge_quality.skill_dictionary import SkillDictionary
    from core.knowledge_quality.tool_manifest_registry import ToolManifestRegistry

    driver = GraphDatabase.driver(DB_URI, auth=(DB_USER, DB_PASS))
    gate = IntakeGate(
        driver=driver,
        skill_dictionary=SkillDictionary(),
        tool_manifest_registry=ToolManifestRegistry(),
    )

    ingestor = SwarmGraphIngestor(DB_URI, DB_USER, DB_PASS, gate=gate)
    schema_path = ROOT_DIR / "Raphael/core/memory/knowledge_graph/swarm_architecture_schem.cypher"

    ingestor.execute_schema(schema_path)
    ingestor.ingest_hardware()
    ingestor.ingest_agents_from_registry(ROOT_DIR / "Raphael/config/agents.yaml")
    ingestor.ingest_llm_registry(ROOT_DIR / "agent_ecosystem/local_llm_registry.json", "macbook")
    ingestor.ingest_llm_registry(ROOT_DIR / "agent_ecosystem/desktop_llm_registry.json", "desktop")
    ingestor.discover_tools_and_agents()
    ingestor.discover_skills()
    ingestor.close()
    driver.close()

    print("Graph ingestion completed successfully!")
    print(f"Gate stats: {gate.get_stats()}")
