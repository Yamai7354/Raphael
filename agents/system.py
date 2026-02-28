import logging
from typing import Any

from src.raphael.agents.base import BaseAgent
from src.raphael.execution.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class SystemAgent(BaseAgent):
    """
    Agent responsible for OS-level interactions, filesystem manipulation, and raw command execution.
    """

    def __init__(self, agent_id: str = "system_agent", tool_registry: ToolRegistry = None):
        super().__init__(agent_id=agent_id, capabilities=["bash", "filesystem", "python"])
        self.tool_registry = tool_registry

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Executes a system command via the ToolRegistry.
        """
        st_id = payload.get("sub_task_id", "unknown")
        command = payload.get("command")

        logger.info(f"SystemAgent [{self.agent_id}] engaging SubTask {st_id}")

        if not self.tool_registry:
            return self._standard_response(
                success=False,
                logs=["ToolRegistry not available to SystemAgent."],
                error="ToolRegistry missing",
            )

        if not command:
            return self._standard_response(
                success=False,
                logs=["No command provided in payload."],
                error="Missing 'command' parameter",
            )

        logs = [f"Executing bash command for {st_id}: {command}"]

        # Execute via registry
        tool_result = self.tool_registry.execute_tool(
            tool_name="bash_execute", params={"command": command}
        )

        success = tool_result.get("exit_code") == 0
        logs.append(f"Command execution finish with exit code: {tool_result.get('exit_code')}")

        return self._standard_response(
            success=success,
            logs=logs,
            output=tool_result,
        )
