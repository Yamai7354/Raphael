import logging
from typing import Dict, Any
from data.schemas import SystemEvent, EventType, LayerContext
from event_bus.event_bus import SystemEventBus
from core.understanding.parser import TaskParser
from core.understanding.decomposition import DecompositionEngine
from core.understanding.goal_manager import GoalManager

logger = logging.getLogger(__name__)


class UnderstandingRouter:
    """
    The orchestrator for Layer 3.
    Subscribes to perception observations, builds Tasks, decomposes them,
    stores them in the Goal Manager, and emits `TASK_SPAWNED` events for the execution swarm.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.parser = TaskParser()
        self.decomposer = DecompositionEngine()
        self.goal_manager = GoalManager()

        self.layer_ctx = LayerContext(layer_number=3, module_name="UnderstandingRouter")

    def register_subscriptions(self):
        """Listen to contextualized observations arriving from Layer 2 Perception."""
        self.bus.subscribe(EventType.OBSERVATION, self.handle_semantic_observation)

    async def handle_semantic_observation(self, event: SystemEvent):
        """
        Callback triggered when a semantic OBSERVATION arrives.
        Translates intent into Actionable Work Graphs.
        """
        # We specifically want events filtered and output by Layer 2 Perception
        if event.source_layer.layer_number != 2:
            return

        try:
            # 1. Parse into an actionable Goal (None if background noise)
            task = self.parser.parse_event(event)
            if not task:
                return  # Not actionable, ignore

            # 2. Decompose into multiple assignable sub-tasks
            decomposed_task = self.decomposer.decompose(task)

            # 3. Store in the active memory Goal Manager
            self.goal_manager.register_task(decomposed_task)

            # 4. Serialize task back to a generic SystemEvent payload
            # so the Swarm Manager (Layer 6) can blindly pick it up off the bus.
            payload = {
                "task_id": str(decomposed_task.task_id),
                "original_intent": decomposed_task.original_intent,
                "sub_tasks": [
                    {
                        "sub_task_id": str(st.sub_task_id),
                        "description": st.description,
                        "required_capabilities": st.required_capabilities,
                        "dependencies": [str(d) for d in st.dependencies],
                    }
                    for st in decomposed_task.sub_tasks
                ],
            }

            # 5. Emit the TASK_SPAWNED event
            spawn_event = SystemEvent(
                event_type=EventType.TASK_SPAWNED,
                source_layer=self.layer_ctx,
                priority=decomposed_task.priority,
                payload=payload,
                correlation_id=event.event_id,  # Trace back to the raw source event
            )

            await self.bus.publish(spawn_event)
            logger.debug(f"Task Understanding successfully built Goal {decomposed_task.task_id}")

        except Exception as e:
            logger.error(f"Task routing failed for observation {event.event_id}: {e}")
            crash_event = SystemEvent(
                event_type=EventType.CRASH_REPORT,
                source_layer=self.layer_ctx,
                priority=10,
                payload={"error": str(e), "failed_observation_id": str(event.event_id)},
            )
            await self.bus.publish(crash_event)
