import os
from typing import Optional
from graph.graph_api import Neo4jGraphStore

_GLOBAL_GRAPH_CLIENT: Optional[Neo4jGraphStore] = None


def get_graph_client() -> Neo4jGraphStore:
    """
    Returns a configured instance of the Neo4jGraphStore.
    Uses environment variables for connection pooling.
    This singleton can be passed into AgentContext.
    """
    global _GLOBAL_GRAPH_CLIENT

    if _GLOBAL_GRAPH_CLIENT is None:
        # Load from environment, fallback to standard defaults for local k3d
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")

        # Instantiate the official Swarm-Grade graph memory contract
        _GLOBAL_GRAPH_CLIENT = Neo4jGraphStore(uri=uri, auth=(user, password))

    return _GLOBAL_GRAPH_CLIENT


async def close_graph_client():
    """Gracefully close the Neo4j connection pool."""
    global _GLOBAL_GRAPH_CLIENT
    if _GLOBAL_GRAPH_CLIENT is not None:
        await _GLOBAL_GRAPH_CLIENT.close()
        _GLOBAL_GRAPH_CLIENT = None
