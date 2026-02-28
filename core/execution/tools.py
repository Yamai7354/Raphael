import logging
from typing import Dict, Any

from src.raphael.execution.tool_registry import BaseTool
from src.raphael.execution.system_control import SystemController
from src.raphael.execution.code_runner import SandboxedCodeRunner

logger = logging.getLogger(__name__)


class BashExecutionTool(BaseTool):
    """
    Allows agents to execute safe Bash commands, such as running test suites (pytest),
    checking file contents, or exploring the environment.
    """

    def __init__(self):
        super().__init__(
            name="bash_execute",
            description="Executes a sterile bash command. Useful for running tests and debugging.",
        )
        self.controller = SystemController()

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = params.get("command")
        if not command:
            return {"error": "Missing required parameter: 'command'"}

        timeout = params.get("timeout", 15)
        return self.controller.execute_command(command=command, timeout=timeout)


class PythonExecutionTool(BaseTool):
    """
    Allows agents to run ephemeral Python scripts in a sandbox.
    Useful for quick logic validation or localized reasoning testing.
    """

    def __init__(self):
        super().__init__(
            name="python_execute",
            description="Executes a raw python string script in a sandbox. Provide 'code_content'.",
        )
        self.runner = SandboxedCodeRunner()

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        code_content = params.get("code_content")
        if not code_content:
            return {"error": "Missing required parameter: 'code_content'"}

        timeout = params.get("timeout", 15)
        return self.runner.execute_script(
            language="python", code_content=code_content, timeout=timeout
        )
