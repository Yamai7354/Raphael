import logging
import json
import random
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from .database import db_manager
from core.understanding.schemas import Task
from . import bus
from event_bus.event_bus import Event

logger = logging.getLogger("ai_router.experiment")


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


class ExperimentVariant(BaseModel):
    id: str
    name: str
    weight: float = 1.0  # Traffic split weight
    config: Dict[str, Any] = Field(
        default_factory=dict
    )  # Scoring weights: {"success_weight": 0.7, "latency_weight": 0.3}


class Experiment(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: List[ExperimentVariant]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    target_roles: List[str] = Field(default_factory=list)


class ExperimentManager:
    def __init__(self):
        self._active_experiments: Dict[str, Experiment] = {}
        self.is_running = False

    async def start(self):
        """Initialize experiment manager and load active experiments."""
        await self.refresh_experiments()
        self.is_running = True
        logger.info("Experiment Manager started.")

    async def stop(self):
        self.is_running = False
        logger.info("Experiment Manager stopped.")

    async def refresh_experiments(self):
        """Load active experiments from the database."""
        try:
            rows = await db_manager.fetch_all(
                "SELECT * FROM experiments WHERE status = ?",
                (ExperimentStatus.ACTIVE.value,),
            )
            new_active = {}
            for row in rows:
                variants_data = json.loads(row["variants"])
                variants = [ExperimentVariant(**v) for v in variants_data]

                # Extract target roles from description or metadata if we had a dedicated column,
                # for now let's assume it's in the variant config or just apply to all if empty.
                exp = Experiment(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    status=ExperimentStatus.ACTIVE,
                    variants=variants,
                    start_time=datetime.fromisoformat(row["start_time"])
                    if row["start_time"]
                    else None,
                    end_time=datetime.fromisoformat(row["end_time"])
                    if row["end_time"]
                    else None,
                )
                new_active[exp.id] = exp

            self._active_experiments = new_active
            logger.info(f"Loaded {len(self._active_experiments)} active experiments.")
        except Exception as e:
            logger.error(f"Failed to refresh experiments: {e}")

    def get_experiments_for_task(self, task: Task) -> List[Experiment]:
        """Determine which experiments apply to this task based on role."""
        role = task.agent_config.get("role")
        matching = []
        for exp in self._active_experiments.values():
            if not exp.target_roles or (role and role in exp.target_roles):
                matching.append(exp)
        return matching

    def get_active_experiments(self) -> List[Experiment]:
        """Return currently active experiments in memory."""
        return list(self._active_experiments.values())

    async def assign_variant(
        self, experiment: Experiment, task: Task
    ) -> ExperimentVariant:
        """Assign a variant to a task and record the assignment."""
        total_weight = sum(v.weight for v in experiment.variants)
        r = random.uniform(0, total_weight)
        cumulative = 0
        selected_variant = experiment.variants[0]

        for v in experiment.variants:
            cumulative += v.weight
            if r <= cumulative:
                selected_variant = v
                break

        task_id_str = str(task.id)
        await self._record_assignment(experiment.id, selected_variant.id, task_id_str)

        # Emit event
        if bus.event_bus:
            await bus.event_bus.publish(
                Event(
                    topic="experiment.assigned",
                    payload={
                        "experiment_id": experiment.id,
                        "variant_id": selected_variant.id,
                        "task_id": task_id_str,
                        "experiment_name": experiment.name,
                        "variant_name": selected_variant.name,
                    },
                    correlation_id=task_id_str,
                )
            )

        return selected_variant

    async def _record_assignment(
        self, experiment_id: str, variant_id: str, task_id: str
    ):
        """Persist the assignment to the database."""
        query = """
            INSERT INTO experiment_assignments (id, experiment_id, variant_id, task_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """
        assignment_id = str(uuid.uuid4())
        await db_manager.execute_query(
            query,
            (
                assignment_id,
                experiment_id,
                variant_id,
                task_id,
                datetime.now().isoformat(),
            ),
        )

    async def create_experiment(self, exp: Experiment):
        """Create a new experiment in the database."""
        query = """
            INSERT INTO experiments (id, name, description, status, start_time, end_time, variants)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        variants_json = json.dumps([v.dict() for v in exp.variants])
        await db_manager.execute_query(
            query,
            (
                exp.id,
                exp.name,
                exp.description,
                exp.status.value,
                exp.start_time.isoformat() if exp.start_time else None,
                exp.end_time.isoformat() if exp.end_time else None,
                variants_json,
            ),
        )
        if exp.status == ExperimentStatus.ACTIVE:
            await self.refresh_experiments()


# Global singleton
experiment_manager = ExperimentManager()
