# swarm_optimizer_agent.py
# Improves routing decisions in the knowledge graph

import os
import random
import logging
from neo4j import GraphDatabase

from core.knowledge_quality.intake_gate import (
    IntakeGate,
    NodeProposal,
    EdgeProposal,
    Provenance,
)

logger = logging.getLogger("knowledge_graph.optimizer")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def update_model_performance(gate: IntakeGate = None):
    with driver.session() as session:
        results = session.run("""
        MATCH (m:Model)-[:RUNS_ON]->(machine:Machine)
        RETURN m.name AS model, machine.id AS machine, m.quantization AS quant
        """)

        for record in results:
            tokens_per_sec = random.randint(10, 80)
            quant = record.get("quant") or "unknown"

            if gate:
                gate.submit_node(NodeProposal(
                    label="PerformanceProfile",
                    match_keys={
                        "model": record["model"],
                        "machine": record["machine"],
                        "quantization": quant,
                    },
                    properties={
                        "tokens_per_sec": tokens_per_sec,
                        "latency_ms": 0,
                    },
                    provenance=Provenance(
                        source="optimization_agent",
                        confidence=0.7,
                        evidence="synthetic benchmark",
                    ),
                    submitted_by="graph_optimization_agent",
                ))
            else:
                session.run("""
                MERGE (p:PerformanceProfile {model:$model, machine:$machine})
                SET p.tokens_per_sec = $speed,
                    p.last_updated = timestamp()
                """, model=record["model"], machine=record["machine"],
                    speed=tokens_per_sec)


def rebalance_cluster(gate: IntakeGate = None):
    if gate:
        # Read machines over threshold, then submit updates through gate
        with driver.session() as session:
            results = session.run("""
            MATCH (machine:Machine)
            WHERE machine.cpu_usage > 85
            RETURN machine.id AS id
            """)
            for record in results:
                gate.submit_node(NodeProposal(
                    label="Machine",
                    match_keys={"id": record["id"]},
                    properties={"status": "overloaded"},
                    provenance=Provenance(
                        source="optimization_agent",
                        confidence=0.9,
                        evidence="cpu_usage > 85%",
                    ),
                    submitted_by="graph_optimization_agent",
                ))
    else:
        with driver.session() as session:
            session.run("""
            MATCH (machine:Machine)
            WHERE machine.cpu_usage > 85
            SET machine.status = "overloaded"
            """)


def optimize_routing_scores():
    # Read-only scoring update — no gate needed (operates on existing data)
    with driver.session() as session:
        session.run("""
        MATCH (m:Model)-[r:HAS_CAPABILITY]->(c:Capability)
        MATCH (p:PerformanceProfile {model:m.name})
        SET r.score = p.tokens_per_sec / 100.0
        """)


def main(gate: IntakeGate = None):
    update_model_performance(gate)
    rebalance_cluster(gate)
    optimize_routing_scores()


if __name__ == "__main__":
    from core.knowledge_quality.skill_dictionary import SkillDictionary
    from core.knowledge_quality.tool_manifest_registry import ToolManifestRegistry

    gate = IntakeGate(
        driver=driver,
        skill_dictionary=SkillDictionary(),
        tool_manifest_registry=ToolManifestRegistry(),
    )
    main(gate)
    print(f"Optimization complete. Gate stats: {gate.get_stats()}")
