import logging
import subprocess
from typing import Any

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class PortfolioAgent(BaseAgent):
    """
    Agent responsible for interfacing with the Portfolio Suite.
    Handles doc generation, diagramming, and reporting.
    """

    def __init__(self, agent_id: str, portfolio_root: str):
        super().__init__(
            agent_id, ["documentation", "diagramming", "reporting", "github_management"]
        )
        self.portfolio_root = portfolio_root
        self.python_exe = "python"  # Assuming python is in path, otherwise use absolute venv path

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action")
        target_path = payload.get("target_path", "/Users/yamai/ai/Raphael")
        logs = []

        try:
            if action == "generate_docs":
                cmd = [self.python_exe, "-m", "tools.cli", "docs", "generate", target_path]
                return await self._run_portfolio_command(cmd, "Documentation generated", logs)

            elif action == "generate_readme":
                cmd = [self.python_exe, "-m", "tools.cli", "docs", "readme", target_path]
                return await self._run_portfolio_command(cmd, "README generated", logs)

            elif action == "generate_diagrams":
                # Architecture diagram
                cmd = [self.python_exe, "-m", "tools.cli", "diagram", "architecture", target_path]
                return await self._run_portfolio_command(
                    cmd, "Architecture diagram generated", logs
                )

            elif action == "generate_report":
                report_type = payload.get("report_type", "daily")
                cmd = [self.python_exe, "-m", "tools.cli", "report", report_type]
                return await self._run_portfolio_command(
                    cmd, f"{report_type.capitalize()} report generated", logs
                )

            elif action == "log_session":
                message = payload.get("message", "Routine activity")
                log_type = payload.get("log_type", "note")
                cmd = [
                    self.python_exe,
                    "-m",
                    "tools.cli",
                    "track",
                    "log",
                    message,
                    "--type",
                    log_type,
                ]
                return await self._run_portfolio_command(cmd, "Session entry logged", logs)

            return self._standard_response(False, logs, f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"PortfolioAgent failure: {e}")
            logs.append(str(e))
            return self._standard_response(False, logs, str(e))

    async def _run_portfolio_command(
        self, cmd: list[str], success_msg: str, logs: list[str]
    ) -> dict[str, Any]:
        """Runs a command with correct CWD and environment."""
        process = subprocess.run(cmd, cwd=self.portfolio_root, capture_output=True, text=True)
        if process.returncode == 0:
            logs.append(process.stdout)
            return self._standard_response(True, logs, success_msg)
        else:
            logs.append(process.stderr)
            return self._standard_response(False, logs, f"Command failed: {process.stderr}")
