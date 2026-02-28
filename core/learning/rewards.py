import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RewardGenerator:
    """
    Translates task execution performance (success, errors, duration)
    into numerical reward or penalty signals for the Learning Engine.
    """

    def __init__(self):
        pass

    def compute_signal(self, task_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates a reward or penalty score based on the result metrics.
        Returns a structured RewardSignal.
        """
        score = 0.0
        reasoning = []

        # Base completion calculation
        if task_result.get("success") is True:
            score += 10.0
            reasoning.append("Task concluded successfully (+10.0)")
        else:
            score -= 10.0
            reasoning.append("Task failed or was rejected (-10.0)")

        # Time efficiency bonus/penalty (arbitrary benchmark for this mock)
        duration = task_result.get("duration_ms", 0)
        if duration > 0 and duration < 500:
            score += 2.0
            reasoning.append("Swift execution (<500ms) bonus (+2.0)")
        elif duration > 5000:
            score -= 2.0
            reasoning.append("Sluggish execution (>5000ms) penalty (-2.0)")

        # Logging anomaly penalty
        logs = task_result.get("logs", [])
        error_lines = sum(
            1 for line in logs if "error" in str(line).lower() or "exception" in str(line).lower()
        )
        if error_lines > 0:
            penalty = error_lines * 1.5
            score -= penalty
            reasoning.append(f"Execution threw {error_lines} error logs (-{penalty})")

        signal = {
            "agent_id": task_result.get("agent_id", "unknown"),
            "task_capability": task_result.get("capability_used", "unknown"),
            "score": score,
            "reasoning": reasoning,
        }

        logger.debug(f"Reward Generator emitted signal: {score} for {signal['agent_id']}")
        return signal
