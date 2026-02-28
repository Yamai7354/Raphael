import pytest
import asyncio
from typing import Optional
from src.raphael.understanding.schemas import Task, SubTask, TaskStatus
from src.raphael.understanding.parser import TaskParser
from src.raphael.understanding.decomposition import DecompositionEngine
from src.raphael.understanding.goal_manager import GoalManager
from src.raphael.understanding.router import UnderstandingRouter
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext


def test_task_schemas_and_parser():
    parser = TaskParser()
    layer_2_ctx = LayerContext(layer_number=2, module_name="PerceptionRouter")

    # 1. Test background noise dropped
    noise_event = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=layer_2_ctx,
        payload={"intent": "background_info", "raw_text": "CPU is 40%"},
    )
    assert parser.parse_event(noise_event) is None

    # 2. Test actionable user directive parses
    action_event = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=layer_2_ctx,
        payload={"intent": "user_directive", "raw_text": "run a network scan"},
    )
    task: Optional[Task] = parser.parse_event(action_event)
    assert task is not None
    assert "run a network scan" in task.original_intent


def test_task_decomposition():
    decomposer = DecompositionEngine()

    task_deploy = Task(original_intent="Deploy the web server")
    decomposed_t1 = decomposer.decompose(task_deploy)
    # The heuristic in our stub returns 2 tasks for 'deploy'
    assert len(decomposed_t1.sub_tasks) == 2
    assert decomposed_t1.sub_tasks[0].required_capabilities == ["filesystem"]
    assert decomposed_t1.sub_tasks[1].required_capabilities == ["bash"]

    # The generic branch returns 1
    task_generic = Task(original_intent="tell me a joke")
    decomposed_t2 = decomposer.decompose(task_generic)
    assert len(decomposed_t2.sub_tasks) == 1
    assert "general_agent" in decomposed_t2.sub_tasks[0].required_capabilities


def test_goal_manager_status_updates():
    manager = GoalManager()
    decomposer = DecompositionEngine()

    task = decomposer.decompose(Task(original_intent="Deploy code"))
    manager.register_task(task)

    st1 = task.sub_tasks[0]
    st2 = task.sub_tasks[1]

    # Partial complete
    manager.update_subtask_status(task.task_id, st1.sub_task_id, TaskStatus.COMPLETED)
    assert manager.active_tasks[task.task_id].status == TaskStatus.PENDING

    # Full complete triggers parent cascade
    manager.update_subtask_status(task.task_id, st2.sub_task_id, TaskStatus.COMPLETED)
    assert manager.active_tasks[task.task_id].status == TaskStatus.COMPLETED


async def test_understanding_router_pipeline():
    bus = SystemEventBus()
    router = UnderstandingRouter(bus)
    router.register_subscriptions()

    captured_spawn_events = []

    async def trap_spawn_events(event: SystemEvent):
        if event.event_type == EventType.TASK_SPAWNED:
            captured_spawn_events.append(event)

    bus.subscribe(EventType.TASK_SPAWNED, trap_spawn_events)
    await bus.start()

    # Simulate an incoming semantic OBSERVATION from Layer 2
    layer_2_ctx = LayerContext(layer_number=2, module_name="PerceptionRouter")
    semantic_event = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=layer_2_ctx,
        payload={"intent": "system_alert", "raw_text": "Error: Kernel Exception!"},
    )

    await bus.publish(semantic_event)
    await asyncio.sleep(0.1)

    # Assertions
    assert len(captured_spawn_events) == 1
    spawn_event = captured_spawn_events[0]

    assert spawn_event.source_layer.layer_number == 3
    assert spawn_event.event_type == EventType.TASK_SPAWNED

    # Verify the payload was converted back from a typed Task to a dict successfully
    payload = spawn_event.payload
    assert "task_id" in payload
    assert len(payload["sub_tasks"]) == 2

    assert payload["sub_tasks"][0]["required_capabilities"] == ["read_logs"]

    await bus.stop()


async def run_all_tests():
    print("Running Task Understanding Layer 3 tests natively...")

    test_task_schemas_and_parser()
    print("test_task_schemas_and_parser: PASSED")

    test_task_decomposition()
    print("test_task_decomposition: PASSED")

    test_goal_manager_status_updates()
    print("test_goal_manager_status_updates: PASSED")

    await test_understanding_router_pipeline()
    print("test_understanding_router_pipeline: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
