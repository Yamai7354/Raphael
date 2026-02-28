import logging
from typing import Any

logger = logging.getLogger(__name__)


class GovernanceCouncil:
    """
    Establishes system-wide policies and resolves conflicts between competing
    directives or autonomous agents.
    """

    def __init__(self, initial_priority: list[str] | None = None):
        # A simple priority matrix: Lower index = Higher priority
        self.priority_matrix = initial_priority or [
            "system_health",  # P0: Keep the OS alive
            "security",  # P1: Maintain sandbox boundaries
            "user_directive",  # P2: Explicit user commands
            "autonomous_research",  # P3: Self-prompted exploration
            "idle_optimization",  # P4: Background defrag/cleanup
        ]
        logger.info(f"GovernanceCouncil initialized with priorities: {self.priority_matrix}")

    async def sync_priority_with_graph(self, graph_store: Any):
        """
        [DYNAMIC] Queries the Neo4j Operational Graph for the current consensus priority.
        Allows the swarm to adjust its own governance based on historical success.
        """
        try:
            # Query the PriorityPolicy nodes
            query = "MATCH (p:PriorityPolicy) RETURN p.sequence ORDER BY p.updated_at DESC LIMIT 1"
            result = await graph_store.execute_cypher(query)
            if result and "p.sequence" in result[0]:
                self.priority_matrix = result[0]["p.sequence"]
                logger.info(f"GovernanceCouncil synced with graph: {self.priority_matrix}")
        except Exception as e:
            logger.warning(
                f"GovernanceCouncil: Failed to sync with graph, using defaults. Error: {e}"
            )

    def resolve_conflict(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Takes a list of competing requests and approves the one with the highest
        systemic priority.
        """
        if not requests:
            return {}

        best_request = None
        best_priority_idx = len(self.priority_matrix)

        for req in requests:
            category = req.get("category", "unknown")

            # Find the priority index for this category
            try:
                idx = self.priority_matrix.index(category)
            except ValueError:
                idx = len(self.priority_matrix)  # Lowest possible priority if unknown

            if idx < best_priority_idx:
                best_priority_idx = idx
                best_request = req

        winner_id = best_request.get("request_id") if best_request else "none"
        logger.info(
            f"GovernanceCouncil resolved conflict between {len(requests)} requests. Winner: {winner_id}"
        )

        return {
            "approved_request_id": best_request.get("request_id") if best_request else None,
            "category": best_request.get("category") if best_request else "unknown",
            "resolution_reason": f"Highest priority class: index {best_priority_idx}",
        }
