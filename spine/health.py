import logging
from typing import Dict, Any, Callable, Awaitable
from src.raphael.core.schemas import SystemEvent

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Subscribes to Layer 1 Telemetry and evaluates system drift or overheating.
    If arbitrary thresholds are exceeded, it triggers callbacks to emit SYSTEM_ALERTs.
    """

    CRITICAL_CPU_THRESHOLD = 95.0
    CRITICAL_RAM_THRESHOLD = 95.0

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def process_telemetry(self, payload: Dict[str, Any]) -> str:
        """
        Updates the resource manager mapped state.
        Returns an alert string if thresholds are violated, else empty string.
        """
        cpu = payload.get("cpu_percent", 0.0)
        ram = payload.get("memory_percent", 0.0)

        self.resource_manager.update_telemetry(cpu, ram)

        alerts = []
        if cpu >= self.CRITICAL_CPU_THRESHOLD:
            alerts.append(f"CPU critical: {cpu}%")
        if ram >= self.CRITICAL_RAM_THRESHOLD:
            alerts.append(f"RAM critical: {ram}%")

        if alerts:
            alert_msg = " | ".join(alerts)
            logger.error(f"Health Monitor triggered: {alert_msg}")
            return alert_msg

        return ""
