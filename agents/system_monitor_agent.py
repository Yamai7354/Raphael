import logging
from typing import Any, Dict, List
from agents.base_agent import BaseAgent
from data.schemas import SystemEvent, EventType

logger = logging.getLogger("system_monitor_agent")


class SystemMonitorAgent(BaseAgent):
    """
    Agent responsible for monitoring the health, uptime, and general status of the system.
    """

    def __init__(self, agent_id: str = "SystemMonitor", capabilities: List[str] = None):
        super().__init__(agent_id, capabilities or ["monitoring", "health_check"])
        self.bus = None

    async def start(self, bus):
        """Start the agent and subscribe to events."""
        self.bus = bus
        # Subscribe to health and status events
        self.bus.subscribe(EventType.CRASH_REPORT, self._handle_crash_report)
        self.bus.subscribe(EventType.OBSERVATION, self._handle_observation)
        logger.info(f"{self.agent_id} started and subscribed to health events.")

    async def _handle_crash_report(self, event: SystemEvent):
        """Handle crash reports by logging them."""
        logger.error(f"SystemMonitor: Received CRASH_REPORT: {event.payload}")

    async def _handle_observation(self, event: SystemEvent):
        """Handle telemetry observations."""
        if event.payload.get("metric_type") == "telemetry":
            logger.debug(f"SystemMonitor: Received telemetry: {event.payload.get('data')}")

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a monitoring task.
        """
        logs = [f"SystemMonitor executing task with payload: {payload}"]
        # Implementation for specific monitoring tasks can be added here
        return self._standard_response(True, logs, {"status": "monitoring_active"})

    def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def plan(self, goal: str) -> List[str]:
        return []

    def act(self, action: str) -> str:
        return ""
