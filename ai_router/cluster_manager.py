"""
Cluster Manager for AI Router.

Handles dynamic node registration, deregistration, and health management.
Manages the lifecycle of nodes in the cluster.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from .node_state import node_state_manager, NodeState, NodeStateInfo
from .capabilities import capability_registry, NodeCapabilities
from .alerting import alerting_system

logger = logging.getLogger("ai_router.cluster")


class ClusterManager:
    """
    Manages cluster membership and health.
    """

    def __init__(self):
        self.health_check_interval = 60  # seconds

    def register_node(
        self,
        node_id: str,
        capabilities: Dict[str, Any],
    ) -> bool:
        """
        Register a new node dynamically (Ticket 1).
        """
        # 1. Register state
        node_state_manager.register_node(node_id)

        # 2. Register capabilities
        caps = NodeCapabilities(
            node_id=node_id,
            max_context_supported=capabilities.get("max_context_length", 32768),
            supported_model_sizes=tuple(capabilities.get("supported_model_sizes", [])),
            supported_quantizations=tuple(
                capabilities.get("supported_quantizations", ("any",))
            ),
            vram_gb=capabilities.get("vram_gb", 16),
        )
        capability_registry.register_node(caps)

        # 3. Mark as JOINING/ONLINE
        node_state_manager.transition_node(
            node_id, NodeState.ONLINE, "dynamic_registration"
        )

        logger.info("node_registered node_id=%s caps=%s", node_id, caps)

        # Alert if new capacity added
        alerting_system.record_alert(
            "node_joined", f"Node {node_id} joined the cluster", "info"
        )
        return True

    def deregister_node(self, node_id: str, reason: str = "manual") -> bool:
        """
        Deregister a node (graceful shutdown).
        """
        info = node_state_manager.get_node_info(node_id)
        if not info:
            return False

        # Mark offline immediately to stop routing
        node_state_manager.transition_node(
            node_id, NodeState.OFFLINE, f"deregister_{reason}"
        )

        # In a real system, we'd drain active connections here

        logger.info("node_deregistered node_id=%s reason=%s", node_id, reason)
        return True

    async def handle_node_failure(self, node_id: str, error: str) -> None:
        """
        Handle a reported node failure (Ticket 5).
        """
        info = node_state_manager.get_node_info(node_id)
        if not info:
            return

        info.error_count += 1

        # Threshold for cooldown
        if info.error_count >= 3:
            if not info.is_in_cooldown():
                info.enter_cooldown(f"too_many_errors: {error}")
                # Mark as DEGRADED or OFFLINE depending on policy
                # For now, cooldown logic in NodeState handles the 'not ready' aspect
                # but we explicitly mark DEGRADED for visibility
                node_state_manager.transition_node(
                    node_id, NodeState.DEGRADED, "error_threshold_exceeded"
                )

                alerting_system.record_alert(
                    "node_degraded",
                    f"Node {node_id} entered cooldown (errors: {info.error_count})",
                    "warning",
                )


# Global singleton
cluster_manager = ClusterManager()
