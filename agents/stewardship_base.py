import logging
from abc import abstractmethod
from typing import Dict, Any, List
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class DatabaseStewardAgent(BaseAgent):
    """
    Base class for agents that monitor, validate, and repair databases.
    """

    def __init__(self, agent_id: str, capabilities: List[str]):
        super().__init__(agent_id, capabilities)
        self.health_metrics = {}

    @abstractmethod
    async def validate(self) -> Dict[str, Any]:
        """Runs validation checks on the database."""
        pass

    @abstractmethod
    async def repair(self, issues: Dict[str, Any]) -> Dict[str, Any]:
        """Runs repair sequences based on found issues."""
        pass

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a stewardship cycle.
        Payload can specify 'action': 'validate', 'repair', or 'full_cycle'.
        """
        action = payload.get("action", "full_cycle")
        logs = []

        try:
            if action in ["validate", "full_cycle"]:
                logs.append(f"Starting validation for {self.agent_id}...")
                issues = await self.validate()
                self.health_metrics = issues
                logs.append(f"Validation complete. Issues found: {issues}")

                if action == "full_cycle" and issues:
                    logs.append("Initiating autonomous repairs...")
                    repair_results = await self.repair(issues)
                    logs.append(f"Repair cycle complete: {repair_results}")
                    return self._standard_response(
                        True, logs, {"issues": issues, "repairs": repair_results}
                    )

                return self._standard_response(True, logs, issues)

            elif action == "repair":
                issues = payload.get("issues", {})
                logs.append(f"Starting manual repair for {self.agent_id}...")
                results = await self.repair(issues)
                return self._standard_response(True, logs, results)

            return self._standard_response(False, logs, f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Stewardship failure in {self.agent_id}: {e}")
            logs.append(f"Critical Error: {str(e)}")
            return self._standard_response(False, logs, str(e))
