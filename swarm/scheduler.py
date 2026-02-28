import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Manages the Execution Plan queue.
    Tracks which subtasks are PENDING, RUNNING, or COMPLETED.
    """

    def __init__(self):
        self.pending_tasks: Dict[str, Dict[str, Any]] = {}  # plan_id -> {sub_task_id -> task_data}
        self.running_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: Dict[str, set] = {}  # plan_id -> set of completed sub_task_ids

    def load_plan(self, execution_plan: Dict[str, Any]):
        """Ingest a finalized plan and stage its subtasks."""
        plan_id = execution_plan.get("plan_metadata", {}).get("id")
        if not plan_id:
            logger.error("Tried to load Execution Plan with no plan_metadata ID.")
            return

        sequence = execution_plan.get("sequence", [])

        self.pending_tasks[plan_id] = {st["sub_task_id"]: st for st in sequence}
        self.running_tasks[plan_id] = {}
        self.completed_tasks[plan_id] = set()
        logger.debug(f"Task Scheduler loaded plan {plan_id} with {len(sequence)} subtasks.")

    def get_ready_tasks(self, plan_id: str) -> List[Dict[str, Any]]:
        """
        Returns a list of tasks whose dependencies have all been met (are in completed_tasks).
        """
        if plan_id not in self.pending_tasks:
            return []

        ready = []
        completed = self.completed_tasks.get(plan_id, set())

        for st_id, st_data in self.pending_tasks[plan_id].items():
            deps = set(st_data.get("dependencies", []))
            if deps.issubset(completed):
                ready.append(st_data)

        return ready

    def mark_running(self, plan_id: str, sub_task_id: str):
        """Moves a task from pending to running."""
        if plan_id in self.pending_tasks and sub_task_id in self.pending_tasks[plan_id]:
            task = self.pending_tasks[plan_id].pop(sub_task_id)
            self.running_tasks[plan_id][sub_task_id] = task
            logger.debug(f"Task Scheduler shifted {sub_task_id} to RUNNING.")

    def mark_completed(self, plan_id: str, sub_task_id: str):
        """Moves a task from running to completed, unlocking downstream dependencies."""
        if plan_id in self.running_tasks and sub_task_id in self.running_tasks[plan_id]:
            self.running_tasks[plan_id].pop(sub_task_id)
            self.completed_tasks[plan_id].add(sub_task_id)
            logger.debug(f"Task Scheduler marked {sub_task_id} as COMPLETED.")

    def is_plan_finished(self, plan_id: str) -> bool:
        """Returns True if the plan has no pending and no running tasks."""
        if plan_id not in self.pending_tasks:
            return True
        return len(self.pending_tasks[plan_id]) == 0 and len(self.running_tasks[plan_id]) == 0
