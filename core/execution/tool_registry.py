import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Standard interface for all external APIs and executable Tools.
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the tool logic and returns a standardized output map."""
        pass


class ToolRegistry:
    """
    Central hub for Agent Swarms to discover and trigger external capabilities.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool):
        """Binds an instantiated tool to the registry."""
        self._tools[tool.name] = tool
        logger.debug(f"Tool [{tool.name}] mounted to registry.")

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieves a tool, executes it with standard logging, and catches crashes.
        """
        if tool_name not in self._tools:
            logger.error(f"Attempted to execute unregistered tool: {tool_name}")
            return {"error": f"Tool '{tool_name}' not found."}

        tool = self._tools[tool_name]
        logger.info(f"Executing Tool '{tool_name}' with params: {params}")

        try:
            result = tool.execute(params)
            # Log the successful output
            logger.debug(f"Tool '{tool_name}' produced output: {result}")
            return result

        except Exception as e:
            logger.error(f"Tool '{tool_name}' encountered critical failure: {e}")
            return {"error": str(e)}
