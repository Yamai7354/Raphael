import pytest
import asyncio
from spine.resources import ResourceManager
from spine.safety import SafetyGate, SecurityViolation
from spine.identity import PermissionsValidator, PermissionDenied
from spine.health import HealthMonitor
from spine.router import SpineRouter
from event_bus.event_bus import SystemEventBus
from data.schemas import SystemEvent, EventType, LayerContext


def test_resource_manager_queueing():
    rm = ResourceManager(max_slots=2)
    # CPU is fine, but slots exhaust

    assert rm.can_schedule_task({"task": "A"}) is True
    rm.allocate({"task": "A"})

    assert rm.can_schedule_task({"task": "B"}) is True
    rm.allocate({"task": "B"})

    # 3rd task should overload
    assert rm.can_schedule_task({"task": "C"}) is False
    rm.queue_task({"task_id": "C"})
    assert len(rm.queued_tasks) == 1

    rm.free_slot()
    assert rm.can_schedule_task(rm.get_queued_task()) is True


def test_safety_gate_violations():
    gate = SafetyGate()

    # Safe payload
    assert gate.evaluate_payload({"command": "ls -la"}) is True

    # Malicious payload buried via recursion
    malicious_payload = {
        "sub_tasks": [{"command": "echo hello"}, {"payload": {"cmd": "sudo rm -rf /"}}]
    }
    with pytest.raises(SecurityViolation):
        gate.evaluate_payload(malicious_payload)


def test_permissions_validator():
    perms = PermissionsValidator()

    # Valid scraper doing scraper things
    assert perms.evaluate_request("scraper_agent", ["network_read"]) is True

    # Unverified capability attempt
    with pytest.raises(PermissionDenied):
        perms.evaluate_request("scraper_agent", ["bash"])

    # User gets everything
    assert perms.evaluate_request("user", ["DROP TABLE"]) is True

    # Unknown Identity
    with pytest.raises(PermissionDenied):
        perms.evaluate_request("ghost_agent", ["read"])


async def test_spine_router_pipeline():
    bus = SystemEventBus()
    router = SpineRouter(bus)
    router.register_subscriptions()

    captured_approvals = []

    async def trap_approvals(event: SystemEvent):
        if event.event_type == EventType.EXECUTION_APPROVED:
            captured_approvals.append(event)

    bus.subscribe(EventType.EXECUTION_APPROVED, trap_approvals)
    await bus.start()

    # Generate a Mock Task coming from Layer 3
    layer_3_ctx = LayerContext(layer_number=3, module_name="UnderstandingRouter")

    clean_task = SystemEvent(
        event_type=EventType.TASK_SPAWNED,
        source_layer=layer_3_ctx,
        payload={
            "task_id": "123",
            "assigned_role": "user",
            "sub_tasks": [{"required_capabilities": ["bash"]}],
        },
    )

    # This should pass Safety, Identity, and Resource tests
    await bus.publish(clean_task)
    await asyncio.sleep(0.1)

    assert len(captured_approvals) == 1
    assert captured_approvals[0].payload["task_id"] == "123"

    await bus.stop()


async def run_all_tests():
    print("Running System Spine Layer 4 tests natively...")

    test_resource_manager_queueing()
    print("test_resource_manager_queueing: PASSED")

    test_safety_gate_violations()
    print("test_safety_gate_violations: PASSED")

    test_permissions_validator()
    print("test_permissions_validator: PASSED")

    await test_spine_router_pipeline()
    print("test_spine_router_pipeline: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
