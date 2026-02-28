import pytest
import asyncio
from src.raphael.swarm.scheduler import TaskScheduler
from src.raphael.swarm.model_router import ModelRouter
from src.raphael.swarm.orchestrator import SwarmOrchestrator
from src.raphael.swarm.router import SwarmRouter
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext


def test_task_scheduler_dependency_chain():
    scheduler = TaskScheduler()

    # Simulating a compiled payload from Layer 5
    mock_payload = {
        "plan_metadata": {"id": "plan_777"},
        "sequence": [
            {"sub_task_id": "T1", "dependencies": []},
            {"sub_task_id": "T2", "dependencies": ["T1"]},  # Blocked by T1
        ],
    }

    scheduler.load_plan(mock_payload)
    ready = scheduler.get_ready_tasks("plan_777")

    # Only T1 should be ready
    assert len(ready) == 1
    assert ready[0]["sub_task_id"] == "T1"

    # Mark T1 as shifted to running, then completed
    scheduler.mark_running("plan_777", "T1")
    scheduler.mark_completed("plan_777", "T1")

    # Now T2 should be unlocked
    ready_round_two = scheduler.get_ready_tasks("plan_777")
    assert len(ready_round_two) == 1
    assert ready_round_two[0]["sub_task_id"] == "T2"


def test_model_router_capability_matching():
    router = ModelRouter()

    # Should match node_mac for bash
    assert router.find_agent(["bash"]) == "node_mac"

    # Should match omega for reasoning
    assert router.find_agent(["reasoning"]) == "agent_omega"

    # Test strict subset enforcement
    assert (
        router.find_agent(["bash", "gguf_inference"]) is None
    )  # No single agent has both in our mock


async def test_swarm_router_dispatch_pipeline():
    bus = SystemEventBus()
    router = SwarmRouter(bus)
    router.register_subscriptions()

    captured_dispatches = []

    async def trap_dispatch(event: SystemEvent):
        if event.event_type == EventType.AGENT_DISPATCH_REQUESTED:
            captured_dispatches.append(event)

    bus.subscribe(EventType.AGENT_DISPATCH_REQUESTED, trap_dispatch)

    await bus.start()

    layer_5_ctx = LayerContext(layer_number=5, module_name="CognitiveRouter")

    # Drop a Finalized Plan on the Bus
    plan_payload = {
        "plan_metadata": {"id": "pln_123"},
        "sequence": [
            {"sub_task_id": "T_START", "dependencies": [], "required_capabilities": ["bash"]},
            {
                "sub_task_id": "T_NEXT",
                "dependencies": ["T_START"],
                "required_capabilities": ["python"],
            },
        ],
    }

    plan_event = SystemEvent(
        event_type=EventType.PLAN_FINALIZED, source_layer=layer_5_ctx, payload=plan_payload
    )

    await bus.publish(plan_event)
    await asyncio.sleep(0.1)

    # T_START should have been dynamically dispatched
    assert len(captured_dispatches) == 1
    assert captured_dispatches[0].payload["sub_task_id"] == "T_START"

    # Simulate Execution Layer returning it
    layer_8_ctx = LayerContext(layer_number=8, module_name="ExecutionAgent")
    complete_event = SystemEvent(
        event_type=EventType.SUBTASK_COMPLETED,
        source_layer=layer_8_ctx,
        payload={"plan_id": "pln_123", "sub_task_id": "T_START"},
    )

    await bus.publish(complete_event)
    await asyncio.sleep(0.1)

    # T_NEXT should now have automatically fired
    assert len(captured_dispatches) == 2
    assert captured_dispatches[1].payload["sub_task_id"] == "T_NEXT"

    await bus.stop()


async def run_all_tests():
    print("Running Swarm Manager Layer 6 tests natively...")

    test_task_scheduler_dependency_chain()
    print("test_task_scheduler_dependency_chain: PASSED")

    test_model_router_capability_matching()
    print("test_model_router_capability_matching: PASSED")

    await test_swarm_router_dispatch_pipeline()
    print("test_swarm_router_dispatch_pipeline: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
