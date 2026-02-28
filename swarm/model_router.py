import httpx
import logging

logger = logging.getLogger(__name__)


class ModelRouter:
    """
    Maintains a mapping of available agents and their capabilities.
    Matches execution tasks to the optimal compatible agent by querying the NodeManager.
    """

    def __init__(self, manager_url: str = "http://localhost:9000"):
        self.manager_url = manager_url.rstrip("/")

    async def find_agent(self, required_capabilities: list[str]) -> str | None:
        """
        Scans the swarm for a node that possesses ALL required capabilities.
        Returns the Node ID, or None if no match is found.
        """
        if not required_capabilities:
            # Default to a general node if no specific tools are needed
            logger.debug("No capabilities required, defaulting to general routing.")
            return "agent_omega"

        req_set = set(required_capabilities)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.manager_url}/swarm/nodes")
                if response.status_code != 200:
                    logger.error(f"Failed to query NodeManager: {response.status_code}")
                    return None

                nodes = response.json().get("nodes", [])

                # Each 'node' in the swarm now acts as a provider for these capabilities
                for node in nodes:
                    node_id = node.get("node_id")
                    # In our registry, we map node models or roles to capabilities
                    # For simplicity, we assume node.models contains capability tags
                    node_caps = set(node.get("models", []))

                    if req_set.issubset(node_caps):
                        logger.info(
                            f"ModelRouter matched {required_capabilities} to node {node_id}"
                        )
                        return str(node_id)

        except Exception as e:
            logger.error(f"Error connecting to NodeManager at {self.manager_url}: {e}")

        logger.warning(f"Model Router failed to find any node matching {required_capabilities}.")
        return None
