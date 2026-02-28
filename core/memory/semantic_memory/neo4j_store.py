import logging
import json
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from neo4j import GraphDatabase, AsyncGraphDatabase

from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)

logger = logging.getLogger("neo4j_graph_store")


class Neo4jGraphStore(MemoryContract):
    """MEM-7: Neo4j Implementation of Graph Memory.
    Stores entities and relationships for structured knowledge.
    """

    def __init__(self, uri: str, auth: tuple, database: str = "neo4j"):
        self.driver = AsyncGraphDatabase.driver(uri, auth=auth)
        self.database = database
        logger.info(f"Initialized Neo4j Graph Store at {uri}")

    async def close(self):
        await self.driver.close()

    async def verify_connectivity(self) -> bool:
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Neo4j connectivity failed: {e}")
            return False

    async def store(self, payload: MemoryPayload):
        """Store a memory as a node in the graph."""
        # This is a generic store. For graph, we expect specific structure or we default to a generic 'Concept' node.
        # Payload content should ideally be a dict with 'label' and 'properties'.

        content = payload.content
        if not isinstance(content, dict):
            # Fallback: Store execution log or simple node
            content = {"content": str(content)}

        label = content.get("label", "Concept")
        properties = content.get("properties", {})

        # Ensure ID depends on payload ID
        properties["id"] = str(payload.id)
        properties["memory_type"] = payload.memory_type.value

        # Add metadata
        properties["source_agent"] = payload.metadata.source_agent
        if payload.metadata.confidence:
            properties["confidence"] = payload.metadata.confidence
        if payload.metadata.tags:
            properties["tags"] = payload.metadata.tags

        query = f"MERGE (n:{label} {{id: $id}}) SET n += $properties RETURN n"

        async with self.driver.session(database=self.database) as session:
            await session.run(query, id=str(payload.id), properties=properties)
            logger.debug(f"Stored node {label}:{payload.id}")

    async def retrieve(
        self, query: str, filters: Dict[str, Any]
    ) -> List[MemoryPayload]:
        """Retrieve memories using Cypher query."""
        # If query is a Cypher query, execute it.
        # Otherwise, perform a full-text search or simple match.

        is_cypher = "MATCH" in query.upper() or "RETURN" in query.upper()

        results = []
        async with self.driver.session(database=self.database) as session:
            if is_cypher:
                result = await session.run(query, parameters=filters)
            else:
                # Simple label/property search
                # query is treated as a label here for simplicity in this MVP
                cypher = f"MATCH (n:{query}) RETURN n LIMIT $limit"
                result = await session.run(cypher, limit=filters.get("limit", 10))

            records = await result.data()
            for record in records:
                # We expect the query to return 'n' or similar nodes.
                # Flatten the result structure
                for key, val in record.items():
                    # Assuming val is a Node-like dict
                    if hasattr(val, "get"):
                        props = dict(val)
                        # Reconstruct payload
                        # This is lossy if we don't store strict types, but sufficient for Phase 4.5
                        results.append(
                            MemoryPayload(
                                id=UUID(props.get("id")),
                                memory_type=MemoryType(
                                    props.get("memory_type", MemoryType.SEMANTIC.value)
                                ),
                                content=props,  # Return full properties as content
                                metadata=MemoryMetadata(
                                    source_agent=props.get("source_agent", "neo4j"),
                                    confidence=props.get("confidence", 1.0),
                                    tags=props.get("tags", []),
                                ),
                            )
                        )
        return results

    async def forget(self, policy: Dict[str, Any]):
        """Delete nodes based on policy."""
        if "id" in policy:
            query = "MATCH (n) WHERE n.id = $id DETACH DELETE n"
            async with self.driver.session(database=self.database) as session:
                await session.run(query, id=policy["id"])
        elif "label" in policy:
            query = f"MATCH (n:{policy['label']}) DETACH DELETE n"
            async with self.driver.session(database=self.database) as session:
                await session.run(query)

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        relation_type: str,
        properties: Dict[str, Any] = None,
    ):
        """Explicitly create a relationship between two existing nodes."""
        query = (
            "MATCH (a), (b) "
            "WHERE a.id = $from_id AND b.id = $to_id "
            f"MERGE (a)-[r:{relation_type}]->(b) "
            "SET r += $props "
            "RETURN r"
        )
        async with self.driver.session(database=self.database) as session:
            await session.run(
                query, from_id=from_id, to_id=to_id, props=properties or {}
            )

    async def execute_cypher(
        self, query: str, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Direct execution for complex graph operations."""
        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, parameters=params or {})
            return await result.data()
