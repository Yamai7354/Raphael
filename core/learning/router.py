import logging
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.learning.policy_engine import PolicyManager

logger = logging.getLogger(__name__)


class LearningRouter:
    """
    Layer 10 Router: The self-improvement loop.
    Subscribes to SUBTASK_COMPLETED and REWARD_SIGNAL to refine system policies.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.policy_engine = PolicyManager(initial_policy={})
        self.layer_ctx = LayerContext(layer_number=10, module_name="LearningEngine")

    def register_subscriptions(self):
        self.bus.subscribe(EventType.SUBTASK_COMPLETED, self.handle_achievement)
        self.bus.subscribe(EventType.REWARD_SIGNAL, self.handle_feedback)

    async def handle_achievement(self, event: SystemEvent):
        """Learns from successful or failed task completions."""
        result = event.payload.get("result", {})
        if result.get("success"):
            logger.info(
                f"Layer 10 reinforcing successful patterns for task {event.payload.get('task_id')}"
            )
            # Policy updates would happen here
            self.policy_engine.update_from_success(event.payload)
        else:
            logger.warning(f"Layer 10 analyzing failure in task {event.payload.get('task_id')}")
            self.policy_engine.update_from_failure(event.payload)

    async def handle_feedback(self, event: SystemEvent):
        """Processes explicit reward signals from Layer 9 (Evaluation)."""
        score = event.payload.get("score", 0)
        logger.info(f"Layer 10 processing reward signal: {score}")
        self.policy_engine.process_reward(score, event.payload)
