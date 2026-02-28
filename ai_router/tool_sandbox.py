from typing import Dict, Any, Optional
from .tools import ToolAdapter, ToolConfig, ToolType
from raphael.core.planning.sandbox import LocalProcessSandbox, SandboxLimits


class ShellTool(ToolAdapter):
    """
    A tool that executes shell commands within a sandbox.
    """

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        if not self.config.sandbox_limits:
            # Default limits if none provided
            self.config.sandbox_limits = SandboxLimits()
        self.sandbox = LocalProcessSandbox(self.config.sandbox_limits)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command provided in inputs.
        """
        command = inputs.get("command")
        if not command:
            raise ValueError("No command provided for ShellTool")

        env = inputs.get("env")

        result = await self.sandbox.run_command(command, env=env)
        return result

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate that a command is present."""
        if "command" not in inputs:
            raise ValueError("ShellTool requires a 'command' input")
        return True


def create_restricted_shell(
    name: str = "secure_shell", allowed_dirs: Optional[set] = None
) -> ShellTool:
    """Helper to create a sandboxed shell tool."""
    limits = SandboxLimits(
        max_memory_mb=64,
        max_cpu_sec=5,
        allowed_dirs=allowed_dirs or {"/tmp", "/Users/yamai/ai/agent_ecosystem/data"},
    )

    config = ToolConfig(
        name=name,
        tool_type=ToolType.SYSTEM,
        description="A sandboxed shell for restricted command execution",
        allowed_roles={"sysadmin", "coder"},
        sandbox_limits=limits,
    )

    return ShellTool(config)
