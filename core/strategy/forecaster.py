import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class CapabilityForecaster:
    """
    Predicts upcoming systemic bottlenecks based on historical telemetry.
    """

    def __init__(self):
        # Hard limits
        self.max_memory_mb = 16000  # 16 GB Apple M4
        self.max_concurrent_tasks = 100

    def forecast_bottlenecks(self, recent_telemetry: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes a time-series of metrics and extrapolates future breaking points.
        """
        if not recent_telemetry:
            return {"status": "stable", "warnings": []}

        warnings = []

        # Check memory trajectory
        # Mocks a linear progression check
        mem_usage = [tick.get("memory_mb", 0) for tick in recent_telemetry]
        if len(mem_usage) >= 2:
            current_mem = mem_usage[-1]
            delta = current_mem - mem_usage[-2]

            if delta > 0:
                # If it keeps growing at this rate, when do we hit the ceiling?
                ticks_remaining = (self.max_memory_mb - current_mem) / delta
                if ticks_remaining < 5:  # Critical warning threshold
                    warnings.append(
                        f"CRITICAL: Memory exhaustion projected in {ticks_remaining:.1f} ticks."
                    )

        # Check concurrency limits
        task_counts = [tick.get("active_tasks", 0) for tick in recent_telemetry]
        if task_counts and task_counts[-1] >= (self.max_concurrent_tasks * 0.9):
            warnings.append("WARNING: Running at 90% task capacity.")

        status = "critical" if warnings else "stable"
        logger.info(f"Forecaster evaluated {len(recent_telemetry)} ticks. Status: {status}")

        return {"status": status, "warnings": warnings}
