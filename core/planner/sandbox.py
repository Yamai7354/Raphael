import os
import subprocess
import resource
import asyncio
import logging
import shlex
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger("core.planning.sandbox")


@dataclass
class SandboxLimits:
    """Resource limits for a sandbox."""

    max_memory_mb: int = 128
    max_cpu_sec: int = 10
    max_processes: int = 20
    timeout_sec: float = 30.0
    allowed_dirs: Set[str] = field(default_factory=set)
    forbidden_env: Set[str] = field(
        default_factory=lambda: {"API_KEY", "SECRET_KEY", "PASSWORD", "TOKEN"}
    )


class Sandbox(ABC):
    """
    Abstract base class for sandboxed execution.
    """

    @abstractmethod
    async def run_command(
        self, command: str, env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Run a command within the sandbox."""
        pass


class LocalProcessSandbox(Sandbox):
    """
    Sandboxes local subprocesses using resource limits and path validation.
    """

    def __init__(self, limits: SandboxLimits):
        self.limits = limits

    def _set_limits(self):
        """Set resource limits for the current (child) process."""
        import sys

        try:
            # Memory limit (RLIMIT_AS - Address Space)
            mem_bytes = self.limits.max_memory_mb * 1024 * 1024

            # Helper to set limit safely
            def set_limit_safe(res, value, name):
                try:
                    soft, hard = resource.getrlimit(res)
                    # We can't set soft/hard higher than current hard without root
                    new_hard = hard if hard != resource.RLIM_INFINITY else value
                    new_soft = min(value, new_hard)
                    resource.setrlimit(res, (new_soft, new_hard))
                except Exception as e:
                    sys.stderr.write(f"Warning: Failed to set {name}: {e}\n")

            set_limit_safe(resource.RLIMIT_AS, mem_bytes, "RLIMIT_AS")
            # Also try RLIMIT_RSS for physical memory
            set_limit_safe(resource.RLIMIT_RSS, mem_bytes, "RLIMIT_RSS")

            # CPU limit (RLIMIT_CPU)
            set_limit_safe(resource.RLIMIT_CPU, self.limits.max_cpu_sec, "RLIMIT_CPU")

            # Process limit (RLIMIT_NPROC)
            set_limit_safe(
                resource.RLIMIT_NPROC, self.limits.max_processes, "RLIMIT_NPROC"
            )

        except Exception as e:
            sys.stderr.write(f"Critical error in preexec_fn: {e}\n")

    def _is_path_safe(self, path: str) -> bool:
        """Check if a path is within the allowed directories."""
        if not self.limits.allowed_dirs:
            return True  # No restriction if set is empty (Open sandbox)

        abs_path = os.path.abspath(path)
        for allowed in self.limits.allowed_dirs:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True
        return False

    def _validate_command(self, command: str) -> bool:
        """Perform basic validation on the command string."""
        # This is a basic check. Real hardening would involve parsing args.
        parts = shlex.split(command)
        for part in parts:
            if part.startswith("/") or part.startswith(".."):
                if not self._is_path_safe(part):
                    logger.warning("sandbox_path_violation path=%s", part)
                    return False
        return True

    async def run_command(
        self, command: str, env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute command with limits.
        """
        if not self._validate_command(command):
            return {
                "success": False,
                "error": "Forbidden path access detected in command.",
                "stdout": "",
                "stderr": "",
            }

        # Filter environment
        safe_env = {}
        target_env = env or os.environ.copy()
        for k, v in target_env.items():
            if k not in self.limits.forbidden_env:
                safe_env[k] = v

        try:
            # Note: resource.setrlimit must be called in the child process via preexec_fn
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
                preexec_fn=self._set_limits,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.limits.timeout_sec
                )

                return {
                    "success": process.returncode == 0,
                    "returncode": process.returncode,
                    "stdout": stdout.decode().strip(),
                    "stderr": stderr.decode().strip(),
                }
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except:
                    pass
                return {
                    "success": False,
                    "error": f"Command timed out after {self.limits.timeout_sec}s",
                    "stdout": "",
                    "stderr": "",
                }

        except Exception as e:
            logger.error("sandbox_execution_failed error=%s", str(e))
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}
