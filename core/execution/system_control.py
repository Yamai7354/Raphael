import logging
import subprocess
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SystemController:
    """
    Wraps the Python subprocess module to execute raw shell commands.
    Includes basic safety heuristics to block globally destructive commands.
    """

    # A tiny mock block-list. Layer 4 SafetyGate catches logic patterns,
    # but Layer 8 intercepts literal destructive lexicons.
    BLOCKED_PHRASES = ["rm -rf /", "chmod 777 -R /", "mkfs"]

    def __init__(self):
        pass

    def _is_safe(self, command_string: str) -> bool:
        """Inspects the command for hardcoded malicious strings."""
        for phrase in self.BLOCKED_PHRASES:
            if phrase in command_string:
                return False
        return True

    def execute_command(self, command: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Fires a blocking shell sequence.
        Returns {"stdout": str, "stderr": str, "exit_code": int}
        """
        logger.info(f"SystemController preparing to execute: `{command}`")

        if not self._is_safe(command):
            logger.critical(f"SystemController dynamically blocked unsafe command: `{command}`")
            return {
                "stdout": "",
                "stderr": "BLOCKED: Command violates core safety heuristics.",
                "exit_code": 1,
            }

        try:
            # shell=True is risky; this is where sandboxing the environment is critical
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )

            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"Command `{command}` hit {timeout}s execution timeout.")
            return {
                "stdout": "",
                "stderr": f"TIMEOUT: Execution exceeded {timeout} seconds.",
                "exit_code": 124,
            }
        except Exception as e:
            logger.error(f"SystemController encountered execution crash: {e}")
            return {"stdout": "", "stderr": str(e), "exit_code": 1}
