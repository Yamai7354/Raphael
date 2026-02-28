import logging
from typing import Any, Dict, List
from core.src.agent_core.agent import Agent
from core.src.bus.event_bus import Event

logger = logging.getLogger("system_monitor_agent")


class SystemMonitorAgent(Agent):
    """
    Agent responsible for monitoring the health, uptime, and general status of the system.
    """

    def __init__(self, name: str = "SystemMonitor", role: str = "monitoring"):
        super().__init__(name, role)
        self.bus = None

    async def start(self, bus):
        """Start the agent and subscribe to events."""
        self.bus = bus
        # TODO: Subscribe to health and status events
        logger.info(f"{self.name} started.")

    def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def plan(self, goal: str) -> List[str]:
        return []

    def act(self, action: str) -> str:
        return ""
