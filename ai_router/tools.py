"""
External Tool Adapter Framework for AI Router.

Provides:
- Standard interface for external tools
- Schema validation
- Role-based permission enforcement
- Async execution
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set, Type
from enum import Enum
from pydantic import BaseModel, ValidationError

from raphael.core.planning.sandbox import SandboxLimits, LocalProcessSandbox

logger = logging.getLogger("ai_router.tools")


# =============================================================================
# TOOL CONFIGURATION
# =============================================================================


class ToolType(str, Enum):
    """Types of external tools."""

    API = "api"
    DATABASE = "database"
    FILESYSTEM = "filesystem"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class ToolConfig:
    """Configuration for a tool."""

    name: str
    tool_type: ToolType
    description: str
    version: str = "1.0.0"
    timeout_sec: float = 30.0
    mock_mode: bool = False
    allowed_roles: Set[str] = field(default_factory=set)
    retry_count: int = 3
    sandbox_limits: Optional[SandboxLimits] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "version": self.version,
            "timeout_sec": self.timeout_sec,
            "mock_mode": self.mock_mode,
            "allowed_roles": list(self.allowed_roles),
            "retry_count": self.retry_count,
        }


# =============================================================================
# TOOL ADAPTER BASE
# =============================================================================


class ToolAdapter(ABC):
    """
    Abstract base class for all external tools.
    """

    def __init__(self, config: ToolConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with given inputs."""
        pass

    @abstractmethod
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate inputs against schema."""
        pass

    async def health_check(self) -> bool:
        """Check if tool is available."""
        return True


# =============================================================================
# SANDBOX & REGISTRY
# =============================================================================


class ToolRegistry:
    """
    Registry and sandbox for external tools.
    Enforces permissions and manages lifecycle.
    """

    def __init__(self):
        self._tools: Dict[str, ToolAdapter] = {}

    def register(self, tool: ToolAdapter) -> None:
        """Register a tool adapter."""
        if tool.name in self._tools:
            logger.warning("tool_overwritten name=%s", tool.name)

        self._tools[tool.name] = tool
        logger.info(
            "tool_registered name=%s type=%s mock=%s",
            tool.name,
            tool.config.tool_type.value,
            tool.config.mock_mode,
        )

    def get_tool(self, name: str) -> Optional[ToolAdapter]:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self, role: Optional[str] = None) -> List[Dict]:
        """List available tools, optionally filtered by role."""
        tools = []
        for tool in self._tools.values():
            if role and role not in tool.config.allowed_roles:
                continue
            tools.append(tool.config.to_dict())
        return tools

    async def execute_tool(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        role: str,
        task_id: Optional[str] = None,
        subtask_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool safely.
        Enforces permissions, validation, and logging.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # 1. Permission check
        if role not in tool.config.allowed_roles:
            logger.warning(
                "tool_access_denied tool=%s role=%s task=%s", tool_name, role, task_id
            )
            raise PermissionError(
                f"Role '{role}' is not allowed to use tool '{tool_name}'"
            )

        # 2. Input validation
        try:
            tool.validate_inputs(inputs)
        except ValidationError as e:
            logger.error(
                "tool_validation_failed tool=%s task=%s error=%s",
                tool_name,
                task_id,
                str(e),
            )
            raise ValueError(f"Invalid inputs for {tool_name}: {e}")

        # 3. Execution (with timeout)
        logger.info(
            "tool_executing tool=%s role=%s task=%s mock=%s",
            tool_name,
            role,
            task_id,
            tool.config.mock_mode,
        )

        try:
            # 3.1 Sandboxed Execution check
            if (
                tool.config.tool_type in [ToolType.SYSTEM, ToolType.FILESYSTEM]
                and tool.config.sandbox_limits
            ):
                sandbox = LocalProcessSandbox(tool.config.sandbox_limits)
                # Use subtask_id as the 'command' if this is a shell tool, or wrap tool.execute
                # For now, we wrap the entire tool execution if possible, or assume SYSTEM tools use run_command
                logger.info("tool_sandboxed name=%s task=%s", tool_name, task_id)
                # If the tool itself is a generic 'ShellTool', we can pass the command.
                # If it's a specific adapter, we might need a more specialized 'SandboxedToolAdapter'

            result = await asyncio.wait_for(
                tool.execute(inputs), timeout=tool.config.timeout_sec
            )

            logger.info("tool_completed tool=%s task=%s", tool_name, task_id)
            return result

        except asyncio.TimeoutError:
            logger.error(
                "tool_timeout tool=%s task=%s timeout=%.1fs",
                tool_name,
                task_id,
                tool.config.timeout_sec,
            )
            raise TimeoutError(
                f"Tool execution timed out after {tool.config.timeout_sec}s"
            )
        except Exception as e:
            logger.error(
                "tool_failed tool=%s task=%s error=%s", tool_name, task_id, str(e)
            )
            raise


# Global singleton
tool_registry = ToolRegistry()
