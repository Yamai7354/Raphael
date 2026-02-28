import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Simulates retrieval of historical data from the Polyglot Memory System.
    Enriches incoming Tasks with necessary past learnings.
    """

    def build_context(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a raw task and injects a `memory_context` block.
        """
        # In a real scenario, this queries LanceDB/Redis using the task intent
        # For our skeleton, we append a mock historical tip based on the intent string.

        intent = task_payload.get("original_intent", "").lower()
        context_tips = []

        if "deploy" in intent or "bash" in str(task_payload.get("sub_tasks", [])):
            context_tips.append(
                "Historical Error: Deploy scripts require 'sudo' permissions in this environment."
            )

        if "network" in intent:
            context_tips.append(
                "Graph Memory: Target subnet 192.168.1.0/24 is restricted during business hours."
            )

        if not context_tips:
            context_tips.append("No relevant historical context found for this task.")

        task_payload["memory_context"] = context_tips
        logger.debug(
            f"Attached {len(context_tips)} memory snippets to Task {task_payload.get('task_id')}"
        )

        return task_payload
