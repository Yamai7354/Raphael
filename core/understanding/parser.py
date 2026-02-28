import logging
from typing import Optional, Dict, Any
from data.schemas import SystemEvent, EventType
from core.understanding.schemas import Task

logger = logging.getLogger(__name__)


class TaskParser:
    """
    Evaluates semantic OBSERVATION events from Layer 2.
    If the event implies an actionable direction, it translates the event
    into a core Task object.
    """

    def parse_event(self, event: SystemEvent) -> Optional[Task]:
        """
        Takes an observation and attempts to parse it into an action.
        Returns a base Task if successful, otherwise None.
        """
        payload = event.payload
        intent = payload.get("intent", "background_info")

        # We only spawn execution tasks for explicit directives or critical alerts.
        # Background telemetry or idle chatter is ignored by the parser.
        actionable_intents = {"user_directive", "system_alert"}

        if intent not in actionable_intents:
            return None

        # Build the initial goal
        raw_text = payload.get("raw_text", "Unknown directive context")

        task = Task(
            original_intent=f"Intent: {intent} | Context: {raw_text}",
            priority=event.priority,
            correlation_id=event.event_id,
        )

        logger.debug(f"Parsed new Action Task {task.task_id} from Event {event.event_id}")
        return task
