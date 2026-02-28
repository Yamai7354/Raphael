"""
WORLD-405 — Resource Awareness Engine.

Tracks GPU load, CPU usage, memory availability, network latency,
and queue length. Agents can request optimal execution environment.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.world_model.resource_awareness")


@dataclass
class ResourceSnapshot:
    """Point-in-time resource usage for a machine."""

    hostname: str = ""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    gpu_load_percent: list[float] = field(default_factory=list)
    gpu_memory_used_gb: list[float] = field(default_factory=list)
    disk_used_percent: float = 0.0
    network_latency_ms: float = 0.0
    queue_length: int = 0

    @property
    def memory_available_gb(self) -> float:
        return max(0, self.memory_total_gb - self.memory_used_gb)

    @property
    def avg_gpu_load(self) -> float:
        return (
            sum(self.gpu_load_percent) / max(1, len(self.gpu_load_percent))
            if self.gpu_load_percent
            else 0.0
        )

    @property
    def load_score(self) -> float:
        """0-1 composite load score (higher = more loaded)."""
        cpu = self.cpu_percent / 100
        mem = self.memory_used_gb / max(1, self.memory_total_gb)
        gpu = self.avg_gpu_load / 100
        return round(cpu * 0.3 + mem * 0.3 + gpu * 0.3 + min(1, self.queue_length / 10) * 0.1, 3)

    def to_dict(self) -> dict:
        return {
            "hostname": self.hostname,
            "cpu_pct": round(self.cpu_percent, 1),
            "memory_avail_gb": round(self.memory_available_gb, 1),
            "gpu_load_avg": round(self.avg_gpu_load, 1),
            "disk_used_pct": round(self.disk_used_percent, 1),
            "net_latency_ms": round(self.network_latency_ms, 1),
            "queue": self.queue_length,
            "load_score": self.load_score,
        }


class ResourceAwareness:
    """Tracks real-time resource availability across all machines."""

    def __init__(self, history_limit: int = 50):
        self.history_limit = history_limit
        self._current: dict[str, ResourceSnapshot] = {}
        self._history: dict[str, list[ResourceSnapshot]] = {}

    def update(self, snapshot: ResourceSnapshot) -> None:
        self._current[snapshot.hostname] = snapshot
        history = self._history.setdefault(snapshot.hostname, [])
        history.append(snapshot)
        if len(history) > self.history_limit:
            self._history[snapshot.hostname] = history[-self.history_limit :]

    def get_current(self, hostname: str) -> ResourceSnapshot | None:
        return self._current.get(hostname)

    def get_least_loaded(self, require_gpu: bool = False) -> str | None:
        """Find the machine with the lowest load score."""
        candidates = list(self._current.values())
        if require_gpu:
            candidates = [s for s in candidates if s.gpu_load_percent]
        if not candidates:
            return None
        best = min(candidates, key=lambda s: s.load_score)
        return best.hostname

    def get_optimal_for_task(
        self, required_memory_gb: float = 0, require_gpu: bool = False
    ) -> str | None:
        """Find the best machine for a task with given requirements."""
        candidates = [
            s for s in self._current.values() if s.memory_available_gb >= required_memory_gb
        ]
        if require_gpu:
            candidates = [s for s in candidates if s.gpu_load_percent and s.avg_gpu_load < 80]
        if not candidates:
            return None
        best = min(candidates, key=lambda s: s.load_score)
        return best.hostname

    def get_overloaded(self, threshold: float = 0.8) -> list[str]:
        return [h for h, s in self._current.items() if s.load_score > threshold]

    def get_all_current(self) -> list[dict]:
        return [s.to_dict() for s in self._current.values()]

    def get_history(self, hostname: str, limit: int = 20) -> list[dict]:
        snapshots = self._history.get(hostname, [])[-limit:]
        return [s.to_dict() for s in snapshots]

    def get_stats(self) -> dict:
        if not self._current:
            return {"machines_tracked": 0}
        loads = [s.load_score for s in self._current.values()]
        return {
            "machines_tracked": len(self._current),
            "avg_load": round(sum(loads) / len(loads), 3),
            "max_load": round(max(loads), 3),
            "overloaded": len(self.get_overloaded()),
        }
