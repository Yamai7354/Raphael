"""
Node State Cache for AI Router.

Provides an in-memory authoritative cache of all node states.
The cache is the single source of truth for routing decisions.
"""

import logging
from typing import Dict, Optional, Any
from .node_state import NodeState, NodeStateInfo

logger = logging.getLogger("ai_router.state_cache")


class NodeStateCache:
    """
    In-memory cache holding the state of all configured nodes.
    This cache is the router's "truth" for routing decisions.
    """

    def __init__(self):
        self._nodes: Dict[str, NodeStateInfo] = {}

    def register_node(
        self,
        node_id: str,
        initial_state: NodeState = NodeState.OFFLINE,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a new node with an initial state and attributes.
        Called during startup for configured nodes or dynamically for discovered nodes.
        """
        if node_id in self._nodes:
            # If node exists, we might want to update attributes?
            # For now, let's allow updating attributes if provided
            if attributes:
                self._nodes[node_id].attributes.update(attributes)
                logger.info("node_id=%s attributes updated", node_id)
            return

        self._nodes[node_id] = NodeStateInfo(node_id, initial_state, attributes)
        logger.info(
            "node_id=%s registered with state=%s attributes=%s",
            node_id,
            initial_state.value,
            attributes,
        )

    def get_node(self, node_id: str) -> Optional[NodeStateInfo]:
        """
        Retrieve the state info for a specific node.
        Returns None if the node is not registered.
        """
        return self._nodes.get(node_id)

    def update_state(self, node_id: str, new_state: NodeState, reason: str) -> None:
        """
        Update the state of a node. Only health checks should call this.
        """
        node = self._nodes.get(node_id)
        if node is None:
            logger.error("node_id=%s not found in cache, cannot update state", node_id)
            return
        node.transition_to(new_state, reason)

    def update_latency(self, node_id: str, latency_ms: float) -> None:
        """
        Update the latency measurement for a node.
        """
        node = self._nodes.get(node_id)
        if node:
            node.latency_ms = latency_ms

    def increment_error_count(self, node_id: str) -> None:
        """
        Increment the error count for a node.
        """
        node = self._nodes.get(node_id)
        if node:
            node.error_count += 1

    def reset_error_count(self, node_id: str) -> None:
        """
        Reset the error count for a node (e.g., on successful recovery).
        """
        node = self._nodes.get(node_id)
        if node:
            node.error_count = 0

    def get_all_nodes(self) -> Dict[str, NodeStateInfo]:
        """
        Return a read-only view of all nodes.
        """
        return dict(self._nodes)

    def get_ready_nodes(self) -> Dict[str, NodeStateInfo]:
        """
        Return only nodes that are in READY state.
        Used by routing logic.
        """
        return {
            node_id: info
            for node_id, info in self._nodes.items()
            if info.state == NodeState.READY
        }

    def list_online_nodes(self) -> list[NodeStateInfo]:
        """
        Return a list of all nodes that are not OFFLINE.
        """
        return [
            info for info in self._nodes.values() if info.state != NodeState.OFFLINE
        ]

    def to_dict(self) -> dict:
        """
        Return a dictionary representation of the entire cache.
        Useful for API responses.
        """
        return {node_id: info.to_dict() for node_id, info in self._nodes.items()}

    def get_all_nodes_as_dicts(self) -> list[Dict[str, Any]]:
        """
        Return a list of node dictionaries, merging static config structure
        with current attributes. This allows the Router to iterate over
        all nodes (static + dynamic) uniformly.
        """
        nodes = []
        for node_id, info in self._nodes.items():
            # Base node dict resembling config structure
            node_data = {"id": node_id}
            # Merge attributes (url, role, etc.)
            node_data.update(info.attributes)
            nodes.append(node_data)
        return nodes


# Global singleton instance
node_cache = NodeStateCache()
