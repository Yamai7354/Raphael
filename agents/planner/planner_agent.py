import logging
import uuid
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from agents.base import BaseAgent
from agents.api import get_event_bus
from data.schemas import SystemEvent, EventType, LayerContext
from core.understanding.schemas import Task, TaskStatus

logger = logging.getLogger("agents.planner")


class PlannerAgent(BaseAgent):
    """
    Agent responsible for decomposing complex tasks into sub-tasks.
    RAPHAEL-501. Uses injected event_bus when provided (e.g. by AgentRouter).
    """

    def __init__(
        self,
        agent_id: str = "Planner",
        capabilities: List[str] = None,
        event_bus: Any = None,
        graph_client: Any = None,
    ):
        super().__init__(agent_id, capabilities or ["planning", "task_decomposition"])
        self._event_bus = event_bus
        self._graph_client = graph_client

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a planning task. The payload should contain the task definition.
        """
        logs = []
        try:
            task_dict = payload.get("task", {})
            task_id = task_dict.get("task_id")
            if not task_id:
                logs.append("No task ID provided.")
                return self._standard_response(False, logs, None)

            # Analyze task complexity
            logs.append(f"Analyzing task {task_id} for decomposition.")
            subtasks = self._decompose_task(task_dict, logs)

            # Publish subtask creation events
            await self._publish_subtasks(task_dict, subtasks, logs)

            return self._standard_response(True, logs, {"subtasks": subtasks})

        except Exception as e:
            msg = f"Error in PlannerAgent: {str(e)}"
            logger.error(msg)
            logs.append(msg)
            return self._standard_response(False, logs, None)

    def _decompose_task(self, parent_task: Dict[str, Any], logs: List[str]) -> List[Dict[str, Any]]:
        """
        Decomposes a complex task into sub-tasks.
        Mock implementation for RAPHAEL-501.
        """
        parent_id = parent_task.get("task_id")

        # In a real implementation, this would call an LLM or use heuristics to determine subtasks.
        # For this prototype, we mock subtask generation if the task intent includes "plan" or "decompose"
        intent = parent_task.get("original_intent", "").lower()

        subtasks_data = []
        if "plan" in intent or "decompose" in intent or parent_task.get("priority", 5) < 3:
            logs.append("Criteria met for decomposition. Generating subtasks.")
            subtasks_data = [
                {
                    "title": f"Subtask 1 for {parent_id}: Analysis",
                    "description": "Analyze requirements and dependencies.",
                },
                {
                    "title": f"Subtask 2 for {parent_id}: Execution",
                    "description": "Execute the core logic of the task.",
                },
            ]
        else:
            logs.append("Task is simple or lacks decomposition markers. Returning as-is.")
            return []

        subtasks = []
        for st_data in subtasks_data:
            st_id = str(uuid.uuid4())
            new_task = {
                "task_id": st_id,
                "parent_id": parent_id,
                "original_intent": st_data["title"],
                "status": "pending",
                "priority": parent_task.get("priority", 5),
                "payload": {"description": st_data["description"]},
                "dependencies": [],
                "created_at": datetime.now().isoformat(),
            }
            subtasks.append(new_task)
            logs.append(f"Created subtask plan: {st_id}")

        return subtasks

    async def _publish_subtasks(
        self, parent_task: Dict[str, Any], subtasks: List[Dict[str, Any]], logs: List[str]
    ):
        """Publish events for the newly created subtasks via the global event bus."""
        bus = get_event_bus(self._event_bus)

        for st in subtasks:
            # We construct a Task object to match the schema, then turn it to dict for payload
            try:
                task_obj = Task(**st)

                event = SystemEvent(
                    event_type=EventType.TASK_CREATED,
                    source_layer=LayerContext(layer_number=6, module_name="planner_agent"),
                    payload={"task": task_obj.model_dump()},
                    priority=st.get("priority", 5),
                )

                await bus.publish(event)
                logs.append(f"Published TASK_CREATED event for {st['task_id']}")
                logger.debug(f"PlannerAgent published subtask creation: {st['task_id']}")
            except Exception as e:
                logs.append(f"Error publishing subtask {st.get('task_id')}: {e}")
                logger.error(f"Failed to mock-publish subtask: {e}")
