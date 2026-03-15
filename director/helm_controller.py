"""
HelmController — Manages Helm chart deployments for habitats.

Responsibilities:
  - Install a habitat Helm chart into the cluster
  - Uninstall a habitat release
  - List active habitat releases
  - Check release status
"""

import asyncio
import logging
import os

logger = logging.getLogger("director.helm_controller")


class HelmController:
    """Controls Helm operations for habitat lifecycle management."""

    def __init__(
        self,
        kubeconfig: str | None = None,
        helm_config_home: str | None = None,
        helm_cache_home: str | None = None,
        helm_data_home: str | None = None,
        namespace: str = "habitats",
    ):
        self._namespace = namespace
        self._env = os.environ.copy()
        if kubeconfig:
            self._env["KUBECONFIG"] = kubeconfig
        if helm_config_home:
            self._env["HELM_CONFIG_HOME"] = helm_config_home
        if helm_cache_home:
            self._env["HELM_CACHE_HOME"] = helm_cache_home
        if helm_data_home:
            self._env["HELM_DATA_HOME"] = helm_data_home

    async def _run_helm(self, args: list[str]) -> tuple[int, str, str]:
        """Execute a helm command and return (returncode, stdout, stderr)."""
        cmd = ["helm"] + args
        logger.debug(f"Running: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def install(
        self,
        release_name: str,
        chart_path: str,
        values_overrides: dict | None = None,
        timeout: str = "5m",
    ) -> bool:
        """Install a habitat Helm chart."""
        args = [
            "install",
            release_name,
            chart_path,
            "-n",
            self._namespace,
            "--create-namespace",
            "--timeout",
            timeout,
        ]

        if values_overrides:
            for key, value in values_overrides.items():
                args.extend(["--set", f"{key}={value}"])

        returncode, stdout, stderr = await self._run_helm(args)

        if returncode == 0:
            logger.info(f"Installed habitat release: {release_name}")
            return True
        else:
            logger.error(f"Failed to install {release_name}: {stderr}")
            return False

    async def uninstall(self, release_name: str) -> bool:
        """Uninstall a habitat release."""
        args = ["uninstall", release_name, "-n", self._namespace]
        returncode, stdout, stderr = await self._run_helm(args)

        if returncode == 0:
            logger.info(f"Uninstalled habitat release: {release_name}")
            return True
        else:
            logger.error(f"Failed to uninstall {release_name}: {stderr}")
            return False

    async def status(self, release_name: str) -> dict | None:
        """Get status of a habitat release."""
        args = ["status", release_name, "-n", self._namespace, "-o", "json"]
        returncode, stdout, stderr = await self._run_helm(args)

        if returncode == 0:
            import json

            return json.loads(stdout)
        return None

    async def list_releases(self) -> list[dict]:
        """List all active habitat releases."""
        args = ["list", "-n", self._namespace, "-o", "json"]
        returncode, stdout, stderr = await self._run_helm(args)

        if returncode == 0:
            import json

            return json.loads(stdout) if stdout.strip() else []
        return []

    async def is_running(self, release_name: str) -> bool:
        """Check if a release is currently deployed."""
        status = await self.status(release_name)
        return status is not None and status.get("info", {}).get("status") == "deployed"
