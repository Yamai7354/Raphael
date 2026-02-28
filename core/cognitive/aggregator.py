import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ResultAggregator:
    """
    Packages the validated plan from the Reasoning module.
    Could eventually perform summarization or add execution metadata.
    """

    def compile_package(self, validated_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes the raw dictionary plan from the planner and ensures it is
        sealed and stamped as ready for Swarm distribution.
        """

        compiled_payload = {
            "version": "1.0",
            "type": "EXECUTION_PLAN",
            "plan_metadata": {
                "id": validated_plan.get("plan_id"),
                "task_id": validated_plan.get("task_id"),
                "total_steps": len(validated_plan.get("execution_sequence", [])),
                "context_hints": validated_plan.get("memory_context"),
            },
            "sequence": validated_plan.get("execution_sequence"),
        }

        logger.debug(
            f"Result Aggregator compiled Execution Plan Package for {compiled_payload['plan_metadata']['id']}"
        )
        return compiled_payload
