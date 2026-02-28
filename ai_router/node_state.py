"""
Node State Model for AI Router.

Defines the possible states for cluster nodes and provides
utilities for tracking and logging state transitions.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Any

# Configure structured logging for state transitions
logger = logging.getLogger("ai_router.node_state")

# Default cooldown duration in seconds
DEFAULT_COOLDOWN_SECONDS = 30


class NodeState(str, Enum):
    """
    Enumeration of possible node states.
    States are mutually exclusive.
    """

    OFFLINE = "OFFLINE"  # Unreachable
    ONLINE = "ONLINE"  # Reachable, unknown readiness
    WARMING = "WARMING"  # Reachable but model not ready
    READY = "READY"  # Safe to route inference
    DEGRADED = "DEGRADED"  # Reachable but error-prone
    BUSY = "BUSY"  # At capacity


class NodeStateInfo:
    """
    Holds the current state of a node along with metadata.
    """

    def __init__(
        self,
        node_id: str,
        initial_state: NodeState = NodeState.OFFLINE,
        attributes: Optional[Dict[str, Any]] = None,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ):
        self.node_id = node_id
        self._state = initial_state
        self.attributes = attributes or {}
        self.last_transition_time: datetime = datetime.now()
        self.last_transition_reason: str = "initial_state"
        self.latency_ms: Optional[float] = None
        self.error_count: int = 0
        self.success_count: int = 0
        self.total_requests: int = 0
        self.last_success_time: Optional[datetime] = None

        # Cooldown management
        self.cooldown_seconds = cooldown_seconds
        self.cooldown_until: Optional[datetime] = None
        self.recovery_confirmations: int = 0
        self.required_recovery_confirmations: int = 2

        # Log the initial state
        logger.info(
            "node_id=%s state=%s reason=%s attributes=%s",
            self.node_id,
            self._state.value,
            self.last_transition_reason,
            self.attributes,
        )

    @property
    def state(self) -> NodeState:
        return self._state

    @property
    def score(self) -> float:
        """Default score using standard 0.7/0.3 weights."""
        return self.calculate_score(success_weight=0.7, latency_weight=0.3)

    def calculate_score(
        self, success_weight: float = 0.7, latency_weight: float = 0.3
    ) -> float:
        """
        Calculate a quality score (0.0 to 1.0) based on historical performance.
        Default weights: Success Rate (70%) + Latency (30%)
        """
        # 1. Success Rate
        if self.total_requests == 0:
            success_rate = 1.0  # Optimistic start
        else:
            success_rate = self.success_count / self.total_requests

        # 2. Latency Score (normalized)
        # Assume < 200ms is perfect (1.0), > 2000ms is poor (0.0)
        latency_score = 1.0
        if self.latency_ms is not None:
            # Linear decay: 1.0 at 200ms, 0.0 at 2000ms
            latency_score = max(0.0, min(1.0, 1.0 - (self.latency_ms - 200) / 1800))

        # Weighted Sum
        # Weights should sum to 1.0 ideally, but we normalize here just in case
        total = success_weight + latency_weight
        if total == 0:
            return success_rate

        return (success_rate * success_weight / total) + (
            latency_score * latency_weight / total
        )

    def is_in_cooldown(self) -> bool:
        """Check if the node is currently in a cooldown period."""
        if self.cooldown_until is None:
            return False
        return datetime.now() < self.cooldown_until

    def get_cooldown_remaining_seconds(self) -> float:
        """Return remaining cooldown time in seconds, or 0 if not in cooldown."""
        if self.cooldown_until is None:
            return 0.0
        remaining = (self.cooldown_until - datetime.now()).total_seconds()
        return max(0.0, remaining)

    def enter_cooldown(self, reason: str) -> None:
        """Put the node into cooldown after a failure."""
        self.cooldown_until = datetime.now() + timedelta(seconds=self.cooldown_seconds)
        self.recovery_confirmations = 0
        logger.info(
            "node_id=%s cooldown_started duration_sec=%d reason=%s",
            self.node_id,
            self.cooldown_seconds,
            reason,
        )

    def confirm_recovery(self) -> bool:
        """
        Record a successful health check during/after cooldown.
        Returns True if the node has met the required confirmations to exit cooldown.
        """
        self.recovery_confirmations += 1
        logger.info(
            "node_id=%s recovery_confirmation=%d/%d",
            self.node_id,
            self.recovery_confirmations,
            self.required_recovery_confirmations,
        )
        if self.recovery_confirmations >= self.required_recovery_confirmations:
            self.cooldown_until = None
            self.recovery_confirmations = 0
            logger.info("node_id=%s cooldown_cleared", self.node_id)
            return True
        return False

    def transition_to(self, new_state: NodeState, reason: str) -> None:
        """
        Transition the node to a new state.
        Logs every transition with structured fields.
        """
        if new_state == self._state:
            # No-op if state is unchanged
            return

        old_state = self._state
        self._state = new_state
        self.last_transition_time = datetime.now()
        self.last_transition_reason = reason

        # Structured log for post-mortem analysis
        logger.info(
            "node_id=%s from=%s to=%s reason=%s",
            self.node_id,
            old_state.value,
            new_state.value,
            reason,
        )

    def to_dict(self) -> dict:
        """
        Return a dictionary representation of the node state info.
        Useful for API responses.
        """
        return {
            "node_id": self.node_id,
            "state": self._state.value,
            "last_transition_time": self.last_transition_time.isoformat(),
            "last_transition_reason": self.last_transition_reason,
            "latency_ms": self.latency_ms,
            "error_count": self.error_count,
            "in_cooldown": self.is_in_cooldown(),
            "cooldown_remaining_sec": round(self.get_cooldown_remaining_seconds(), 1),
            "attributes": self.attributes,
        }


class NodeStateManager:
    """
    Manages state for all nodes in the cluster.
    """

    def __init__(self):
        self._nodes: Dict[str, NodeStateInfo] = {}

    def register_node(self, node_id: str) -> None:
        """Register a new node if not exists."""
        if node_id not in self._nodes:
            self._nodes[node_id] = NodeStateInfo(node_id)

    def get_node_state(self, node_id: str) -> NodeState:
        """Get current state of a node."""
        if node_id not in self._nodes:
            return NodeState.OFFLINE
        return self._nodes[node_id].state

    def transition_node(self, node_id: str, new_state: NodeState, reason: str) -> None:
        """Transition node to new state."""
        if node_id in self._nodes:
            self._nodes[node_id].transition_to(new_state, reason)

    def get_all_states(self) -> Dict[str, str]:
        """Get mapping of node_id -> state value."""
        return {nid: info.state.value for nid, info in self._nodes.items()}

    def get_node_info(self, node_id: str) -> Optional[NodeStateInfo]:
        """Get full state info."""
        return self._nodes.get(node_id)


# Global singleton
node_state_manager = NodeStateManager()
