import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


def _load_capabilities_fallback(capabilities_path: Path | None = None) -> dict[str, list[str]] | None:
    """Load data/capabilities.json (by_agent map). Returns None if file missing."""
    if capabilities_path is None:
        capabilities_path = Path("data/capabilities.json")
    if not capabilities_path.exists():
        return None
    try:
        with open(capabilities_path) as f:
            data = json.load(f)
        by_agent = data.get("by_agent")
        return by_agent if isinstance(by_agent, dict) else None
    except Exception as e:
        logger.warning("Failed to load capabilities.json: %s", e)
        return None


class ModelRouter:
    """
    Maintains a mapping of available agents and their capabilities.
    Matches execution tasks to the optimal compatible agent by querying the NodeManager.
    Falls back to data/capabilities.json (from config/agents.yaml) when NodeManager is unavailable.
    """

    def __init__(
        self,
        manager_url: str = "http://localhost:9000",
        capabilities_json_path: Path | str | None = None,
    ):
        self.manager_url = manager_url.rstrip("/")
        self.capabilities_path = Path(capabilities_json_path) if capabilities_json_path else None

    async def find_agent(self, required_capabilities: list[str]) -> str | None:
        """
        Scans the swarm for a node that possesses ALL required capabilities.
        Returns the Node ID, or None if no match is found.
        """
        if not required_capabilities:
            logger.debug("No capabilities required, defaulting to general routing.")
            return "agent_omega"

        req_set = set(required_capabilities)

        # 1. Try NodeManager (swarm nodes)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.manager_url}/swarm/nodes")
                if response.status_code == 200:
                    nodes = response.json().get("nodes", [])
                    for node in nodes:
                        node_id = node.get("node_id")
                        node_caps = set(node.get("models", []))
                        if req_set.issubset(node_caps):
                            logger.info(
                                "ModelRouter matched %s to node %s",
                                required_capabilities,
                                node_id,
                            )
                            return str(node_id)
        except Exception as e:
            logger.debug("NodeManager unavailable, using capability map fallback: %s", e)

        # 2. Fallback: capability map from agents.yaml / capabilities.json
        by_agent = _load_capabilities_fallback(self.capabilities_path)
        if by_agent:
            for agent_id, caps in by_agent.items():
                if isinstance(caps, list) and req_set.issubset(set(caps)):
                    logger.info(
                        "ModelRouter (fallback) matched %s to agent %s",
                        required_capabilities,
                        agent_id,
                    )
                    return agent_id

        logger.warning(
            "Model Router failed to find any node matching %s.",
            required_capabilities,
        )
        return None
