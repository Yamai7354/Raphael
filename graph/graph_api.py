import logging
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from neo4j import AsyncGraphDatabase

from core.memory.contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)
from core.knowledge_quality.intake_gate import IntakeGate, NodeProposal, Provenance

logger = logging.getLogger("neo4j_graph_store")

# Define the Swarm-Grade allowed schema
ALLOWED_LABELS = {
    # Original ontology
    "Agent",
    "Concept",
    "Episode",
    "Procedure",
    "TaskType",
    "Tool",
    "Model",
    "Skill",
    "MemoryAudit",
    # Swarm Director ontology (Phase 1+)
    "Task",
    "Capability",
    "AgentType",
    "HabitatBlueprint",
    "Service",
    "Machine",
    "Metric",
    "GPU",
}

ALLOWED_RELATIONSHIPS = {
    # Original ontology
    "USES_CONCEPT",
    "INVOLVED_AGENT",
    "AFFECTED_CONCEPT",
    "USED_IN",
    "OPTIMIZES",
    "CREATED_PROCEDURE",
    "DERIVED_FROM",
    "WORKS_WITH",
    "HAS_TRAIT",
    "USES_MODEL",
    "HAS_SKILL",
    "USES_TOOL",
    "FOR_TASK",
    # Swarm Director ontology (Phase 1+)
    "REQUIRES",
    "HAS_CAPABILITY",
    "REQUIRES_CAPABILITY",
    "SPAWNS_AGENT",
    "USES_SERVICE",
    "RUNS_ON",
    "PERFORMANCE",
    "SOLVED_BY",
    "REQUIRES_GPU",
    "HAS_GPU",
}


