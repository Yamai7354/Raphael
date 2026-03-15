import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from event_bus.event_bus import SystemEventBus
from data.schemas import SystemEvent, EventType, LayerContext
from core.cognitive.router import CognitiveRouter
from swarm.router import SwarmRouter
from agents.router import AgentRouter


@pytest.mark.asyncio
async def test_layer_5_to_7_event_flow(monkeypatch):
    """
    Test the cognitive to execution pipeline:
    Layer 5 (Core Cognitive) -> Layer 6 (Swarm Manager) -> Layer 7 (Agent Swarm)
    """
    # Mock LLM calls so tests don't actually hit APIs
    monkeypatch.setattr(
        "core.cognitive.planner.ExecutionPlanner.generate_plan",
        MagicMock(return_value=["dummy_step"]),
    )
    monkeypatch.setattr(
        "core.cognitive.validator.ReasoningValidator.validate_plan",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        "core.cognitive.aggregator.ResultAggregator.compile_package",
        MagicMock(
            return_value={
                "plan_metadata": {"id": "test_plan_1"},
                "sequence": [{"sub_task_id": "sub_1", "required_capabilities": ["coding"]}],
            }
        ),
    )
    # Also mock Swarm Orchestrator and ModelRouter to easily route to a fake agent
    monkeypatch.setattr(
        "swarm.model_router.ModelRouter.find_agent",
        AsyncMock(return_value="agent_omega"),
    )

    # Mock the Agent base execute method so we don't run real code
    monkeypatch.setattr(
        "agents.coder.CodingAgent.execute",
        AsyncMock(return_value={"success": True, "result": "code written"}),
    )

    bus = SystemEventBus()

    cognitive = CognitiveRouter(bus)
    swarm = SwarmRouter(bus)
    agents = AgentRouter(bus)

    cognitive.register_subscriptions()
    swarm.register_subscriptions()
    agents.register_subscriptions()

    final_events = []

    async def task_completed_tracker(event: SystemEvent):
        final_events.append(event)

    bus.subscribe(EventType.SUBTASK_COMPLETED, task_completed_tracker)

    # Simulate an approved execution from Layer 4
    approved_event = SystemEvent(
        event_type=EventType.EXECUTION_APPROVED,
        source_layer=LayerContext(layer_number=4, module_name="SpineRouter"),
        priority=5,
        payload={"task_id": "task_123", "sub_tasks": []},
    )

    await bus.start()
    await bus.publish(approved_event)

    # Wait for the chain to complete
    # L4->L5 (PLAN_FINALIZED) -> L6 (AGENT_DISPATCH_REQUESTED) -> L7 (SUBTASK_COMPLETED)
    await asyncio.sleep(0.5)
    await bus.stop()

    assert len(final_events) > 0, "No SUBTASK_COMPLETED event retrieved. Chain broken."
    completed = final_events[0]
    assert completed.event_type == EventType.SUBTASK_COMPLETED
    assert completed.source_layer.layer_number == 7
    assert completed.payload["result"]["success"] is True
