import logging
from typing import Dict, Any, List
import copy

logger = logging.getLogger(__name__)


class PolicyManager:
    """
    Manages overarching system behavior constraints.
    Supports versioning and automatic rollbacks if recent operations yield consecutive negative rewards.
    """

    def __init__(self, initial_policy: Dict[str, Any]):
        self.history: List[Dict[str, Any]] = []
        self.current_version = 0
        self.consecutive_failures = 0
        self.rollback_threshold = 3

        self._commit_policy(initial_policy)

    def _commit_policy(self, policy: Dict[str, Any]):
        """Saves the current state inside the history stack."""
        self.current_version += 1
        record = {"version": self.current_version, "policy": copy.deepcopy(policy)}
        self.history.append(record)
        self.current_policy = record["policy"]
        logger.info(f"Policy Engine committed Version {self.current_version}")

    def update_policy(self, new_rules: Dict[str, Any]):
        """Merges new rules and cuts a new version."""
        merged = copy.deepcopy(self.current_policy)
        merged.update(new_rules)
        self._commit_policy(merged)
        # Reset stability counter on new version
        self.consecutive_failures = 0

    def evaluate_system_stability(self, systemic_reward_signal: float) -> bool:
        """
        Monitors the macro-level Reward Signals across the OS.
        If consecutive negative signals hit the threshold, rolls back the policy.
        Returns True if a rollback occurred.
        """
        if systemic_reward_signal < 0:
            self.consecutive_failures += 1
            logger.warning(
                f"Policy Engine logged negative stability signal: {self.consecutive_failures}/{self.rollback_threshold}"
            )
        else:
            # A success resets the panic counter
            self.consecutive_failures = 0

        if self.consecutive_failures >= self.rollback_threshold:
            return self.trigger_rollback()

        return False

    def trigger_rollback(self) -> bool:
        """Reverts the active policy to the previous stable version."""
        if len(self.history) <= 1:
            logger.critical(
                "Policy Rollback triggered, but no previous states exist. Staying on v1."
            )
            self.consecutive_failures = 0  # reset to prevent endless loop
            return False

        current = self.history.pop()  # Remove the failing version
        previous = self.history[-1]  # Grab the new current

        self.current_policy = copy.deepcopy(previous["policy"])
        self.current_version = previous["version"]
        self.consecutive_failures = 0

        logger.warning(
            f"POLICY ROLLBACK EXECUTED. Reverted {current['version']} -> {self.current_version}"
        )
        return True
