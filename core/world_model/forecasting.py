"""
WORLD-411 — Resource Forecasting System.

Predicts future resource usage to prevent overload:
workload spikes, memory growth, GPU demand, agent activity trends.
"""

import logging
import time
from dataclasses import dataclass, field

from .resource_awareness import ResourceAwareness

logger = logging.getLogger("core.world_model.forecasting")


@dataclass
class Forecast:
    """A resource usage prediction."""

    hostname: str = ""
    metric: str = ""  # cpu, memory, gpu, queue
    current_value: float = 0.0
    predicted_value: float = 0.0
    predicted_at_hours: float = 1.0  # how far ahead
    confidence: float = 0.5
    alert: bool = False
    alert_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "hostname": self.hostname,
            "metric": self.metric,
            "current": round(self.current_value, 2),
            "predicted": round(self.predicted_value, 2),
            "hours_ahead": self.predicted_at_hours,
            "confidence": round(self.confidence, 3),
            "alert": self.alert,
            "alert_reason": self.alert_reason,
        }


class ResourceForecaster:
    """Predicts future resource utilization using simple trend analysis."""

    def __init__(
        self,
        resources: ResourceAwareness | None = None,
        cpu_threshold: float = 90,
        memory_threshold_pct: float = 90,
        gpu_threshold: float = 95,
    ):
        self.resources = resources or ResourceAwareness()
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold_pct
        self.gpu_threshold = gpu_threshold
        self._forecasts: list[Forecast] = []

    def _linear_trend(self, values: list[float]) -> float:
        """Simple linear regression slope."""
        n = len(values)
        if n < 3:
            return 0.0
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den != 0 else 0.0

    def forecast_host(self, hostname: str, hours_ahead: float = 1.0) -> list[Forecast]:
        """Forecast resource usage for a specific host."""
        history = self.resources.get_history(hostname, limit=20)
        if len(history) < 3:
            return []

        forecasts: list[Forecast] = []

        # CPU forecast
        cpu_vals = [h["cpu_pct"] for h in history]
        cpu_slope = self._linear_trend(cpu_vals)
        # Estimate steps ahead (each snapshot ~60s apart)
        steps = hours_ahead * 60
        cpu_pred = cpu_vals[-1] + cpu_slope * steps
        cpu_pred = max(0, min(100, cpu_pred))
        cpu_fc = Forecast(
            hostname=hostname,
            metric="cpu",
            current_value=cpu_vals[-1],
            predicted_value=cpu_pred,
            predicted_at_hours=hours_ahead,
            confidence=0.6 if len(history) >= 10 else 0.4,
        )
        if cpu_pred > self.cpu_threshold:
            cpu_fc.alert = True
            cpu_fc.alert_reason = f"CPU predicted to hit {cpu_pred:.0f}% in {hours_ahead}h"
        forecasts.append(cpu_fc)

        # Memory forecast
        mem_vals = [h.get("memory_avail_gb", 0) for h in history]
        mem_slope = self._linear_trend(mem_vals)
        mem_pred = max(0, mem_vals[-1] + mem_slope * steps)
        mem_fc = Forecast(
            hostname=hostname,
            metric="memory_available_gb",
            current_value=mem_vals[-1],
            predicted_value=mem_pred,
            predicted_at_hours=hours_ahead,
            confidence=0.5,
        )
        if mem_pred < 1.0:  # Less than 1GB available
            mem_fc.alert = True
            mem_fc.alert_reason = f"Memory predicted to drop to {mem_pred:.1f}GB in {hours_ahead}h"
        forecasts.append(mem_fc)

        # GPU forecast
        gpu_vals = [h.get("gpu_load_avg", 0) for h in history]
        if any(v > 0 for v in gpu_vals):
            gpu_slope = self._linear_trend(gpu_vals)
            gpu_pred = max(0, min(100, gpu_vals[-1] + gpu_slope * steps))
            gpu_fc = Forecast(
                hostname=hostname,
                metric="gpu_load",
                current_value=gpu_vals[-1],
                predicted_value=gpu_pred,
                predicted_at_hours=hours_ahead,
                confidence=0.5,
            )
            if gpu_pred > self.gpu_threshold:
                gpu_fc.alert = True
                gpu_fc.alert_reason = f"GPU predicted to hit {gpu_pred:.0f}% in {hours_ahead}h"
            forecasts.append(gpu_fc)

        self._forecasts.extend(forecasts)
        return forecasts

    def forecast_all(self, hours_ahead: float = 1.0) -> list[Forecast]:
        """Forecast for all tracked machines."""
        all_fcs: list[Forecast] = []
        for snap in self.resources.get_all_current():
            fcs = self.forecast_host(snap["hostname"], hours_ahead)
            all_fcs.extend(fcs)
        return all_fcs

    def get_alerts(self) -> list[dict]:
        return [f.to_dict() for f in self._forecasts if f.alert]

    def get_stats(self) -> dict:
        alerts = [f for f in self._forecasts if f.alert]
        return {
            "total_forecasts": len(self._forecasts),
            "active_alerts": len(alerts),
        }
