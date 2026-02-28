import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class InfrastructureManager:
    """
    Monitors global resource utilization to automate or recommend
    evolutionary infrastructure upgrades (e.g. scaling memory limits or core counts).
    """

    def __init__(self):
        self.baseline_memory = 16000  # 16 GB baseline
        self.sustained_high_usage_threshold = 0.85  # 85% utilization

    def evaluate_evolution_needs(self, historical_utilization: List[float]) -> Dict[str, Any]:
        """
        Ingeats a timeline of resource utilization percentages [0.0 - 1.0].
        If usage is consistently high, recommend an infrastructure scale-up.
        """
        if not historical_utilization:
            return {"action": "none", "reason": "No data"}

        # Check if the last N ticks have been above the threshold
        window_size = 5
        if len(historical_utilization) >= window_size:
            recent_window = historical_utilization[-window_size:]

            # If all recent checks are above 85%
            if all(usage >= self.sustained_high_usage_threshold for usage in recent_window):
                logger.warning(
                    "InfrastructureManager detected sustained high utilization. Recommending evolution."
                )
                return {
                    "action": "recommend_upgrade",
                    "resource": "memory",
                    "current_baseline_mb": self.baseline_memory,
                    "recommended_baseline_mb": int(self.baseline_memory * 1.5),
                    "reason": f"Sustained utilization >= {self.sustained_high_usage_threshold * 100}%",
                }

        logger.debug("Infrastructure utilization is nominal.")
        return {"action": "none", "reason": "Utilization within acceptable parameters"}
