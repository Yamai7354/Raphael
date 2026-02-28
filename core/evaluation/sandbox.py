import logging
import uuid
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SandboxManager:
    """
    Interface for provisioning and tearing down isolated Execution bounds.
    (e.g., spinning up a Docker container instead of the native subprocess runner)
    """

    def __init__(self, mode: str = "mock"):
        # "mock" runs the provisioning logic but doesn't actually bind Docker APIs natively yet
        # "docker" would import the docker-py SDK
        self.mode = mode
        self.active_sandboxes: Dict[str, Dict[str, Any]] = {}

    def provision_environment(self, image: str = "python:3.11-slim") -> str:
        """
        Requests an isolated sandbox capable of running arbitrary logic securely.
        Returns the unique Sandbox ID.
        """
        sandbox_id = f"sbx-{uuid.uuid4().hex[:8]}"

        logger.info(
            f"SandboxManager [{self.mode}] provisioning isolated environment: {sandbox_id} based on {image}"
        )

        if self.mode == "mock":
            # Just track the metadata
            self.active_sandboxes[sandbox_id] = {"image": image, "status": "running"}
            return sandbox_id

        elif self.mode == "docker":
            logger.critical(
                "Native Docker binding requested but SDK is not implemented in logic yet."
            )
            raise NotImplementedError(
                "Layer 9 native containerization requires the 'docker' python package."
            )

        return sandbox_id

    def execute_in_sandbox(self, sandbox_id: str, command: str) -> Dict[str, Any]:
        """
        Forwards a command directly into the provisioned container.
        """
        if sandbox_id not in self.active_sandboxes:
            logger.error(f"Attempted to execute in missing sandbox: {sandbox_id}")
            return {"exit_code": 1, "stderr": "Sandbox ID not found.", "stdout": ""}

        logger.debug(f"SandboxManager routing command to {sandbox_id}: `{command}`")

        if self.mode == "mock":
            # Mock an execution success without risking the host
            return {
                "exit_code": 0,
                "stdout": f"Mock output from container {sandbox_id}",
                "stderr": "",
            }

    def teardown_environment(self, sandbox_id: str) -> bool:
        """Destroys the isolated container, enforcing aggressive cleanup."""
        if sandbox_id in self.active_sandboxes:
            logger.info(f"SandboxManager tearing down sandbox: {sandbox_id}")
            del self.active_sandboxes[sandbox_id]
            return True
        return False
