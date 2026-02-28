"""
SOS-503 — Resource Coordination Layer.

Coordinates hardware, memory, and computational resources.
Prevents overload, optimizes throughput and latency.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.resource_coordinator")


@dataclass
class ResourceAllocation:
    """An active resource allocation."""

    alloc_id: str = ""
    task_id: str = ""
    hostname: str = ""
    cpu_reserved: float = 0  # cores
    memory_reserved_gb: float = 0
    gpu_reserved: bool = False
    allocated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "task": self.task_id,
            "host": self.hostname,
            "cpu": self.cpu_reserved,
            "mem_gb": self.memory_reserved_gb,
            "gpu": self.gpu_reserved,
        }


class ResourceCoordinator:
    """Coordinates resource allocation across the swarm."""

    def __init__(
        self,
        max_cpu_per_host: float = 90,
        max_memory_pct: float = 85,
        max_gpu_tasks_per_host: int = 3,
    ):
        self.max_cpu = max_cpu_per_host
        self.max_memory_pct = max_memory_pct
        self.max_gpu_tasks = max_gpu_tasks_per_host
        self._allocations: dict[str, ResourceAllocation] = {}
        self._host_usage: dict[str, dict] = {}  # hostname -> {cpu, memory, gpu_tasks}
        self._denied: list[dict] = []

    def request(
        self,
        task_id: str,
        hostname: str,
        cpu_cores: float = 1,
        memory_gb: float = 1,
        needs_gpu: bool = False,
    ) -> ResourceAllocation | None:
        """Request resource allocation. Returns None if denied."""
        usage = self._host_usage.get(hostname, {"cpu": 0, "memory": 0, "gpu_tasks": 0})

        if usage["cpu"] + cpu_cores > self.max_cpu:
            self._deny(
                task_id, hostname, f"CPU limit ({usage['cpu'] + cpu_cores:.0f} > {self.max_cpu})"
            )
            return None
        if needs_gpu and usage["gpu_tasks"] >= self.max_gpu_tasks:
            self._deny(
                task_id, hostname, f"GPU limit ({usage['gpu_tasks']} >= {self.max_gpu_tasks})"
            )
            return None

        alloc_id = f"alloc_{task_id}"
        alloc = ResourceAllocation(
            alloc_id=alloc_id,
            task_id=task_id,
            hostname=hostname,
            cpu_reserved=cpu_cores,
            memory_reserved_gb=memory_gb,
            gpu_reserved=needs_gpu,
        )
        self._allocations[alloc_id] = alloc

        usage["cpu"] = usage.get("cpu", 0) + cpu_cores
        usage["memory"] = usage.get("memory", 0) + memory_gb
        if needs_gpu:
            usage["gpu_tasks"] = usage.get("gpu_tasks", 0) + 1
        self._host_usage[hostname] = usage

        logger.info(
            "resource_allocated task=%s host=%s cpu=%.1f mem=%.1fGB gpu=%s",
            task_id,
            hostname,
            cpu_cores,
            memory_gb,
            needs_gpu,
        )
        return alloc

    def release(self, task_id: str) -> None:
        alloc_id = f"alloc_{task_id}"
        alloc = self._allocations.pop(alloc_id, None)
        if not alloc:
            return
        usage = self._host_usage.get(alloc.hostname, {})
        usage["cpu"] = max(0, usage.get("cpu", 0) - alloc.cpu_reserved)
        usage["memory"] = max(0, usage.get("memory", 0) - alloc.memory_reserved_gb)
        if alloc.gpu_reserved:
            usage["gpu_tasks"] = max(0, usage.get("gpu_tasks", 0) - 1)

    def get_host_usage(self, hostname: str) -> dict:
        return self._host_usage.get(hostname, {"cpu": 0, "memory": 0, "gpu_tasks": 0})

    def get_least_utilized_host(self, hosts: list[str]) -> str | None:
        if not hosts:
            return None
        return min(hosts, key=lambda h: self._host_usage.get(h, {}).get("cpu", 0))

    def _deny(self, task_id: str, hostname: str, reason: str) -> None:
        self._denied.append(
            {"task": task_id, "host": hostname, "reason": reason, "at": time.time()}
        )
        logger.warning("resource_denied task=%s host=%s reason=%s", task_id, hostname, reason)

    def get_active_allocations(self) -> list[dict]:
        return [a.to_dict() for a in self._allocations.values()]

    def get_stats(self) -> dict:
        return {
            "active_allocations": len(self._allocations),
            "hosts_in_use": len(self._host_usage),
            "denied_requests": len(self._denied),
        }
