import logging
from typing import Dict, Optional
from uuid import UUID
from core.understanding.schemas import Task, TaskStatus

logger = logging.getLogger(__name__)


class GoalManager:
    """
    Maintains the lifecycle and hierarchy of active Tasks and SubTasks.
    Responsible for storing tasks before assigning them down to Execution engines.
    """

    def __init__(self):
        # In-memory storage (to be replicated by Layer 4 Working Memory later)
        self.active_tasks: Dict[UUID, Task] = {}

    def register_task(self, task: Task):
        """
        Saves a newly parsed and decomposed task into active working memory,
        and marks it as ready for assignment.
        """
        self.active_tasks[task.task_id] = task
        logger.info(f"Goal Manager registered new Task {task.task_id}")

    def update_task_status(self, task_id: UUID, status: TaskStatus):
        """Updates the status of a high-level task."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id].status = status
            logger.debug(f"Task {task_id} updated to {status.value}")

    def update_subtask_status(self, parent_task_id: UUID, subtask_id: UUID, status: TaskStatus):
        """Updates the status of an executing SubTask and evaluates parent completion."""
        if parent_task_id not in self.active_tasks:
            return

        task = self.active_tasks[parent_task_id]
        all_complete = True

        for st in task.sub_tasks:
            if st.sub_task_id == subtask_id:
                st.status = status
                logger.debug(f"SubTask {subtask_id} updated to {status.value}")

            if st.status != TaskStatus.COMPLETED:
                all_complete = False

        # Auto-complete the parent goal if all SubTasks are done
        if all_complete:
            self.update_task_status(parent_task_id, TaskStatus.COMPLETED)

    def get_pending_tasks(self) -> Dict[UUID, Task]:
        """Returns all tasks currently waiting to be picked up by Layer 6 (Swarm Manager)."""
        return {
            tid: task
            for tid, task in self.active_tasks.items()
            if task.status == TaskStatus.PENDING
        }
