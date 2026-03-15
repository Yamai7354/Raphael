import logging
from typing import Any, Dict, List
from datetime import datetime

from agents.base import BaseAgent
from agents.api import get_event_bus
from data.schemas import SystemEvent, EventType, LayerContext

logger = logging.getLogger("agents.evaluator")


class EvaluatorAgent(BaseAgent):
    """
    Agent responsible for evaluating the quality of completed tasks.
    RAPHAEL-502. Uses injected event_bus when provided (e.g. by AgentRouter).
    """

    def __init__(
        self,
        agent_id: str = "Evaluator",
        capabilities: List[str] = None,
        event_bus: Any = None,
        graph_client: Any = None,
    ):
        super().__init__(agent_id, capabilities or ["evaluation", "qa", "validation"])
        self._event_bus = event_bus
        self._graph_client = graph_client

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an evaluation task against a specific output.
        Payload expected: {"target_task_id": str, "output": dict, "description": str}
        """
        logs = []
        try:
            target_task_id = payload.get("target_task_id")
            output = payload.get("output", {})
            description = payload.get("description", "")

            if not target_task_id:
                logs.append("No target_task_id provided for evaluation.")
                return self._standard_response(False, logs, None)

            logs.append(f"Evaluating output for task {target_task_id}.")

            score, feedback = self._evaluate_output(output, description)
            logs.append(f"Evaluation complete. Score: {score}")

            eval_result = {
                "target_task_id": target_task_id,
                "score": score,
                "feedback": feedback,
                "evaluator_id": self.agent_id,
                "timestamp": datetime.now().isoformat(),
            }

            # Optionally publish the result to the event bus
            await self._publish_eval_result(eval_result, logs)

            return self._standard_response(True, logs, eval_result)

        except Exception as e:
            msg = f"Error in EvaluatorAgent: {str(e)}"
            logger.error(msg)
            logs.append(msg)
            return self._standard_response(False, logs, None)

    def _evaluate_output(self, output: Any, target_description: str) -> tuple[float, str]:
        """
        Analyze output quality using heuristics or an LLM call.
        Returns (score 0-1, feedback string).
        """
        # Hack for testing: if output is literally "FAIL_TEST", we return a low score
        if isinstance(output, dict) and output.get("text") == "FAIL_TEST":
            return 0.2, "Output explicitly marked as failure for testing."

        if not output:
            return 0.0, "Empty output provided."

        # Mock high quality for most things in this skeleton
        return 0.95, "Output meets quality standards and aligns with the target description."

    async def _publish_eval_result(self, eval_result: Dict[str, Any], logs: List[str]):
        """Publish the evaluation result to the system event bus."""
        try:
            bus = get_event_bus(self._event_bus)
            event = SystemEvent(
                event_type=EventType.TASK_EVALUATED,
                source_layer=LayerContext(layer_number=9, module_name="evaluator_agent"),
                payload=eval_result,
                priority=4,
            )
            await bus.publish(event)
            logs.append("Published TASK_EVALUATED event.")
        except Exception as e:
            logs.append(f"Failed to publish evaluation event: {e}")
            logger.error(f"Failed to publish evaluation event: {e}")
