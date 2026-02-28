import pytest
import asyncio
from core.cognitive.context import ContextBuilder
from core.cognitive.planner import ExecutionPlanner
from core.cognitive.validator import ReasoningValidator, LogicValidationError
from core.cognitive.aggregator import ResultAggregator
from core.cognitive.router import CognitiveRouter
from event_bus.event_bus import SystemEventBus
from data.schemas import SystemEvent, EventType, LayerContext


def test_context_builder():
    builder = ContextBuilder()

    # Test network context injection
    task1 = {"original_intent": "scan the network"}
    ctx1 = builder.build_context(task1)
    assert len(ctx1["memory_context"]) == 1
    assert "Graph Memory" in ctx1["memory_context"][0]

    # Generic context
    task2 = {"original_intent": "unknown objective"}
    ctx2 = builder.build_context(task2)
    assert "No relevant historical context" in ctx2["memory_context"][0]


def test_execution_planner():
    planner = ExecutionPlanner()

    # Create simple DAG subtasks where C depends on B which depends on A
    t_a = {"sub_task_id": "A", "dependencies": []}
    t_b = {"sub_task_id": "B", "dependencies": ["A"]}
    t_c = {"sub_task_id": "C", "dependencies": ["B"]}

    enriched_task = {
        "task_id": "123",
        "original_intent": "DAG Test",
        "sub_tasks": [t_b, t_c, t_a],  # Supplied out of order
    }

    plan = planner.generate_plan(enriched_task)
    seq = plan["execution_sequence"]

    # Planner should have topologically sorted them into A -> B -> C
    assert seq[0]["sub_task_id"] == "A"
    assert seq[1]["sub_task_id"] == "B"
    assert seq[2]["sub_task_id"] == "C"


def test_reasoning_validator():
    validator = ReasoningValidator()

    valid_plan = {"execution_sequence": [{"required_capabilities": ["bash", "filesystem"]}]}
    assert validator.validate_plan(valid_plan) is True

    invalid_plan = {"execution_sequence": [{"required_capabilities": ["create_universe"]}]}
    with pytest.raises(LogicValidationError):
        validator.validate_plan(invalid_plan)


async def test_cognitive_router_pipeline():
    bus = SystemEventBus()
    router = CognitiveRouter(bus)
    router.register_subscriptions()

    captured_plans = []
    captured_crashes = []

    # We must mock the event enum existence for tests if PLAN_FINALIZED isn't injected yet
    # Or rely on string bypasses if necessary. For now, assuming it will match our schema patch.

    async def trap_final(event: SystemEvent):
        if event.event_type == EventType.PLAN_FINALIZED:
            captured_plans.append(event)

    async def trap_crashes(event: SystemEvent):
        if event.event_type == EventType.CRASH_REPORT:
            captured_crashes.append(event)

    bus.subscribe(EventType.PLAN_FINALIZED, trap_final)
    bus.subscribe(EventType.CRASH_REPORT, trap_crashes)

    await bus.start()

    layer_4_ctx = LayerContext(layer_number=4, module_name="SpineRouter")

    # Send a valid plan approved by Layer 4
    valid_payload = {
        "task_id": "789",
        "original_intent": "Deploy code",
        "sub_tasks": [{"sub_task_id": "T1", "dependencies": [], "required_capabilities": ["bash"]}],
    }

    approved_event = SystemEvent(
        event_type=EventType.EXECUTION_APPROVED, source_layer=layer_4_ctx, payload=valid_payload
    )

    await bus.publish(approved_event)
    await asyncio.sleep(0.1)

    assert len(captured_plans) == 1
    assert captured_plans[0].payload["type"] == "EXECUTION_PLAN"
    assert len(captured_plans[0].payload["sequence"]) == 1

    # Send an invalid plan asking for impossible things
    invalid_payload = {
        "task_id": "999",
        "original_intent": "Destroy reality",
        "sub_tasks": [
            {"sub_task_id": "T2", "dependencies": [], "required_capabilities": ["magic"]}
        ],
    }

    bad_event = SystemEvent(
        event_type=EventType.EXECUTION_APPROVED, source_layer=layer_4_ctx, payload=invalid_payload
    )

    await bus.publish(bad_event)
    await asyncio.sleep(0.1)

    assert len(captured_crashes) == 1
    assert "unsupported capability" in captured_crashes[0].payload["error"]

    await bus.stop()


async def run_all_tests():
    print("Running Core Cognitive System Layer 5 tests natively...")

    test_context_builder()
    print("test_context_builder: PASSED")

    test_execution_planner()
    print("test_execution_planner: PASSED")

    test_reasoning_validator()
    print("test_reasoning_validator: PASSED")

    # A bit of monkeypatching strings if EventType schema isn't fully updated yet across files
    # but we'll try to run it organically.
    await test_cognitive_router_pipeline()
    print("test_cognitive_router_pipeline: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
