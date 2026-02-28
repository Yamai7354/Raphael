"""
WORLD-407 — Hardware-Aware Task Scheduler.

Improves task assignment using hardware capabilities:
machine performance, GPU availability, model location,
task requirements, and current load.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from .hardware_registry import HardwareRegistry
from .model_capabilities import ModelCapabilityMap
from .resource_awareness import ResourceAwareness

logger = logging.getLogger("core.world_model.hw_scheduler")


@dataclass
class TaskAssignment:
    """A task assigned to a specific machine."""

    assignment_id: str = field(default_factory=lambda: f"ta_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    task_type: str = ""
    assigned_to: str = ""  # hostname
    model_name: str = ""
    reason: str = ""
    estimated_duration_ms: float = 0
    assigned_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "assignment_id": self.assignment_id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "machine": self.assigned_to,
            "model": self.model_name,
            "reason": self.reason,
        }


@dataclass
class TaskRequirements:
    """Requirements for a task to determine optimal placement."""

    task_id: str = ""
    task_type: str = ""
    requires_gpu: bool = False
    min_vram_gb: float = 0
    min_ram_gb: float = 0
    preferred_model: str = ""
    max_latency_ms: float = 0  # 0 = no constraint
    priority: int = 5  # 1 (highest) - 10 (lowest)


class HardwareAwareScheduler:
    """Assigns tasks to machines based on hardware capabilities and load."""

    def __init__(
        self,
        hardware: HardwareRegistry | None = None,
        models: ModelCapabilityMap | None = None,
        resources: ResourceAwareness | None = None,
    ):
        self.hardware = hardware or HardwareRegistry()
        self.models = models or ModelCapabilityMap()
        self.resources = resources or ResourceAwareness()
        self._assignments: list[TaskAssignment] = []

    def schedule(self, req: TaskRequirements) -> TaskAssignment:
        """Find optimal machine for a task."""
        reasons: list[str] = []

        # 1. If preferred model specified, route to its host
        if req.preferred_model:
            model = self.models._by_name.get(req.preferred_model)
            if model and model in self.models._models:
                m = self.models._models[model]
                if m.hosted_on:
                    hostname = m.hosted_on[0]
                    reasons.append(f"model_affinity:{req.preferred_model}@{hostname}")
                    return self._assign(req, hostname, req.preferred_model, " | ".join(reasons))

        # 2. Find optimal machine based on resource availability
        hostname = self.resources.get_optimal_for_task(
            required_memory_gb=req.min_ram_gb,
            require_gpu=req.requires_gpu,
        )
        if hostname:
            reasons.append(f"optimal_resources:{hostname}")
        else:
            # Fallback: find any machine meeting min requirements
            available = self.hardware.get_available(
                min_ram_gb=req.min_ram_gb,
                min_vram_gb=req.min_vram_gb,
            )
            if available:
                hostname = available[0].hostname
                reasons.append(f"fallback_hardware:{hostname}")
            else:
                hostname = "local"
                reasons.append("no_match:defaulting_to_local")

        # 3. Find best model for task type
        model_name = req.preferred_model
        if not model_name:
            best = self.models.find_best_for_task(
                req.task_type, max_vram_gb=req.min_vram_gb or None
            )
            model_name = best.name if best else ""
            if model_name:
                reasons.append(f"auto_model:{model_name}")

        return self._assign(req, hostname, model_name, " | ".join(reasons))

    def _assign(
        self, req: TaskRequirements, hostname: str, model_name: str, reason: str
    ) -> TaskAssignment:
        assignment = TaskAssignment(
            task_id=req.task_id,
            task_type=req.task_type,
            assigned_to=hostname,
            model_name=model_name,
            reason=reason,
        )
        self._assignments.append(assignment)
        self.hardware.add_workload(hostname, req.task_id)
        logger.info(
            "task_scheduled task=%s -> machine=%s model=%s reason=%s",
            req.task_id,
            hostname,
            model_name,
            reason,
        )
        return assignment

    def complete_task(self, task_id: str, hostname: str) -> None:
        self.hardware.remove_workload(hostname, task_id)

    def get_assignments(self, limit: int = 20) -> list[dict]:
        return [a.to_dict() for a in self._assignments[-limit:]]

    def get_stats(self) -> dict:
        by_machine: dict[str, int] = {}
        for a in self._assignments:
            by_machine[a.assigned_to] = by_machine.get(a.assigned_to, 0) + 1
        return {
            "total_assigned": len(self._assignments),
            "by_machine": by_machine,
        }
