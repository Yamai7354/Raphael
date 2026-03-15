"""
GraphReasoner — Queries the Neo4j knowledge graph for habitat decisions.

Responsibilities:
  - Find which capabilities are needed for a task
  - Find which habitat blueprints provide those capabilities
  - Return ranked blueprint candidates with their agent/service manifests
"""

import logging

from graph.graph_api import Neo4jGraphStore
from director.models import BlueprintCandidate

logger = logging.getLogger("director.graph_reasoner")


class GraphReasoner:
    """Queries the knowledge graph to reason about infrastructure needs."""

    def __init__(self, graph_store: Neo4jGraphStore):
        self._graph = graph_store

    async def find_blueprints_for_capabilities(
        self, capabilities: list[str]
    ) -> list[BlueprintCandidate]:
        """
        Given required capabilities, find all habitat blueprints that provide them.
        Returns candidates ranked by how many capabilities they match.
        """
        query = """
        UNWIND $capabilities AS cap_name
        MATCH (h:HabitatBlueprint)-[:REQUIRES_CAPABILITY]->(c:Capability {name: cap_name})
        WITH h, collect(DISTINCT c.name) AS matched_caps, count(DISTINCT c) AS match_count

        // Get all agents this habitat spawns
        OPTIONAL MATCH (h)-[sa:SPAWNS_AGENT]->(a:AgentType)
        WITH h, matched_caps, match_count,
             collect(DISTINCT {name: a.name, count: sa.count, role: sa.role}) AS agents

        // Get all services this habitat uses
        OPTIONAL MATCH (h)-[:USES_SERVICE]->(s:Service)
        WITH h, matched_caps, match_count, agents,
             collect(DISTINCT s.name) AS services

        RETURN h.name AS name,
               h.helmChart AS helmChart,
               h.recommendedAgents AS recommendedAgents,
               matched_caps AS capabilities,
               agents,
               services,
               match_count AS score
        ORDER BY score DESC
        """
        results = await self._graph.execute_cypher(query, {"capabilities": capabilities})

        candidates = []
        for row in results:
            candidates.append(
                BlueprintCandidate(
                    name=row["name"],
                    helm_chart=row["helmChart"],
                    recommended_agents=row["recommendedAgents"],
                    capabilities=row["capabilities"],
                    agents=row["agents"],
                    services=row["services"],
                    score=float(row["score"]),
                )
            )

        logger.info(f"Found {len(candidates)} blueprints for capabilities {capabilities}")
        return candidates

    async def get_blueprint_details(self, blueprint_name: str) -> BlueprintCandidate | None:
        """Get full details of a specific blueprint."""
        query = """
        MATCH (h:HabitatBlueprint {name: $name})
        OPTIONAL MATCH (h)-[:REQUIRES_CAPABILITY]->(c:Capability)
        WITH h, collect(DISTINCT c.name) AS caps
        OPTIONAL MATCH (h)-[sa:SPAWNS_AGENT]->(a:AgentType)
        WITH h, caps, collect(DISTINCT {name: a.name, count: sa.count, role: sa.role}) AS agents
        OPTIONAL MATCH (h)-[:USES_SERVICE]->(s:Service)
        RETURN h.name AS name,
               h.helmChart AS helmChart,
               h.recommendedAgents AS recommendedAgents,
               caps AS capabilities,
               agents,
               collect(DISTINCT s.name) AS services
        """
        results = await self._graph.execute_cypher(query, {"name": blueprint_name})
        if not results:
            return None

        row = results[0]
        return BlueprintCandidate(
            name=row["name"],
            helm_chart=row["helmChart"],
            recommended_agents=row["recommendedAgents"],
            capabilities=row["capabilities"],
            agents=row["agents"],
            services=row["services"],
        )

    async def record_task_solution(self, task_uuid: str, blueprint_name: str):
        """Record that a task was solved by a specific blueprint."""
        query = """
        MATCH (t:Task {uuid: $task_uuid})
        MATCH (h:HabitatBlueprint {name: $blueprint_name})
        MERGE (t)-[:SOLVED_BY]->(h)
        """
        await self._graph.execute_cypher(
            query, {"task_uuid": task_uuid, "blueprint_name": blueprint_name}
        )
        logger.info(f"Recorded: Task {task_uuid} solved by {blueprint_name}")
