import logging
import uuid
from typing import Dict, Any
from datetime import datetime

from event_bus.event_bus import Event
from . import bus

logger = logging.getLogger("ai_router.evaluation")


class EvaluationService:
    """
    Service that monitors task completion and manages the self-evaluation loop.
    If a task fails evaluation, it automatically triggers a refinement subtask.
    """

    def __init__(self, score_threshold: float = 0.5):
        self._running = False
        self.score_threshold = score_threshold
        # Cache to track tasks being evaluated
        self._pending_evaluations: Dict[str, Dict[str, Any]] = {}

    async def start(self):
        """Start the evaluation service and subscribe to events."""
        if self._running:
            return

        self._running = True
        logger.info("EvaluationService starting...")

        if bus.event_bus:
            await bus.event_bus.subscribe("task.completed", self._handle_task_completed)
            await bus.event_bus.subscribe("task.eval_result", self._handle_eval_result)
            logger.info("EvaluationService subscribed to events.")
        else:
            logger.warning(
                "Event bus not available, EvaluationService cannot subscribe."
            )

    async def stop(self):
        """Stop the evaluation service."""
        self._running = False
        logger.info("EvaluationService stopped.")

    async def _handle_task_completed(self, event: Event):
        """
        Handle 'task.completed' events.
        Decide if the task needs evaluation.
        """
        try:
            payload = event.payload
            task_id = payload.get("task_id")
            node_id = payload.get("node_id")
            output = payload.get("output")

            if not task_id:
                return

            logger.info(f"EvaluationService: Triggering evaluation for task {task_id}")

            eval_request = {
                "task_id": task_id,
                "node_id": node_id,
                "output": output,
                "description": payload.get("description", "Unknown task"),
            }

            self._pending_evaluations[task_id] = eval_request

            await bus.event_bus.publish(
                Event(
                    topic="task.evaluate", payload=eval_request, correlation_id=task_id
                )
            )

        except Exception as e:
            logger.error(f"Error handling task.completed in EvaluationService: {e}")

    async def _handle_eval_result(self, event: Event):
        """
        Handle 'task.eval_result' events.
        If score is too low, trigger refinement.
        """
        try:
            payload = event.payload
            task_id = payload.get("task_id")
            score = payload.get("score", 0.0)
            feedback = payload.get("feedback", "")

            if not task_id or task_id not in self._pending_evaluations:
                return

            original_request = self._pending_evaluations.pop(task_id)

            if score < self.score_threshold:
                logger.warning(
                    f"Task {task_id} failed evaluation (Score: {score}). Triggering refinement."
                )
                await self._trigger_refinement(original_request, feedback)
            else:
                logger.info(f"Task {task_id} passed evaluation (Score: {score}).")

        except Exception as e:
            logger.error(f"Error handling task.eval_result in EvaluationService: {e}")

    async def _trigger_refinement(
        self, original_request: Dict[str, Any], feedback: str
    ):
        """Create a new refinement task as a subtask."""
        orig_task_id = original_request["task_id"]

        refinement_payload = {
            "id": str(uuid.uuid4()),
            "title": f"Refinement: {original_request['description'][:30]}...",
            "description": f"Refine previous task output based on feedback: {feedback}",
            "status": "pending",
            "priority": "high",
            "type": "refactor",
            "parent_id": orig_task_id,
            "input": {
                "original_output": original_request["output"],
                "feedback": feedback,
            },
            "created_at": datetime.now().isoformat(),
        }

        await bus.event_bus.publish(
            Event(
                topic="task.create",
                payload=refinement_payload,
                correlation_id=orig_task_id,
            )
        )
        logger.info(f"Published refinement task for {orig_task_id}")


evaluation_service = EvaluationService()
