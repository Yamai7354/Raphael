"""
WORLD-402 — Machine & Hardware Registry Expansion.

Detailed capabilities of each machine: CPU, GPU, RAM,
storage, network speed, OS, and active workloads.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.world_model.hardware_registry")


@dataclass
class MachineRecord:
    """A machine in the swarm infrastructure."""

    machine_id: str = field(default_factory=lambda: f"machine_{uuid.uuid4().hex[:8]}")
    hostname: str = ""
    os: str = ""
    cpu_model: str = ""
    cpu_cores: int = 0
    gpu_models: list[str] = field(default_factory=list)
    gpu_vram_gb: list[float] = field(default_factory=list)
    ram_gb: float = 0.0
    storage_type: str = "ssd"  # ssd, hdd, nvme
    storage_gb: float = 0.0
    network_speed_mbps: float = 0.0
    ip_address: str = ""
    active_workloads: list[str] = field(default_factory=list)
    status: str = "online"  # online, offline, degraded
    registered_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def gpu_count(self) -> int:
        return len(self.gpu_models)

    @property
    def total_vram_gb(self) -> float:
        return sum(self.gpu_vram_gb)

    def to_dict(self) -> dict:
        return {
            "machine_id": self.machine_id,
            "hostname": self.hostname,
            "os": self.os,
            "cpu": f"{self.cpu_model} ({self.cpu_cores} cores)",
            "gpus": self.gpu_count,
            "total_vram_gb": self.total_vram_gb,
            "ram_gb": self.ram_gb,
            "storage": f"{self.storage_gb}GB {self.storage_type}",
            "network_mbps": self.network_speed_mbps,
            "workloads": len(self.active_workloads),
            "status": self.status,
        }


class HardwareRegistry:
    """Registry of all machines in the swarm infrastructure."""

    def __init__(self):
        self._machines: dict[str, MachineRecord] = {}
        self._by_hostname: dict[str, str] = {}

    def register(self, hostname: str, **kwargs) -> MachineRecord:
        if hostname in self._by_hostname:
            m = self._machines[self._by_hostname[hostname]]
            for k, v in kwargs.items():
                if hasattr(m, k):
                    setattr(m, k, v)
            m.updated_at = time.time()
            return m

        m = MachineRecord(hostname=hostname, **kwargs)
        self._machines[m.machine_id] = m
        self._by_hostname[hostname] = m.machine_id
        logger.info(
            "machine_registered hostname=%s gpus=%d ram=%.0fGB", hostname, m.gpu_count, m.ram_gb
        )
        return m

    def update_status(self, hostname: str, status: str) -> None:
        mid = self._by_hostname.get(hostname)
        if mid and mid in self._machines:
            self._machines[mid].status = status
            self._machines[mid].updated_at = time.time()

    def add_workload(self, hostname: str, workload: str) -> None:
        mid = self._by_hostname.get(hostname)
        if mid and mid in self._machines:
            self._machines[mid].active_workloads.append(workload)

    def remove_workload(self, hostname: str, workload: str) -> None:
        mid = self._by_hostname.get(hostname)
        if mid and mid in self._machines:
            wl = self._machines[mid].active_workloads
            if workload in wl:
                wl.remove(workload)

    def get_by_hostname(self, hostname: str) -> MachineRecord | None:
        mid = self._by_hostname.get(hostname)
        return self._machines.get(mid) if mid else None

    def get_with_gpu(self) -> list[MachineRecord]:
        return [m for m in self._machines.values() if m.gpu_count > 0 and m.status == "online"]

    def get_available(self, min_ram_gb: float = 0, min_vram_gb: float = 0) -> list[MachineRecord]:
        return [
            m
            for m in self._machines.values()
            if m.status == "online" and m.ram_gb >= min_ram_gb and m.total_vram_gb >= min_vram_gb
        ]

    def get_all(self) -> list[dict]:
        return [m.to_dict() for m in self._machines.values()]

    def get_stats(self) -> dict:
        online = [m for m in self._machines.values() if m.status == "online"]
        return {
            "total_machines": len(self._machines),
            "online": len(online),
            "total_gpus": sum(m.gpu_count for m in online),
            "total_vram_gb": round(sum(m.total_vram_gb for m in online), 1),
            "total_ram_gb": round(sum(m.ram_gb for m in online), 1),
        }
