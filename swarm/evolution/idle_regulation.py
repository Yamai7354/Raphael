"""
SWARM-114 — Idle Agent Regulation.

Prevents agents from excessive idle exploration.
Idle agents must: join tasks, assist others, enter sleep mode,
or perform system maintenance. Exploration limited when memory
growth rate exceeds threshold.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("swarm.evolution.idle_regulation")


class IdleAction(str, Enum):
    """Actions that can be assigned to idle agents."""

    JOIN_TASK = "join_task"
    ASSIST_AGENT = "assist_agent"
    SLEEP = "sleep"
    MAINTENANCE = "maintenance"


@dataclass
class AgentActivityRecord:
    """Tracks an agent's activity state."""

    agent_id: str
    last_active: float = field(default_factory=time.time)
    idle_since: float | None = None
    assigned_action: IdleAction | None = None
    total_idle_time: float = 0.0
    exploration_count: int = 0

    @property
    def is_idle(self) -> bool:
        return self.idle_since is not None

    @property
    def idle_duration(self) -> float:
        if self.idle_since is None:
            return 0.0
        return time.time() - self.idle_since

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "is_idle": self.is_idle,
            "idle_duration": round(self.idle_duration, 1),
            "assigned_action": self.assigned_action.value if self.assigned_action else None,
            "total_idle_time": round(self.total_idle_time, 1),
            "exploration_count": self.exploration_count,
        }


class IdleRegulator:
    """
    Monitors agent activity and assigns idle agents to productive work.
    Limits exploration when memory growth rate is too high.
    """

    def __init__(
        self,
        idle_threshold_seconds: float = 300.0,  # 5 minutes
        max_exploration_rate: float = 0.5,  # Max fraction of agents exploring
        memory_growth_limit: float = 100.0,  # Max new memories per hour
    ):
        self.idle_threshold = idle_threshold_seconds
        self.max_exploration_rate = max_exploration_rate
        self.memory_growth_limit = memory_growth_limit
        self._agents: dict[str, AgentActivityRecord] = {}
        self._memory_growth_rate: float = 0.0
        self._exploration_throttled: bool = False

    def register_agent(self, agent_id: str) -> None:
        self._agents[agent_id] = AgentActivityRecord(agent_id=agent_id)

    def mark_active(self, agent_id: str) -> None:
        """Mark an agent as active (currently working on a task)."""
        record = self._agents.get(agent_id)
        if record:
            if record.is_idle and record.idle_since:
                record.total_idle_time += time.time() - record.idle_since
            record.last_active = time.time()
            record.idle_since = None
            record.assigned_action = None

    def mark_idle(self, agent_id: str) -> None:
        """Mark an agent as idle."""
        record = self._agents.get(agent_id)
        if record and not record.is_idle:
            record.idle_since = time.time()

    def mark_exploring(self, agent_id: str) -> None:
        """Record that an agent is exploring."""
        record = self._agents.get(agent_id)
        if record:
            record.exploration_count += 1

    def update_memory_growth(self, rate: float) -> None:
        """Update the current memory growth rate (memories per hour)."""
        self._memory_growth_rate = rate
        self._exploration_throttled = rate > self.memory_growth_limit
        if self._exploration_throttled:
            logger.warning(
                "exploration_throttled memory_growth=%.1f limit=%.1f",
                rate,
                self.memory_growth_limit,
            )

    def check_idle_agents(self) -> list[dict]:
        """
        Identify idle agents and assign them productive work.
        Returns list of assignments made.
        """
        assignments = []
        now = time.time()

        for record in self._agents.values():
            if not record.is_idle:
                # Check if agent has been inactive long enough to be considered idle
                if (now - record.last_active) > self.idle_threshold:
                    self.mark_idle(record.agent_id)

            if record.is_idle and record.assigned_action is None:
                action = self._decide_action(record)
                record.assigned_action = action
                assignments.append(
                    {
                        "agent_id": record.agent_id,
                        "action": action.value,
                        "idle_duration": round(record.idle_duration, 1),
                    }
                )
                logger.info(
                    "idle_assigned agent=%s action=%s idle=%.0fs",
                    record.agent_id,
                    action.value,
                    record.idle_duration,
                )

        return assignments

    def _decide_action(self, record: AgentActivityRecord) -> IdleAction:
        """Decide what an idle agent should do."""
        # If exploration is throttled, don't allow exploration-adjacent work
        if self._exploration_throttled:
            return IdleAction.MAINTENANCE

        # Short idle: try to join a task
        if record.idle_duration < self.idle_threshold * 2:
            return IdleAction.JOIN_TASK

        # Medium idle: assist another agent
        if record.idle_duration < self.idle_threshold * 4:
            return IdleAction.ASSIST_AGENT

        # Long idle: sleep or maintenance
        if record.total_idle_time > 3600:  # Over 1 hour total idle
            return IdleAction.SLEEP

        return IdleAction.MAINTENANCE

    def can_explore(self) -> bool:
        """Check if exploration is currently allowed."""
        if self._exploration_throttled:
            return False

        active = sum(1 for r in self._agents.values() if not r.is_idle)
        exploring = sum(
            1 for r in self._agents.values() if r.exploration_count > 0 and not r.is_idle
        )
        if active == 0:
            return True
        return (exploring / active) < self.max_exploration_rate

    def get_idle_agents(self) -> list[str]:
        return [r.agent_id for r in self._agents.values() if r.is_idle]

    def get_status(self) -> dict:
        total = len(self._agents)
        idle = len(self.get_idle_agents())
        return {
            "total_agents": total,
            "idle_agents": idle,
            "active_agents": total - idle,
            "exploration_throttled": self._exploration_throttled,
            "memory_growth_rate": round(self._memory_growth_rate, 1),
            "agents": [r.to_dict() for r in self._agents.values()],
        }

    def remove_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
