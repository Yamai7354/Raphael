import logging
from typing import Any

from swarm.scheduler import TaskScheduler
from swarm.model_router import ModelRouter
from swarm.dynamics import SwarmMetabolism

logger = logging.getLogger(__name__)


class SwarmOrchestrator:
    """
    The orchestrator continuously interfaces with the Scheduler to pull Ready tasks,
    asks the ModelRouter for capable agents, and formats dispatch payloads.
    """

    def __init__(self):
        self.scheduler = TaskScheduler()
        self.router = ModelRouter()
        self.metabolism = SwarmMetabolism()

    def ingest_plan(self, execution_plan: dict[str, Any]):
        """Pushes a new finalized plan into the Scheduler."""
        self.scheduler.load_plan(execution_plan)

    async def process_queue(self, plan_id: str) -> list[dict[str, Any]]:
        """
        Polls the scheduler for ready tasks. Assigns agents to them.
        Returns a list of payload dictionaries formatted for agent execution.
        """
        dispatch_list = []
        ready_tasks = self.scheduler.get_ready_tasks(plan_id)

        for task in ready_tasks:
            st_id = task.get("sub_task_id")
            reqs = task.get("required_capabilities", [])

            agent_id = await self.router.find_agent(reqs)

            if agent_id:
                # Mark it running so we don't dispatch it twice
                self.scheduler.mark_running(plan_id, st_id)

                # Bundle the task (Injecting all task parameters like 'command', 'code_content')
                dispatch_bundle = {
                    **task,
                    "plan_id": plan_id,
                    "assigned_agent": agent_id,
                    "capabilities": reqs,
                    "context": {"memory_session": "active"},
                }
                dispatch_list.append(dispatch_bundle)

                # Metabolism: Deduct energy when a task is dispatched
                self.metabolism.deduct_exploration_cost()
            else:
                logger.error(
                    f"Orchestrator halting dispatch for {st_id}: No capable agent available."
                )

        return dispatch_list

    def handle_completion(self, plan_id: str, sub_task_id: str):
        """Signals the scheduler that an assigned agent successfully finished a task."""
        self.scheduler.mark_completed(plan_id, sub_task_id)
        # Metabolism: Reward energy for completed task
        self.metabolism.add_task_reward()
        # Record outcome to episodic metrics (e.g. episodic_memory.log_event(...))

    def is_finished(self, plan_id: str) -> bool:
        """Returns whether the entire plan has been resolved."""
        return self.scheduler.is_plan_finished(plan_id)
