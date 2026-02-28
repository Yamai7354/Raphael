"""
WORLD-406 — Environment State Monitor.

Continuously updates the world model with real-time system state:
machine status, model availability, experiments, agent workload,
and infrastructure health.
"""

import logging
import time
from dataclasses import dataclass, field

from .hardware_registry import HardwareRegistry
from .model_capabilities import ModelCapabilityMap
from .resource_awareness import ResourceAwareness, ResourceSnapshot

logger = logging.getLogger("core.world_model.state_monitor")


@dataclass
class HealthCheck:
    """Result of a health check."""

    component: str
    status: str  # healthy, degraded, down
    details: str = ""
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"component": self.component, "status": self.status, "details": self.details}


class EnvironmentMonitor:
    """Monitors and updates the world model with live system state."""

    def __init__(
        self,
        hardware: HardwareRegistry | None = None,
        models: ModelCapabilityMap | None = None,
        resources: ResourceAwareness | None = None,
        check_interval_seconds: float = 60,
    ):
        self.hardware = hardware or HardwareRegistry()
        self.models = models or ModelCapabilityMap()
        self.resources = resources or ResourceAwareness()
        self.check_interval = check_interval_seconds
        self._last_check: float = 0
        self._health_log: list[HealthCheck] = []
        self._agent_workloads: dict[str, dict] = {}
        self._running_experiments: list[dict] = []

    def should_check(self) -> bool:
        return time.time() - self._last_check >= self.check_interval

    def update_machine_status(self, hostname: str, status: str) -> None:
        self.hardware.update_status(hostname, status)
        self._health_log.append(
            HealthCheck(
                component=f"machine:{hostname}",
                status=status,
            )
        )

    def update_resources(
        self,
        hostname: str,
        cpu: float,
        memory_used: float,
        memory_total: float,
        gpu_loads: list[float] | None = None,
        gpu_mem: list[float] | None = None,
        net_latency: float = 0,
        queue: int = 0,
    ) -> None:
        snapshot = ResourceSnapshot(
            hostname=hostname,
            cpu_percent=cpu,
            memory_used_gb=memory_used,
            memory_total_gb=memory_total,
            gpu_load_percent=gpu_loads or [],
            gpu_memory_used_gb=gpu_mem or [],
            network_latency_ms=net_latency,
            queue_length=queue,
        )
        self.resources.update(snapshot)

    def update_model_availability(self, model_name: str, available: bool) -> None:
        # Update via the model map
        model = self.models._by_name.get(model_name)
        if model and model in self.models._models:
            self.models._models[model].available = available

    def update_agent_workload(
        self, agent_name: str, tasks_active: int, current_task: str = ""
    ) -> None:
        self._agent_workloads[agent_name] = {
            "tasks_active": tasks_active,
            "current_task": current_task,
            "updated_at": time.time(),
        }

    def register_experiment(self, experiment_id: str, description: str, machine: str) -> None:
        self._running_experiments.append(
            {
                "id": experiment_id,
                "description": description,
                "machine": machine,
                "started_at": time.time(),
            }
        )

    def complete_experiment(self, experiment_id: str) -> None:
        self._running_experiments = [
            e for e in self._running_experiments if e["id"] != experiment_id
        ]

    def run_health_check(self) -> list[HealthCheck]:
        """Run a full health check and return results."""
        self._last_check = time.time()
        checks: list[HealthCheck] = []

        # Check machines
        for m in self.hardware.get_all():
            status = m.get("status", "unknown")
            checks.append(
                HealthCheck(
                    component=f"machine:{m['hostname']}",
                    status="healthy" if status == "online" else "degraded",
                )
            )

        # Check model availability
        for model in self.models.get_all():
            checks.append(
                HealthCheck(
                    component=f"model:{model['name']}",
                    status="healthy" if model["available"] else "down",
                )
            )

        # Check resource overload
        for hostname in self.resources.get_overloaded():
            checks.append(
                HealthCheck(
                    component=f"resources:{hostname}",
                    status="degraded",
                    details="high load",
                )
            )

        self._health_log.extend(checks)
        self._health_log = self._health_log[-500:]
        return checks

    def get_system_state(self) -> dict:
        return {
            "machines": self.hardware.get_all(),
            "models": self.models.get_all(),
            "resources": self.resources.get_all_current(),
            "agent_workloads": self._agent_workloads,
            "running_experiments": self._running_experiments,
            "health": [h.to_dict() for h in self._health_log[-20:]],
        }

    def get_stats(self) -> dict:
        healthy = sum(1 for h in self._health_log[-50:] if h.status == "healthy")
        total = min(50, len(self._health_log))
        return {
            "machines": self.hardware.get_stats(),
            "models": self.models.get_stats(),
            "resources": self.resources.get_stats(),
            "active_agents": len(self._agent_workloads),
            "running_experiments": len(self._running_experiments),
            "health_rate": round(healthy / max(1, total), 3),
        }
