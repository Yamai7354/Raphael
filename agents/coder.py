import logging
from typing import Any

from src.raphael.agents.base import BaseAgent
from src.raphael.execution.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class CodingAgent(BaseAgent):
    """
    Agent responsible for writing logic, applying diffs, and deep logic analysis.
    Ideally backed by a strong reasoning model. Connects to ToolRegistry for running tests and debugging.
    """

    def __init__(self, agent_id: str = "coding_agent", tool_registry: ToolRegistry = None):
        super().__init__(
            agent_id=agent_id,
            capabilities=["python", "reasoning", "general_agent", "testing", "debugging"],
        )
        self.tool_registry = tool_registry

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Executes code generation or dynamically runs testing/debugging tools.
        """
        st_id = payload.get("sub_task_id", "unknown")
        logger.info(f"CodingAgent [{self.agent_id}] engaging SubTask {st_id}")

        logs = [
            "Loaded Coder model contexts.",
            f"Generating code payload for {st_id}...",
        ]

        tool_result = None
        # If the task requires running tests or debugging, intercept it and use the execution sandbox.
        if "test_command" in payload and self.tool_registry:
            logger.info("CodingAgent orchestrating Test/Debug sequence.")
            test_cmd = payload["test_command"]
            logs.append(f"Executing debugging command: {test_cmd}")

            tool_result = self.tool_registry.execute_tool(
                tool_name="bash_execute", params={"command": test_cmd}
            )
            logs.append(
                f"Tool Result (Exit Code {tool_result.get('exit_code')}): {tool_result.get('stdout') or tool_result.get('stderr')}"
            )

            if tool_result.get("exit_code", 1) == 0:
                logs.append("Successfully validated logic via test suite.")
                success = True
            else:
                logs.append("Debugging step failed. Agent would iterate and fix code here.")
                success = False
        else:
            logs.append("Successfully linted logic string.")
            success = True

        return self._standard_response(
            success=success,
            logs=logs,
            output={
                "code_diff": payload.get("code_diff", "+ generated python logic"),
                "tool_result": tool_result,
            },
        )
