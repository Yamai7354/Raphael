"""
DISC-312 — Discovery Safety Controls.

Prevents runaway system modifications with prototype limits,
resource caps, integration review checkpoints, and rate throttling.
"""

import logging
import time

logger = logging.getLogger("core.discovery.safety_controls")


class DiscoverySafetyControls:
    """Safeguards against runaway discovery modifications."""

    def __init__(
        self,
        max_concurrent_prototypes: int = 5,
        max_integrations_per_hour: int = 3,
        max_cycles_per_hour: int = 6,
        cooldown_after_failure_seconds: float = 120,
    ):
        self.max_concurrent_prototypes = max_concurrent_prototypes
        self.max_integrations_per_hour = max_integrations_per_hour
        self.max_cycles_per_hour = max_cycles_per_hour
        self.cooldown_after_failure_seconds = cooldown_after_failure_seconds

        self._active_prototypes: int = 0
        self._integration_timestamps: list[float] = []
        self._cycle_timestamps: list[float] = []
        self._last_failure: float = 0
        self._violations: list[dict] = []

    def can_start_cycle(self) -> bool:
        """Check if a new discovery cycle is allowed."""
        now = time.time()

        # Cooldown after failure
        if now - self._last_failure < self.cooldown_after_failure_seconds:
            self._record_violation("cycle_cooldown", "In cooldown after failure")
            return False

        # Rate limit cycles
        cutoff = now - 3600
        recent = [t for t in self._cycle_timestamps if t > cutoff]
        if len(recent) >= self.max_cycles_per_hour:
            self._record_violation("cycle_rate_limit", f"Hit {self.max_cycles_per_hour}/hr limit")
            return False

        self._cycle_timestamps.append(now)
        self._cycle_timestamps = [t for t in self._cycle_timestamps if t > cutoff]
        return True

    def can_create_prototype(self) -> bool:
        """Check if a new prototype can be created."""
        if self._active_prototypes >= self.max_concurrent_prototypes:
            self._record_violation(
                "prototype_limit", f"At max {self.max_concurrent_prototypes} prototypes"
            )
            return False
        return True

    def can_integrate(self) -> bool:
        """Check if an integration is allowed."""
        now = time.time()
        cutoff = now - 3600
        recent = [t for t in self._integration_timestamps if t > cutoff]
        if len(recent) >= self.max_integrations_per_hour:
            self._record_violation(
                "integration_rate_limit", f"Hit {self.max_integrations_per_hour}/hr limit"
            )
            return False
        return True

    def record_prototype_start(self) -> None:
        self._active_prototypes += 1

    def record_prototype_end(self) -> None:
        self._active_prototypes = max(0, self._active_prototypes - 1)

    def record_integration(self) -> None:
        self._integration_timestamps.append(time.time())

    def record_failure(self) -> None:
        self._last_failure = time.time()
        logger.warning(
            "safety_failure_recorded cooldown=%.0fs", self.cooldown_after_failure_seconds
        )

    def _record_violation(self, violation_type: str, message: str) -> None:
        self._violations.append(
            {
                "type": violation_type,
                "message": message,
                "timestamp": time.time(),
            }
        )
        logger.warning("safety_violation type=%s: %s", violation_type, message)

    def get_violations(self, limit: int = 20) -> list[dict]:
        return self._violations[-limit:]

    def get_status(self) -> dict:
        return {
            "active_prototypes": self._active_prototypes,
            "max_prototypes": self.max_concurrent_prototypes,
            "integrations_this_hour": len(
                [t for t in self._integration_timestamps if t > time.time() - 3600]
            ),
            "max_integrations_per_hour": self.max_integrations_per_hour,
            "in_cooldown": time.time() - self._last_failure < self.cooldown_after_failure_seconds,
            "total_violations": len(self._violations),
        }
