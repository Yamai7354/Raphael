import logging
from typing import Any, Dict, List
from core.src.agent_core.agent import Agent
from core.src.bus.event_bus import Event

logger = logging.getLogger("experiment_agent")


class ExperimentAgent(Agent):
    """
    Agent responsible for proposing, designing, and executing systematic experiments.
    """

    def __init__(self, name: str = "ExperimentAgent", role: str = "experimentation"):
        super().__init__(name, role)
        self.bus = None

    async def start(self, bus):
        """Start the agent and subscribe to events."""
        self.bus = bus
        # TODO: Subscribe to experiment events
        logger.info(f"{self.name} started.")

    def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def plan(self, goal: str) -> List[str]:
        return []

    def act(self, action: str) -> str:
        return ""
