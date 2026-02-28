import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    The polymorphic foundation for all Swarm Agents.
    Forces child classes to implement a standard `execute()` method
    and provide a standard `{success, logs, output}` payload schema.
    """

    def __init__(self, agent_id: str, capabilities: list[str]):
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.domain_success_tracker: dict[str, int] = {}
        self.specialization_threshold = 5  # Example threshold

    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Executes a specific subtask from an Execution Plan.

        Must return:
        {
            "success": bool,
            "logs": list[str],
            "output": any
        }
        """
        pass

    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Wrapper around execute() to inject automated memory tracking.
        """
        sub_task_id = str(payload.get("sub_task_id", "UNKNOWN"))

        logger.debug(f"Agent {self.agent_id} starting task {sub_task_id}")

        try:
            # Operational tracking for active assignment
            # await operational_kg.record_task(...)
            pass
        except Exception as e:
            logger.warning(f"Failed to record task start to KG: {e}")

        # Execute the agent's core capability
        result = await self.execute(payload)

        try:
            # Log the outcome to Portfolio Tracker
            # We fire and forget as a non-blocking task
            asyncio.create_task(self._log_to_portfolio(sub_task_id, result))

            # Log to long-term memory
            # await episodic_memory.log_event(...)

            # Specialization Drift Logic
            if result.get("success"):
                domain = payload.get("domain", "general")
                self._record_domain_success(domain)

        except Exception as e:
            logger.warning(f"Failed to record session outcome: {e}")

        return result

    def _record_domain_success(self, domain: str):
        """Tracks domain successes and triggers specialization drift."""
        if domain not in self.domain_success_tracker:
            self.domain_success_tracker[domain] = 0

        self.domain_success_tracker[domain] += 1

        if self.domain_success_tracker[domain] >= self.specialization_threshold:
            # Trigger specialization drift
            new_specialization = f"expert_{domain}"
            if new_specialization not in self.capabilities:
                self.capabilities.append(new_specialization)
                logger.info(
                    f"Specialization Drift: Agent {self.agent_id} specialized as {new_specialization}"
                )
                # Optional: Reset or scale threshold to require more successes for next tier
                self.domain_success_tracker[domain] = 0
                self.specialization_threshold = int(self.specialization_threshold * 1.5)

    async def _log_to_portfolio(self, task_id: str, result: dict[str, Any]):
        """Helper to log session entry to Portfolio Suite."""
        # In a real integration, this could call the PortfolioAgent via the Bus
        # or directly invoke the subprocess for speed.
        msg = f"Agent {self.agent_id} completed {task_id}. Success: {result.get('success')}"
        logger.info(f"Portfolio Log: {msg}")
        # Note: Direct CLI integration could go here if Raphael has portfolio dependency

    def _standard_response(
        self, success: bool, logs: list[str], output: Any = None, **kwargs
    ) -> dict[str, Any]:
        """Helper to ensure all agents return the correct schema format."""
        resp = {"success": success, "logs": logs, "output": output}
        resp.update(kwargs)
        return resp
