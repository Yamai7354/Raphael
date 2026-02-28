"""
SOS-504 — Metrics & Telemetry Hub.

Centralizes all swarm metrics: agent performance, memory growth,
task completion rates, cognition/discovery outputs, and health.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.telemetry")


@dataclass
class MetricSnapshot:
    """A point-in-time metric recording."""

    name: str = ""
    value: float = 0.0
    tags: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class TelemetryHub:
    """Collects and aggregates swarm-wide telemetry."""

    def __init__(self, history_limit: int = 500):
        self.history_limit = history_limit
        self._metrics: dict[str, list[MetricSnapshot]] = {}
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}

    def record(self, name: str, value: float, tags: dict | None = None) -> None:
        snap = MetricSnapshot(name=name, value=value, tags=tags or {})
        history = self._metrics.setdefault(name, [])
        history.append(snap)
        if len(history) > self.history_limit:
            self._metrics[name] = history[-self.history_limit :]
        self._gauges[name] = value

    def increment(self, name: str, delta: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + delta

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def get_latest(self, name: str) -> float | None:
        return self._gauges.get(name)

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_trend(self, name: str, limit: int = 20) -> list[dict]:
        snapshots = self._metrics.get(name, [])[-limit:]
        return [{"value": s.value, "timestamp": s.timestamp} for s in snapshots]

    def get_average(self, name: str, window: int = 10) -> float | None:
        snapshots = self._metrics.get(name, [])[-window:]
        if not snapshots:
            return None
        return sum(s.value for s in snapshots) / len(snapshots)

    def get_all_gauges(self) -> dict[str, float]:
        return dict(self._gauges)

    def get_all_counters(self) -> dict[str, int]:
        return dict(self._counters)

    def get_summary(self) -> dict:
        """Aggregated metrics summary for analytics."""
        return {
            "gauges": dict(self._gauges),
            "counters": dict(self._counters),
            "tracked_metrics": len(self._metrics),
            "total_snapshots": sum(len(v) for v in self._metrics.values()),
        }

    def get_stats(self) -> dict:
        return {
            "metrics_tracked": len(self._metrics),
            "counters": len(self._counters),
            "gauges": len(self._gauges),
        }
