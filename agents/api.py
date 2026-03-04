"""
Formal Agent Interfaces — APIs for agents to interact with Neo4j and the event bus.

Contract:
- Agents receive an optional AgentContext (event_bus, graph_client) via constructor.
- When context is provided (e.g. by AgentRouter), agents MUST use it for publishing
  events and querying the graph instead of creating their own connections.
- When context is omitted (standalone tests, CLI), agents may fall back to creating
  a default SystemEventBus() for publishing; graph operations are no-ops if no client.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    from event_bus.event_bus import SystemEventBus

logger = logging.getLogger("agents.api")


@dataclass
class AgentContext:
    """
    Injected dependencies for agents running inside the swarm.
    Passed by AgentRouter (or Director) so all agents share the same event bus
    and optional graph connection.
    """

    event_bus: "SystemEventBus"
    """Shared system event bus. Use for publish/subscribe instead of creating a new bus."""

    graph_client: Optional[Any] = None
    """
    Optional Neo4j graph client (e.g. Neo4jGraphStore or a read-only wrapper).
    When set, agents may query capabilities, blueprints, or write task outcomes.
    When None, agents skip graph operations (e.g. in tests or minimal deployments).
    """

    def publish(self, event: Any) -> Any:
        """Publish an event to the bus. Returns the coroutine; caller must await if in async context."""
        return self.event_bus.publish(event)

    async def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Run a read-only or write Cypher query if graph_client is available.
        Returns empty list if no client or on error.
        """
        if not self.graph_client or not hasattr(self.graph_client, "execute_cypher"):
            return []
        try:
            return await self.graph_client.execute_cypher(query, params or {})
        except Exception as e:
            logger.warning("Agent graph query failed: %s", e)
            return []


def get_event_bus(
    context_or_bus: Optional[Union["AgentContext", "SystemEventBus"]] = None,
) -> "SystemEventBus":
    """
    Return the event bus from context, an injected bus, or a default for standalone use.
    Agents should use this instead of instantiating SystemEventBus() directly.
    """
    if context_or_bus is None:
        from event_bus.event_bus import SystemEventBus
        return SystemEventBus()
    if hasattr(context_or_bus, "event_bus"):  # AgentContext
        return context_or_bus.event_bus
    return context_or_bus  # already a SystemEventBus
