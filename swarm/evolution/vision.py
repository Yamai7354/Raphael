"""
SWARM-108 — Swarm Vision System.

Long-term objectives guiding swarm behavior and research priorities.
Agents reference vision when selecting tasks and research targets.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("swarm.evolution.vision")


@dataclass
class VisionObjective:
    """A single long-term objective for the swarm."""

    objective_id: str
    title: str
    description: str
    priority: float = 5.0  # 1-10
    domain: str = "general"
    progress: float = 0.0  # 0.0 → 1.0
    target_date: float | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "objective_id": self.objective_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "domain": self.domain,
            "progress": round(self.progress, 2),
            "target_date": self.target_date,
        }


class SwarmVision:
    """
    Manages long-term objectives that guide the swarm's behavior.
    Agents query the vision to prioritize tasks and research.
    """

    def __init__(self):
        self._objectives: dict[str, VisionObjective] = {}

    def set_objective(
        self,
        objective_id: str,
        title: str,
        description: str = "",
        priority: float = 5.0,
        domain: str = "general",
        target_date: float | None = None,
    ) -> VisionObjective:
        """Set or update a vision objective."""
        obj = VisionObjective(
            objective_id=objective_id,
            title=title,
            description=description,
            priority=priority,
            domain=domain,
            target_date=target_date,
        )
        self._objectives[objective_id] = obj
        logger.info("vision_set id=%s title=%s priority=%.1f", objective_id, title, priority)
        return obj

    def update_progress(self, objective_id: str, delta: float) -> None:
        """Increment progress on an objective."""
        obj = self._objectives.get(objective_id)
        if obj:
            obj.progress = min(1.0, obj.progress + delta)
            logger.info(
                "vision_progress id=%s progress=%.2f",
                objective_id,
                obj.progress,
            )

    def get_priorities(self) -> list[VisionObjective]:
        """Return objectives sorted by priority (highest first)."""
        return sorted(
            self._objectives.values(),
            key=lambda o: o.priority * (1.0 - o.progress),  # Incomplete + high priority first
            reverse=True,
        )

    def get_research_targets(self) -> list[str]:
        """Return domains the swarm should focus research on."""
        priorities = self.get_priorities()
        return [obj.domain for obj in priorities[:5] if obj.progress < 1.0]

    def should_prioritize_task(self, task_domain: str) -> float:
        """
        Returns a priority multiplier for tasks in a given domain.
        Higher if the domain aligns with current vision objectives.
        """
        for obj in self.get_priorities():
            if obj.domain == task_domain and obj.progress < 1.0:
                return 1.0 + (obj.priority / 10.0)
        return 1.0  # No bonus

    def get_all_objectives(self) -> list[dict]:
        return [o.to_dict() for o in self.get_priorities()]

    def remove_objective(self, objective_id: str) -> None:
        self._objectives.pop(objective_id, None)
