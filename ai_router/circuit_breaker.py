"""
Circuit Breaker for AI Router.

Prevents routing to nodes experiencing repeated failures.
Provides automatic recovery via health checks.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger("ai_router.circuit_breaker")


# =============================================================================
# CIRCUIT STATE
# =============================================================================


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for a single node.

    State transitions:
    - CLOSED: Normal operation, counting failures
    - OPEN: After N failures, block requests for cooldown period
    - HALF_OPEN: After cooldown, allow one test request
    """

    node_id: str
    failure_threshold: int = 3  # Failures before opening
    cooldown_sec: float = 60.0  # How long to stay open
    half_open_max_calls: int = 1  # Test calls in half-open

    # State
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    half_open_calls: int = 0

    def is_available(self) -> bool:
        """Check if node can receive requests."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if cooldown expired
            if self._cooldown_expired():
                self._transition_to_half_open()
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited test calls
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Record a successful call."""
        self.success_count += 1

        if self.state == CircuitState.HALF_OPEN:
            # Success in half-open = recovery complete
            self._transition_to_closed()
            logger.info("circuit_recovered node=%s", self.node_id)
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open = reopen circuit
            self._transition_to_open()
            logger.warning(
                "circuit_reopened node=%s failure_count=%d",
                self.node_id,
                self.failure_count,
            )
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()
                logger.warning(
                    "circuit_opened node=%s failures=%d threshold=%d",
                    self.node_id,
                    self.failure_count,
                    self.failure_threshold,
                )

    def _transition_to_open(self) -> None:
        """Open the circuit."""
        self.state = CircuitState.OPEN
        self.opened_at = datetime.now()
        self.half_open_calls = 0
        logger.info(
            "circuit_state_change node=%s state=OPEN cooldown_sec=%.1f",
            self.node_id,
            self.cooldown_sec,
        )

    def _transition_to_half_open(self) -> None:
        """Transition to half-open for testing."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        logger.info("circuit_state_change node=%s state=HALF_OPEN", self.node_id)

    def _transition_to_closed(self) -> None:
        """Close the circuit (recovery complete)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None
        self.half_open_calls = 0
        logger.info("circuit_state_change node=%s state=CLOSED", self.node_id)

    def _cooldown_expired(self) -> bool:
        """Check if cooldown period has expired."""
        if not self.opened_at:
            return True
        elapsed = (datetime.now() - self.opened_at).total_seconds()
        return elapsed >= self.cooldown_sec

    def time_until_recovery(self) -> Optional[float]:
        """Get seconds until circuit might recover (None if closed)."""
        if self.state != CircuitState.OPEN or not self.opened_at:
            return None
        elapsed = (datetime.now() - self.opened_at).total_seconds()
        remaining = self.cooldown_sec - elapsed
        return max(0, remaining)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "cooldown_sec": self.cooldown_sec,
            "time_until_recovery": self.time_until_recovery(),
            "last_failure": self.last_failure.isoformat()
            if self.last_failure
            else None,
        }


# =============================================================================
# CIRCUIT BREAKER REGISTRY
# =============================================================================


class CircuitBreakerRegistry:
    """Registry of circuit breakers for all nodes."""

    def __init__(
        self,
        default_failure_threshold: int = 3,
        default_cooldown_sec: float = 60.0,
    ):
        self.default_failure_threshold = default_failure_threshold
        self.default_cooldown_sec = default_cooldown_sec
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_breaker(self, node_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for a node."""
        if node_id not in self._breakers:
            self._breakers[node_id] = CircuitBreaker(
                node_id=node_id,
                failure_threshold=self.default_failure_threshold,
                cooldown_sec=self.default_cooldown_sec,
            )
        return self._breakers[node_id]

    def is_available(self, node_id: str) -> bool:
        """Check if node is available (circuit not open)."""
        breaker = self.get_breaker(node_id)
        return breaker.is_available()

    def record_success(self, node_id: str) -> None:
        """Record successful call to node."""
        breaker = self.get_breaker(node_id)
        breaker.record_success()

    def record_failure(self, node_id: str) -> None:
        """Record failed call to node."""
        breaker = self.get_breaker(node_id)
        breaker.record_failure()

    def get_available_nodes(self, node_ids: list[str]) -> list[str]:
        """Filter to only available nodes."""
        return [n for n in node_ids if self.is_available(n)]

    def get_all_states(self) -> Dict[str, Dict]:
        """Get state of all circuit breakers."""
        return {
            node_id: breaker.to_dict() for node_id, breaker in self._breakers.items()
        }

    def force_open(self, node_id: str) -> None:
        """Manually open circuit (for testing/admin)."""
        breaker = self.get_breaker(node_id)
        breaker._transition_to_open()

    def force_close(self, node_id: str) -> None:
        """Manually close circuit (for testing/admin)."""
        breaker = self.get_breaker(node_id)
        breaker._transition_to_closed()


# Global singleton
circuit_breaker_registry = CircuitBreakerRegistry()
