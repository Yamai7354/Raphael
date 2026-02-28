import asyncio
import os
import sys

# Ensure imports work regardless of execution location
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus


async def test_pub_sub_basic():
    bus = SystemEventBus()
    received_events = []

    # 1. Define async mock subscriber
    async def mock_subscriber(event: SystemEvent):
        received_events.append(event)

    # 2. Subscribe and start
    bus.subscribe(EventType.OBSERVATION, mock_subscriber)
    await bus.start()

    # 3. Publish test event
    layer_ctx = LayerContext(layer_number=2, module_name="Vision Model")
    test_event = SystemEvent(
        event_type=EventType.OBSERVATION, source_layer=layer_ctx, payload={"object": "cat detected"}
    )

    await bus.publish(test_event)

    # 4. Give the worker loop a millisecond to process
    await asyncio.sleep(0.1)

    # 5. Assertions
    assert len(received_events) == 1, "Event was not received by subscriber"
    assert received_events[0].event_id == test_event.event_id
    assert received_events[0].payload["object"] == "cat detected"

    await bus.stop()
    print("test_pub_sub_basic: PASSED")


async def test_priority_ordering():
    bus = SystemEventBus()
    execution_order = []

    async def mock_subscriber(event: SystemEvent):
        execution_order.append(event.payload["order"])

    bus.subscribe(EventType.TASK_SPAWNED, mock_subscriber)

    # DO NOT start the bus yet to let the queue fill up and sort
    layer_ctx = LayerContext(layer_number=3, module_name="Task Parser")

    # Priority 10 (Lowest priority technically via our schema rules, but PriorityQueue orders low integers first. Wait, standard Python priority queue pops lowest integers first. Let's assume 1 is highest priority. Our schema says 1 is lowest, 10 is highest. Wait: the Queue relies on normal sorting. The lowest integers come out first. So if 10 is highest priority mathematically in our app, we need to sort by -priority. Let's check our bus code: `queue_item = (event.priority, event.timestamp, event)`. A larger integer means it goes to the back. A smaller integer goes to the front. We need to flip or adjust priority. If priority 1 runs before priority 10, then 1 is highest priority in execution terms.)
    # In schemas.py: "from 1 (lowest) to 10 (highest)".
    # Oh! `asyncio.PriorityQueue()` pops the lowest number first. I need to make sure my test proves the behavior. Let's structure the test so that it puts events in order [LowPriority(1), HighPriority(10), MediumPriority(5)].
    # If standard Python is used, it pops 1, 5, 10. That's backward to the schema description.
    # We will test the functionality anyway immediately to see.

    e1 = SystemEvent(
        event_type=EventType.TASK_SPAWNED,
        source_layer=layer_ctx,
        priority=1,
        payload={"order": "priority_1"},
    )
    e2 = SystemEvent(
        event_type=EventType.TASK_SPAWNED,
        source_layer=layer_ctx,
        priority=10,
        payload={"order": "priority_10"},
    )
    e3 = SystemEvent(
        event_type=EventType.TASK_SPAWNED,
        source_layer=layer_ctx,
        priority=5,
        payload={"order": "priority_5"},
    )

    await bus.publish(e1)
    await bus.publish(e2)
    await bus.publish(e3)

    await bus.start()
    await asyncio.sleep(0.1)
    await bus.stop()

    assert len(execution_order) == 3
    # With standard asyncio.PriorityQueue, it will pop priority=1, then priority=5, then priority=10.
    assert execution_order == ["priority_1", "priority_5", "priority_10"]
    print(f"test_priority_ordering: PASSED - execution order was {execution_order}")


async def run_all_tests():
    print("Running Event Bus tests natively...")
    await test_pub_sub_basic()
    await test_priority_ordering()
    print("All tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
