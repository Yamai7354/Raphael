import pytest
import asyncio
from unittest.mock import MagicMock

from event_bus.event_bus import SystemEventBus
from data.schemas import SystemEvent, EventType, LayerContext
from core.perception.router import PerceptionRouter
from core.understanding.router import UnderstandingRouter
from spine.router import SpineRouter


@pytest.mark.asyncio
async def test_layer_1_to_4_event_flow():
    """
    Test the full semantic routing pipeline:
    Layer 1 (Raw Input) -> Layer 2 (Perception) -> Layer 3 (Understanding) -> Layer 4 (Spine Approval)
    """
    # Use a real event bus for true integration routing
    bus = SystemEventBus()

    # Instantiate routers
    perception = PerceptionRouter(bus)
    understanding = UnderstandingRouter(bus)
    spine = SpineRouter(bus)

    # Register subscriptions
    perception.register_subscriptions()
    understanding.register_subscriptions()
    spine.register_subscriptions()

    # We need a tracker to capture the final output of Layer 4
    final_events = []

    async def execution_approved_tracker(event: SystemEvent):
        final_events.append(event)

    bus.subscribe(EventType.EXECUTION_APPROVED, execution_approved_tracker)

    # 1. Create a dummy raw input from Layer 1
    raw_input = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=LayerContext(layer_number=1, module_name="UserInterface"),
        priority=5,
        payload={"text": "user_command: Please write a simple python script."},
    )

    # Execute the flow
    await bus.start()
    await bus.publish(raw_input)

    # Wait a small tick to ensure all async callbacks in the event bus resolve
    await asyncio.sleep(0.5)

    await bus.stop()

    # Assert that the event made it all the way to Layer 4 and was approved
    assert len(final_events) > 0, "No EXECUTION_APPROVED event was emitted."

    approved_event = final_events[0]
    assert approved_event.event_type == EventType.EXECUTION_APPROVED
    assert approved_event.source_layer.layer_number == 4

    # Check payload has task info injected by Layer 3 (Understanding)
    assert "task_id" in approved_event.payload
    assert "sub_tasks" in approved_event.payload

    # Subtasks should exist
    assert len(approved_event.payload["sub_tasks"]) > 0
