import logging
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.evaluation.qa import QualityAssessor

logger = logging.getLogger(__name__)


class EvaluationRouter:
    """Layer 9 Router: Critic & Quality Assessment."""

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.qa = QualityAssessor()
        self.layer_ctx = LayerContext(layer_number=9, module_name="EvaluationTesting")

    def register_subscriptions(self):
        # Listens for task completions to evaluate
        self.bus.subscribe(EventType.SUBTASK_COMPLETED, self.evaluate_outcome)

    async def evaluate_outcome(self, event: SystemEvent):
        """Runs QA on completed subtasks and emits REWARD_SIGNAL."""
        score = self.qa.evaluate(event.payload)
        reward_event = SystemEvent(
            event_type=EventType.REWARD_SIGNAL,
            source_layer=self.layer_ctx,
            priority=event.priority,
            payload={"task_id": event.payload.get("task_id"), "score": score},
        )
        await self.bus.publish(reward_event)
