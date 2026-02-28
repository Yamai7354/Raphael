import logging

from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.swarm.orchestrator import SwarmOrchestrator

logger = logging.getLogger(__name__)


class SwarmRouter:
    """
    Connects the Layer 6 Swarm Manager logic to the global Event Bus.
    Listens for PLAN_FINALIZED from Layer 5 Cognition.
    Also listens for SUBTASK_COMPLETED from Layer 8 Execution, to continue the queue.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.orchestrator = SwarmOrchestrator()
        self.layer_ctx = LayerContext(layer_number=6, module_name="SwarmRouter")

    def register_subscriptions(self):
        """Listen to incoming plans and feedback from execution."""
        self.bus.subscribe(EventType.PLAN_FINALIZED, self.handle_new_plan)
        self.bus.subscribe(EventType.SUBTASK_COMPLETED, self.handle_task_completion)

    async def _emit_dispatch_batch(self, dispatch_list: list):
        """Fires an Event onto the bus for every assigned task."""
        for assignment in dispatch_list:
            dispatch_event = SystemEvent(
                event_type=EventType.AGENT_DISPATCH_REQUESTED,
                source_layer=self.layer_ctx,
                priority=5,
                payload=assignment,
            )
            await self.bus.publish(dispatch_event)
            logger.info(
                f"Layer 6 dispatched {assignment.get('sub_task_id')} to {assignment.get('assigned_agent')}"
            )

    async def handle_new_plan(self, event: SystemEvent):
        """
        Ingests a finalized plan from Layer 5.
        Instantly attempts to start execution of the initial tasks.
        """
        payload = event.payload
        plan_id = payload.get("plan_metadata", {}).get("id")

        # Load the plan map
        self.orchestrator.ingest_plan(payload)

        # Pull any steps that map to 0 dependencies immediately
        dispatch_list = await self.orchestrator.process_queue(plan_id)
        if dispatch_list:
            await self._emit_dispatch_batch(dispatch_list)

    async def handle_task_completion(self, event: SystemEvent):
        """
        Feedback loop. When an agent reports 'done' from down the stack,
        we unblock the topological chain and dispatch the next tasks.
        """
        payload = event.payload
        plan_id = payload.get("plan_id")
        sub_task_id = payload.get("sub_task_id")

        if not plan_id or not sub_task_id:
            return

        # Signal the orchestrator
        self.orchestrator.handle_completion(plan_id, sub_task_id)
        logger.debug(f"Swarm Manager logged completion of {sub_task_id}")

        # See if anything new was unblocked
        dispatch_list = await self.orchestrator.process_queue(plan_id)
        if dispatch_list:
            await self._emit_dispatch_batch(dispatch_list)
