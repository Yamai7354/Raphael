"""
COG-205 — Experiment Assignment System.

Auto-assigns experiments to appropriate agents based on role:
coding agents → implementation tasks, research agents → data gathering,
evaluator agents → result validation.
"""

import logging
from dataclasses import dataclass

from .experiments import Experiment, ExperimentType

logger = logging.getLogger("swarm.cognition.experiment_assignment")


@dataclass
class AgentProfile:
    """Lightweight agent profile for assignment matching."""

    agent_id: str
    role: str  # researcher, builder, evaluator, etc.
    skills: list[str]
    current_load: int = 0  # Active assignments
    max_load: int = 3


class ExperimentAssigner:
    """
    Matches experiments to agents by role and skill.
    Optimizes distribution to prevent overloading.
    """

    # Mapping: experiment type → preferred agent roles
    TYPE_ROLE_MAP: dict[str, list[str]] = {
        ExperimentType.PROMPT_TEST.value: ["researcher", "evaluator"],
        ExperimentType.STRATEGY_TEST.value: ["researcher", "builder"],
        ExperimentType.MODEL_BENCHMARK.value: ["evaluator", "researcher"],
        ExperimentType.ARCHITECTURE_TEST.value: ["builder", "architect"],
        ExperimentType.CUSTOM.value: ["researcher", "builder", "evaluator"],
    }

    def __init__(self):
        self._agents: dict[str, AgentProfile] = {}

    def register_agent(
        self,
        agent_id: str,
        role: str,
        skills: list[str] | None = None,
        max_load: int = 3,
    ) -> None:
        self._agents[agent_id] = AgentProfile(
            agent_id=agent_id,
            role=role,
            skills=skills or [],
            max_load=max_load,
        )

    def assign(self, experiment: Experiment) -> str | None:
        """Find the best agent for an experiment. Returns agent_id or None."""
        preferred_roles = self.TYPE_ROLE_MAP.get(
            experiment.experiment_type.value, ["researcher"]
        )

        candidates = [
            a
            for a in self._agents.values()
            if a.role in preferred_roles and a.current_load < a.max_load
        ]

        if not candidates:
            # Fallback: any agent with capacity
            candidates = [
                a for a in self._agents.values() if a.current_load < a.max_load
            ]

        if not candidates:
            logger.warning(
                "no_available_agents for experiment=%s", experiment.experiment_id
            )
            return None

        # Score candidates: prefer lower load + skill match
        def score(agent: AgentProfile) -> float:
            load_score = 1.0 - (agent.current_load / agent.max_load)
            role_score = 1.0 if agent.role in preferred_roles else 0.3
            return load_score * role_score

        best = max(candidates, key=score)
        best.current_load += 1
        experiment.assigned_agent = best.agent_id
        logger.info(
            "experiment_assigned exp=%s agent=%s role=%s",
            experiment.experiment_id,
            best.agent_id,
            best.role,
        )
        return best.agent_id

    def release(self, agent_id: str) -> None:
        agent = self._agents.get(agent_id)
        if agent and agent.current_load > 0:
            agent.current_load -= 1

    def get_load_summary(self) -> list[dict]:
        return [
            {
                "agent_id": a.agent_id,
                "role": a.role,
                "load": a.current_load,
                "max": a.max_load,
            }
            for a in self._agents.values()
        ]
