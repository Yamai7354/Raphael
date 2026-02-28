"""
COG-209 — Research Mission System.

Converts questions and hypotheses into structured missions
with objectives, required agents, expected outputs, and evaluation metrics.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.cognitive.missions")


class MissionStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MissionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResearchMission:
    """A structured research mission for the swarm."""

    mission_id: str
    objective: str
    domain: str
    priority: MissionPriority = MissionPriority.MEDIUM
    required_agents: list[str] = field(default_factory=list)  # roles needed
    expected_outputs: list[str] = field(default_factory=list)
    evaluation_metrics: list[str] = field(default_factory=list)
    question_id: str | None = None
    hypothesis_id: str | None = None
    assigned_agents: list[str] = field(default_factory=list)  # actual agent IDs
    status: MissionStatus = MissionStatus.PLANNED
    progress: float = 0.0
    results: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "domain": self.domain,
            "priority": self.priority.value,
            "required_agents": self.required_agents,
            "expected_outputs": self.expected_outputs,
            "assigned_agents": self.assigned_agents,
            "status": self.status.value,
            "progress": round(self.progress, 2),
        }


class MissionSystem:
    """Creates and manages research missions from questions and hypotheses."""

    PRIORITY_MAP = {
        "critical": MissionPriority.CRITICAL,
        "high": MissionPriority.HIGH,
        "medium": MissionPriority.MEDIUM,
        "low": MissionPriority.LOW,
    }

    def __init__(self):
        self._missions: dict[str, ResearchMission] = {}

    def create_from_question(
        self,
        question_text: str,
        domain: str,
        importance: float,
        question_id: str | None = None,
    ) -> ResearchMission:
        priority = (
            MissionPriority.CRITICAL
            if importance >= 8
            else (MissionPriority.HIGH if importance >= 6 else MissionPriority.MEDIUM)
        )
        mission = ResearchMission(
            mission_id=f"mission_{uuid.uuid4().hex[:8]}",
            objective=question_text,
            domain=domain,
            priority=priority,
            required_agents=["researcher"],
            expected_outputs=["research_report", "knowledge_update"],
            evaluation_metrics=["relevance", "completeness", "accuracy"],
            question_id=question_id,
        )
        self._missions[mission.mission_id] = mission
        logger.info(
            "mission_created id=%s domain=%s priority=%s",
            mission.mission_id,
            domain,
            priority.value,
        )
        return mission

    def create_from_hypothesis(
        self,
        hypothesis_statement: str,
        domain: str,
        experiment_plan: str,
        hypothesis_id: str | None = None,
    ) -> ResearchMission:
        mission = ResearchMission(
            mission_id=f"mission_{uuid.uuid4().hex[:8]}",
            objective=f"Test hypothesis: {hypothesis_statement}",
            domain=domain,
            priority=MissionPriority.HIGH,
            required_agents=["researcher", "evaluator", "builder"],
            expected_outputs=["experiment_results", "conclusion"],
            evaluation_metrics=["statistical_significance", "reproducibility"],
            hypothesis_id=hypothesis_id,
        )
        self._missions[mission.mission_id] = mission
        return mission

    def assign_agent(self, mission_id: str, agent_id: str) -> None:
        m = self._missions.get(mission_id)
        if m and agent_id not in m.assigned_agents:
            m.assigned_agents.append(agent_id)
            if m.status == MissionStatus.PLANNED:
                m.status = MissionStatus.ACTIVE

    def update_progress(self, mission_id: str, progress: float) -> None:
        m = self._missions.get(mission_id)
        if m:
            m.progress = min(1.0, progress)

    def complete(self, mission_id: str, results: dict | None = None) -> None:
        m = self._missions.get(mission_id)
        if m:
            m.status = MissionStatus.COMPLETED
            m.progress = 1.0
            m.results = results or {}
            m.completed_at = time.time()
            logger.info("mission_completed id=%s", mission_id)

    def fail(self, mission_id: str) -> None:
        m = self._missions.get(mission_id)
        if m:
            m.status = MissionStatus.FAILED
            m.completed_at = time.time()

    def get_active(self) -> list[ResearchMission]:
        return [m for m in self._missions.values() if m.status == MissionStatus.ACTIVE]

    def get_planned(self) -> list[ResearchMission]:
        return sorted(
            [m for m in self._missions.values() if m.status == MissionStatus.PLANNED],
            key=lambda m: list(MissionPriority).index(m.priority),
        )

    def get_all(self) -> list[dict]:
        return [m.to_dict() for m in self._missions.values()]

    def get_stats(self) -> dict:
        counts: dict[str, int] = {}
        for m in self._missions.values():
            counts[m.status.value] = counts.get(m.status.value, 0) + 1
        return {"total": len(self._missions), "by_status": counts}
