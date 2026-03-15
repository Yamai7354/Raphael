"""
HabitatMonitor — Monitors running habitats and their health.

Responsibilities:
  - Poll Helm releases for status
  - Detect failed or stale habitats
  - Trigger cleanup for expired habitats (TTL-based)
  - Report habitat health to the Director
"""

import asyncio
import logging
import time

from director.helm_controller import HelmController

logger = logging.getLogger("director.habitat_monitor")


class HabitatRecord:
    """Tracks a running habitat's lifecycle."""

    __slots__ = (
        "release_name",
        "blueprint_name",
        "task_id",
        "deployed_at",
        "ttl_seconds",
        "last_check",
        "healthy",
    )

    def __init__(
        self, release_name: str, blueprint_name: str, task_id: str, ttl_seconds: int = 3600
    ):
        self.release_name = release_name
        self.blueprint_name = blueprint_name
        self.task_id = task_id
        self.deployed_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.last_check = 0.0
        self.healthy = True

    @property
    def expired(self) -> bool:
        return (time.time() - self.deployed_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.deployed_at


class HabitatMonitor:
    """Monitors running habitats and manages their lifecycle."""

    def __init__(self, helm: HelmController, check_interval: float = 30.0):
        self._helm = helm
        self._habitats: dict[str, HabitatRecord] = {}
        self._check_interval = check_interval
        self._running = False

    def register(self, record: HabitatRecord):
        """Register a newly deployed habitat for monitoring."""
        self._habitats[record.release_name] = record
        logger.info(
            f"Monitoring habitat: {record.release_name} "
            f"(blueprint={record.blueprint_name}, ttl={record.ttl_seconds}s)"
        )

    def unregister(self, release_name: str):
        """Stop monitoring a habitat."""
        self._habitats.pop(release_name, None)

    async def check_all(self) -> dict[str, list[str]]:
        """
        Check all registered habitats.
        Returns: {"healthy": [...], "unhealthy": [...], "expired": [...]}
        """
        result = {"healthy": [], "unhealthy": [], "expired": []}

        for name, record in list(self._habitats.items()):
            if record.expired:
                result["expired"].append(name)
                logger.warning(f"Habitat {name} has expired (age={record.age_seconds:.0f}s)")
                continue

            is_running = await self._helm.is_running(name)
            record.last_check = time.time()
            record.healthy = is_running

            if is_running:
                result["healthy"].append(name)
            else:
                result["unhealthy"].append(name)
                logger.warning(f"Habitat {name} is unhealthy")

        return result

    async def cleanup_expired(self) -> list[str]:
        """Uninstall all expired habitats. Returns list of cleaned up release names."""
        cleaned = []
        for name, record in list(self._habitats.items()):
            if record.expired:
                success = await self._helm.uninstall(name)
                if success:
                    self.unregister(name)
                    cleaned.append(name)
                    logger.info(f"Cleaned up expired habitat: {name}")
        return cleaned

    async def run(self):
        """Run the monitoring loop (call from Director)."""
        self._running = True
        logger.info(f"Monitor loop started (interval={self._check_interval}s)")
        while self._running:
            try:
                status = await self.check_all()
                if status["expired"]:
                    await self.cleanup_expired()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            await asyncio.sleep(self._check_interval)

    def stop(self):
        """Stop the monitoring loop."""
        self._running = False

    @property
    def active_count(self) -> int:
        return len(self._habitats)

    def get_habitat(self, release_name: str) -> HabitatRecord | None:
        return self._habitats.get(release_name)
