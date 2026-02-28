import logging
import asyncio
from typing import Dict, Any, Optional
from collections import defaultdict
from datetime import datetime

from event_bus.event_bus import Event
from . import bus

logger = logging.getLogger("ai_router.perception")


class PerceptionService:
    """
    Aggregates events from the ecosystem to build a 'perceived' state of the system.
    This includes tracking task load on nodes, detecting anomalies, and eventually
    fusing multi-modal inputs.
    """

    def __init__(self):
        self._running = False
        self._task_counts: Dict[str, int] = defaultdict(int)
        self._last_update: datetime = datetime.now()
        self._processed_events = 0

    async def start(self):
        """Start the perception service and subscribe to events."""
        if self._running:
            return

        self._running = True
        logger.info("PerceptionService starting...")

        if bus.event_bus:
            # Subscribe to relevant topics
            await bus.event_bus.subscribe("task.routed", self._handle_task_routed)
            await bus.event_bus.subscribe("agent.announce", self._handle_agent_announce)
            await bus.event_bus.subscribe("task.completed", self._handle_task_completed)
            await bus.event_bus.subscribe("task.failed", self._handle_task_failed)

            logger.info("PerceptionService subscribed to events.")
        else:
            logger.warning(
                "Event bus not available, PerceptionService cannot subscribe."
            )

    async def stop(self):
        """Stop the perception service."""
        self._running = False
        logger.info("PerceptionService stopped.")

    async def _handle_task_routed(self, event: Event):
        """
        Handle 'task.routed' events.
        Update local view of node load.
        """
        try:
            payload = event.payload
            node_id = payload.get("node_id")
            task_id = payload.get("task_id")

            if node_id:
                self._task_counts[node_id] += 1
                self._processed_events += 1
                self._last_update = datetime.now()

                count = self._task_counts[node_id]

                # Basic 'Fusion' Logic: Detect high load
                # In a real system, this would be more complex (windowed, weighted, etc.)
                if count % 10 == 0:
                    logger.info(
                        f"perception_fusion node={node_id} accumulated_tasks={count} status=HIGH_TRAFFIC"
                    )
                else:
                    logger.debug(
                        f"perception_update node={node_id} task={task_id} total_node_tasks={count}"
                    )

        except Exception as e:
            logger.error(f"Error handling task.routed event: {e}")

    async def _handle_agent_announce(self, event: Event):
        """
        Handle 'agent.announce' events for dynamic discovery.
        Register the agent with the NodeStateCache.
        """
        try:
            payload = event.payload
            agent_id = payload.get("id")
            if not agent_id:
                logger.warning("Agent announcement missing 'id' field.")
                return

            # Extract attributes that Router expects (url, role, model, etc.)
            attributes = {
                "url": payload.get("url"),
                "role": payload.get("role"),
                "model": payload.get("model"),
                "capabilities": payload.get("capabilities", []),
                "name": payload.get("name", agent_id),
            }

            logger.info(f"Discovered dynamic agent: {agent_id} ({attributes['role']})")

            # Register in state cache (authoritative source)
            # We import here to avoid circular dependencies if possible, or use global
            from .state_cache import node_cache
            from .node_state import NodeState

            # Start as ONLINE or READY depending on confidence?
            # Let's start as ONLINE and let health check upgrade it,
            # OR trusting the announcement, set to ONLINE immediately.
            # Warning: checks rely on attributes being present.
            node_cache.register_node(
                agent_id, initial_state=NodeState.ONLINE, attributes=attributes
            )

        except Exception as e:
            logger.error(f"Error handling agent.announce event: {e}")

    async def _handle_task_completed(self, event: Event):
        """
        Handle 'task.completed' events.
        Update success metrics in NodeStateCache.
        """
        try:
            payload = event.payload
            node_id = payload.get("node_id")
            if not node_id:
                return

            from .state_cache import node_cache

            node_info = node_cache.get_node(node_id)
            if node_info:
                node_info.success_count += 1
                node_info.total_requests += 1
                node_info.last_success_time = datetime.now()
                logger.debug(
                    f"perception_score_update node={node_id} success={node_info.success_count} total={node_info.total_requests} score={node_info.score:.2f}"
                )

        except Exception as e:
            logger.error(f"Error handling task.completed event: {e}")

    async def _handle_task_failed(self, event: Event):
        """
        Handle 'task.failed' events.
        Update failure metrics in NodeStateCache.
        """
        try:
            payload = event.payload
            node_id = payload.get("node_id")
            if not node_id:
                return

            from .state_cache import node_cache

            node_info = node_cache.get_node(node_id)
            if node_info:
                node_info.total_requests += 1
                node_info.error_count += 1
                logger.debug(
                    f"perception_score_update node={node_id} success={node_info.success_count} total={node_info.total_requests} score={node_info.score:.2f}"
                )

        except Exception as e:
            logger.error(f"Error handling task.failed event: {e}")

    def get_state(self) -> Dict[str, Any]:
        """Return the current perceived state."""
        return {
            "task_counts": dict(self._task_counts),
            "events_processed": self._processed_events,
            "last_update": self._last_update.isoformat(),
        }


# Global Singleton
perception_service = PerceptionService()
