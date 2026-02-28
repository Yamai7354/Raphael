import logging
from typing import Any
from src.raphael.agents.base import BaseAgent
from src.raphael.execution.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class UniversalAgent(BaseAgent):
    """
    A generalist agent that can execute any task by mapping its required
    capabilities directly to tools in the ToolRegistry.
    """

    def __init__(self, agent_id: str, tool_registry: ToolRegistry):
        # Universal agents claim to support whatever the registry has
        super().__init__(agent_id=agent_id, capabilities=list(tool_registry._tools.keys()))
        self.tool_registry = tool_registry

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        st_id = payload.get("sub_task_id", "unknown")
        req_caps = payload.get("capabilities", [])

        logger.info(
            f"UniversalAgent [{self.agent_id}] evaluating task {st_id} with caps {req_caps}"
        )
        logs = [f"UniversalAgent dispatching based on capabilities: {req_caps}"]

        if not req_caps:
            return self._standard_response(
                success=False,
                logs=logs,
                error="No capabilities specified for UniversalAgent execution.",
            )

        # Pick the first matching tool
        target_tool = None
        if "bash" in req_caps and "bash_execute" in self.tool_registry._tools:
            target_tool = "bash_execute"
        elif "python" in req_caps and "python_execute" in self.tool_registry._tools:
            target_tool = "python_execute"

        if not target_tool:
            # Fallback search
            for cap in req_caps:
                if cap in self.tool_registry._tools:
                    target_tool = cap
                    break

        if not target_tool:
            return self._standard_response(
                success=False,
                logs=logs,
                error=f"No matching tool found in registry for caps: {req_caps}",
            )

        # Prepare parameters
        params = {}
        if target_tool == "bash_execute":
            params["command"] = payload.get("command") or payload.get("description")
        elif target_tool == "python_execute":
            params["code_content"] = (
                payload.get("code_content") or payload.get("code") or payload.get("command")
            )
        else:
            # Generic mapping
            params = payload

        logs.append(f"Executing tool: {target_tool}")
        tool_result = self.tool_registry.execute_tool(target_tool, params)

        success = tool_result.get("exit_code") == 0 or "exit_code" not in tool_result
        logs.append(f"Tool execution completed. Success: {success}")

        return self._standard_response(success=success, logs=logs, output=tool_result)
