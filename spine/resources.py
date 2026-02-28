import logging
from typing import Dict, Optional
from uuid import UUID
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ResourceState(BaseModel):
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    active_agent_slots: int = 0
    max_agent_slots: int = 10


class ResourceManager:
    """
    Evaluates system resource availability before permitting tasks to spawn agents.
    Maintains a simple queue string for tasks that exceed current hardware limits.
    """

    def __init__(self, max_slots: int = 10):
        self.state = ResourceState(max_agent_slots=max_slots)
        self.queued_tasks: list[Dict] = []

    def update_telemetry(self, cpu: float, memory: float):
        """Called by the Health Monitor to keep hardware state fresh."""
        self.state.cpu_usage_percent = cpu
        self.state.memory_usage_percent = memory

    def can_schedule_task(self, task_payload: Dict) -> bool:
        """
        Determines if the system has enough slots and hardware headroom
        to spin up new agents for this task.
        """
        # Simple heuristic: If CPU > 90% or all slots full, we deny scheduling.
        if self.state.cpu_usage_percent > 90.0:
            logger.warning("Resource constraint: CPU overload. Queuing task.")
            return False

        if self.state.active_agent_slots >= self.state.max_agent_slots:
            logger.warning("Resource constraint: Agent slots exhausted. Queuing task.")
            return False

        return True

    def allocate(self, task_payload: Dict):
        """Claims a slot for a task that was cleared to run."""
        self.state.active_agent_slots += 1
        logger.debug(
            f"Allocated agent slot. Active: {self.state.active_agent_slots}/{self.state.max_agent_slots}"
        )

    def free_slot(self):
        """Releases a slot when an agent finishes execution."""
        if self.state.active_agent_slots > 0:
            self.state.active_agent_slots -= 1
            logger.debug(
                f"Freed agent slot. Active: {self.state.active_agent_slots}/{self.state.max_agent_slots}"
            )

    def queue_task(self, task_payload: Dict):
        """Holds a task until resources free up."""
        self.queued_tasks.append(task_payload)

    def get_queued_task(self) -> Optional[Dict]:
        """Pops a queued task if available."""
        if self.queued_tasks:
            return self.queued_tasks.pop(0)
        return None
