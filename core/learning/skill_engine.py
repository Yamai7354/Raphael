import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SkillManager:
    """
    Tracks and persists the competency level of Agent/Capability pairs
    based on the continuous feed of Reward Signals.
    """

    def __init__(self):
        # In a real build, this mounts to a persistent Database.
        # Format: {"agent_id": {"capability": proficiency_score}}
        # 1.0 is baseline.
        self._competency_matrix: Dict[str, Dict[str, float]] = {}

    def get_proficiency(self, agent_id: str, capability: str) -> float:
        """Looks up the current tracked skill level."""
        return self._competency_matrix.get(agent_id, {}).get(capability, 1.0)

    def process_reward_signal(self, signal: Dict[str, Any]) -> float:
        """
        Ingests a RewardSignal (+/- score) and adjusts the Agent's baseline skill modifier.
        Returns the new proficiency score.
        """
        agent = signal.get("agent_id")
        cap = signal.get("task_capability")
        score = signal.get("score", 0.0)

        if agent == "unknown" or cap == "unknown":
            logger.warning("SkillManager dropped anonymous reward signal.")
            return 1.0

        # Initialize if virgin
        if agent not in self._competency_matrix:
            self._competency_matrix[agent] = {}
        if cap not in self._competency_matrix[agent]:
            self._competency_matrix[agent][cap] = 1.0

        # Adjust the proficiency.
        # A positive +10 reward bumps proficiency by a fraction (e.g. +0.01)
        # Cap proficiency between 0.1 and 5.0
        adjustment = score * 0.001
        current = self._competency_matrix[agent][cap]
        new_prof = max(0.1, min(5.0, current + adjustment))

        self._competency_matrix[agent][cap] = new_prof
        logger.info(f"Skill updated for {agent} on '{cap}': {current:.3f} -> {new_prof:.3f}")

        return new_prof