class Neo4jGraphStore(MemoryContract):
    """MEM-7: Neo4j Implementation of Graph Memory.
    Enforces the Swarm-Grade 3-Embedding Ontology and prevents generic graph sprawl.
    """

    def __init__(self, uri: str, auth: tuple, database: str = "neo4j", gate: IntakeGate = None):
        self.driver = AsyncGraphDatabase.driver(uri, auth=auth)
        self.database = database
        self._gate = gate
        logger.info(f"Initialized Neo4j Swarm-Grade Graph Store at {uri}")

    async def initialize_constraints(self):
        """Build constraints to prevent duplication"""
        constraints = [
            # Original ontology constraints
            "CREATE CONSTRAINT agent_uuid IF NOT EXISTS FOR (a:Agent) REQUIRE a.uuid IS UNIQUE;",
            "CREATE CONSTRAINT concept_uuid IF NOT EXISTS FOR (c:Concept) REQUIRE c.uuid IS UNIQUE;",
            "CREATE CONSTRAINT episode_uuid IF NOT EXISTS FOR (e:Episode) REQUIRE e.uuid IS UNIQUE;",
            "CREATE CONSTRAINT procedure_uuid IF NOT EXISTS FOR (p:Procedure) REQUIRE p.uuid IS UNIQUE;",
            # Swarm Director ontology constraints (Phase 1+)
            "CREATE CONSTRAINT task_uuid IF NOT EXISTS FOR (t:Task) REQUIRE t.uuid IS UNIQUE;",
            "CREATE CONSTRAINT capability_name IF NOT EXISTS FOR (c:Capability) REQUIRE c.name IS UNIQUE;",
            "CREATE CONSTRAINT agenttype_name IF NOT EXISTS FOR (a:AgentType) REQUIRE a.name IS UNIQUE;",
            "CREATE CONSTRAINT habitat_name IF NOT EXISTS FOR (h:HabitatBlueprint) REQUIRE h.name IS UNIQUE;",
            "CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE;",
            "CREATE CONSTRAINT machine_hostname IF NOT EXISTS FOR (m:Machine) REQUIRE m.hostname IS UNIQUE;",
            "CREATE CONSTRAINT metric_uuid IF NOT EXISTS FOR (m:Metric) REQUIRE m.uuid IS UNIQUE;",
            "CREATE CONSTRAINT gpu_uuid IF NOT EXISTS FOR (g:GPU) REQUIRE g.uuid IS UNIQUE;",
        ]
        async with self.driver.session(database=self.database) as session:
            for query in constraints:
                try:
                    await session.run(query)
                except Exception as e:
                    logger.warning(f"Failed to create constraint: {e}")
        logger.info("Neo4j Ontology Constraints Verified.")

    async def close(self):
        await self.driver.close()

    async def verify_connectivity(self) -> bool:
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Neo4j connectivity failed: {e}")
            return False

    async def _unsafe_store_node(self, label: str, properties: Dict[str, Any]):
        """Internal worker to Merge a node based on uuid."""
        if "uuid" not in properties or not properties["uuid"]:
            raise ValueError(f"Cannot store {label} without a valid 'uuid' property")

        query = f"MERGE (n:{label} {{uuid: $uuid}}) SET n += $properties RETURN n"
        async with self.driver.session(database=self.database) as session:
            await session.run(query, uuid=str(properties["uuid"]), properties=properties)
            logger.debug(f"Stored node {label}:{properties['uuid']}")

    async def store_node(self, label: str, uuid: str, memory_type: str, properties: Dict[str, Any]):
        """
        Store an explicitly typed node in the Swarm-Grade schema.
        All nodes MUST have `uuid`, `memory_type`, and `promotion_score`.
        """
        if label not in ALLOWED_LABELS:
            raise ValueError(
                f"Label {label} is not permitted in the Swarm-Grade ontology. "
                f"Allowed: {ALLOWED_LABELS}"
            )

        # Enforce baseline properties
        base_props = {
            "uuid": str(uuid),
            "memory_type": str(memory_type).lower(),
            "promotion_score": float(properties.get("promotion_score", 0.0)),
        }

        # Merge dictionaries, overriding any baseline property misconfigurations
        final_props = {**properties, **base_props}

        if self._gate:
            await self._gate.asubmit_node(
                NodeProposal(
                    label=label,
                    match_keys={"uuid": str(uuid)},
                    properties=final_props,
                    provenance=Provenance(source="neo4j_semantic_sync", confidence=1.0),
                    submitted_by="neo4j_semantic_sync",
                )
            )
            return

        await self._unsafe_store_node(label, final_props)

    async def store(self, payload: MemoryPayload):
        """
        [Legacy Compatibility Method for MemoryContract]
        Interprets generic MemoryPayload into a Concept node.
        """
        if payload.memory_type != MemoryType.SEMANTIC:
            logger.warning(
                f"Neo4jGraphStore rejected non-semantic legacy payload: {payload.memory_type}"
            )
            return

        content = payload.content
        if not isinstance(content, dict):
            content = {"description": str(content)}

        props = {
            "name": content.get("name", f"Concept_{payload.id.hex[:8]}"),
            "description": content.get("description", str(content)),
            "embedding_id": content.get("embedding_id", ""),
            "quality_score": float(content.get("quality_score", 0.0)),
            "last_validated": content.get("last_validated", ""),
            "source_type": content.get("source_type", "distillation"),
            "source_agent": payload.metadata.source_agent,
            "promotion_score": float(content.get("promotion_score", 0.0)),
        }

        # Legacy store mapped to Concept
        await self.store_node(
            label="Concept",
            uuid=str(payload.id),
            memory_type=MemoryType.SEMANTIC.value,
            properties=props,
        )

    async def retrieve(self, query: str, filters: Dict[str, Any]) -> List[MemoryPayload]:
        # Legacy retrieve for MemoryContract backwards compatibility
        is_cypher = "MATCH" in query.upper() or "RETURN" in query.upper()
        results = []
        async with self.driver.session(database=self.database) as session:
            if is_cypher:
                result = await session.run(query, parameters=filters)
            else:
                cypher = f"MATCH (n:{query}) RETURN n LIMIT $limit"
                result = await session.run(cypher, limit=filters.get("limit", 10))

            records = await result.data()
            for record in records:
                for key, val in record.items():
                    if hasattr(val, "get"):
                        props = dict(val)
                        results.append(
                            MemoryPayload(
                                id=UUID(props.get("uuid", props.get("id"))),
                                memory_type=MemoryType(
                                    props.get("memory_type", MemoryType.SEMANTIC.value).upper()
                                ),
                                content=props,
                                metadata=MemoryMetadata(
                                    source_agent=props.get("source_agent", "neo4j"),
                                    confidence=props.get("confidence", 1.0),
                                    tags=props.get("tags", []),
                                ),
                            )
                        )
        return results

    async def forget(self, policy: Dict[str, Any]):
        """Delete nodes based on uuid or label."""
        if "uuid" in policy:
            query = "MATCH (n) WHERE n.uuid = $uuid DETACH DELETE n"
            async with self.driver.session(database=self.database) as session:
                await session.run(query, uuid=policy["uuid"])
        elif "id" in policy:
            query = "MATCH (n) WHERE n.id = $id DETACH DELETE n"
            async with self.driver.session(database=self.database) as session:
                await session.run(query, id=policy["id"])
        elif "label" in policy:
            query = f"MATCH (n:{policy['label']}) DETACH DELETE n"
            async with self.driver.session(database=self.database) as session:
                await session.run(query)

    async def create_relationship(
        self,
        from_uuid: str,
        to_uuid: str,
        relation_type: str,
        properties: Dict[str, Any] = None,
        provenance: Provenance = None,
    ):
        """Explicitly create a relationship between two existing nodes using uuids."""
        if relation_type not in ALLOWED_RELATIONSHIPS:
            raise ValueError(
                f"Relationship type '{relation_type}' is forbidden. "
                f"Swarm-Grade allowed edges: {ALLOWED_RELATIONSHIPS}"
            )

        edge_props = properties or {}

        if self._gate:
            gate_props = {**edge_props, **(provenance.to_props() if provenance else {})}
            query = (
                "MATCH (a), (b) "
                "WHERE a.uuid = $from_uuid AND b.uuid = $to_uuid "
                f"MERGE (a)-[r:{relation_type}]->(b) "
                "SET r += $props "
                "RETURN r"
            )
            async with self.driver.session(database=self.database) as session:
                await session.run(query, from_uuid=from_uuid, to_uuid=to_uuid, props=gate_props)
            return

        query = (
            "MATCH (a), (b) "
            "WHERE a.uuid = $from_uuid AND b.uuid = $to_uuid "
            f"MERGE (a)-[r:{relation_type}]->(b) "
            "SET r += $props "
            "RETURN r"
        )
        async with self.driver.session(database=self.database) as session:
            await session.run(query, from_uuid=from_uuid, to_uuid=to_uuid, props=edge_props)

    async def execute_cypher(
        self, query: str, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Direct execution for complex graph operations."""
        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, parameters=params or {})
            return await result.data()
