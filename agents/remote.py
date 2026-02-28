import logging
import asyncio
from typing import Dict, Any, List

from src.raphael.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class RemoteAgent(BaseAgent):
    """
    Agent responsible for executing tasks on external hardware nodes via SSH or RPC.
    """

    def __init__(self, agent_id: str, ip_address: str, capabilities: List[str]):
        super().__init__(agent_id=agent_id, capabilities=capabilities)
        self.ip_address = ip_address

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock execution of an external hardware payload.
        """
        st_id = payload.get("sub_task_id", "unknown")
        logger.info(f"RemoteAgent [{self.agent_id} @ {self.ip_address}] engaging SubTask {st_id}")

        await asyncio.sleep(0.1)

        logs = [
            f"Established secure connection to {self.ip_address}.",
            f"Offloaded task payload {st_id} to external node hardware.",
            f"Received successful execution signal from remote.",
        ]

        return self._standard_response(
            success=True, logs=logs, output={"remote_ip": self.ip_address, "status": "executed"}
        )
