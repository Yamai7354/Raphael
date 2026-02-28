import logging
import asyncio
from typing import Dict, Any

from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.cognitive.context import ContextBuilder
from src.raphael.cognitive.planner import ExecutionPlanner
from src.raphael.cognitive.validator import ReasoningValidator, LogicValidationError
from src.raphael.cognitive.aggregator import ResultAggregator

logger = logging.getLogger(__name__)


class CognitiveRouter:
    """
    The brain stem orchestration for Layer 5.
    Intercepts EXECUTION_APPROVED Tasks from Layer 4 Spine.
    Pipes them strictly through: Context -> Planner -> Validator -> Aggregator.
    Publishes the finale as a PLAN_FINALIZED event back to the bus.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.context = ContextBuilder()
        self.planner = ExecutionPlanner()
        self.validator = ReasoningValidator()
        self.aggregator = ResultAggregator()
        self.layer_ctx = LayerContext(layer_number=5, module_name="CognitiveRouter")

    def register_subscriptions(self):
        """Listen to tasks approved by the System Spine."""
        self.bus.subscribe(EventType.EXECUTION_APPROVED, self.handle_approved_execution)

    async def handle_approved_execution(self, event: SystemEvent):
        """
        Runs the cognitive pipeline on an approved raw Task.
        """
        # Ensure it came directly from Layer 4 Spine
        if event.source_layer.layer_number != 4:
            return

        payload = event.payload
        try:
            # 1. Enrich with Historical Memory
            enriched_payload = self.context.build_context(payload)

            # 2. Topologically sort dependencies into an Execution Plan
            raw_plan = self.planner.generate_plan(enriched_payload)

            # 3. Use the LLM logic critic to validate the plan assumptions
            self.validator.validate_plan(raw_plan)

            # 4. Package for the Agent Swarm
            final_package = self.aggregator.compile_package(raw_plan)

            # 5. Emit
            finalized_event = SystemEvent(
                event_type=EventType.PLAN_FINALIZED,  # Let's assume this exists now
                source_layer=self.layer_ctx,
                priority=event.priority,
                payload=final_package,
                correlation_id=event.event_id,
            )

            await self.bus.publish(finalized_event)
            logger.info(
                f"Layer 5 Cognition exported PLAN_FINALIZED for Goal {payload.get('task_id')}"
            )

        except LogicValidationError as e:
            # If the critic hates the plan, we bounce it to CRASH_REPORT
            logger.error(f"Reasoning Validation rejected Plan: {e}")
            crash_event = SystemEvent(
                event_type=EventType.CRASH_REPORT,
                source_layer=self.layer_ctx,
                priority=9,
                payload={"error": str(e), "task_id": payload.get("task_id")},
            )
            await self.bus.publish(crash_event)
        except Exception as e:
            logger.error(f"Cognitive Pipeline encountered a fatal error: {e}")
            crash_event = SystemEvent(
                event_type=EventType.CRASH_REPORT,
                source_layer=self.layer_ctx,
                priority=10,
                payload={"error": str(e), "task_id": payload.get("task_id")},
            )
            await self.bus.publish(crash_event)
