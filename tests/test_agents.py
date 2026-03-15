import pytest
import asyncio

from agents.system import SystemAgent
from agents.coder import CodingAgent
from agents.researcher import ResearchAgent
from agents.router import AgentRouter
from core.execution.tool_registry import ToolRegistry
from core.execution.tools import BashExecutionTool
from event_bus.event_bus import SystemEventBus
from data.schemas import SystemEvent, EventType, LayerContext


@pytest.mark.asyncio
async def test_agent_schemas():
    """Ensure all agents return the standard dict schema."""
    registry = ToolRegistry()
    registry.register_tool(BashExecutionTool())

    agents = [
        SystemAgent(tool_registry=registry),
        CodingAgent(),
        ResearchAgent(),
    ]
    payloads = [
        {"sub_task_id": "T_TEST", "command": "echo ok"},
        {"sub_task_id": "T_TEST"},
        {"sub_task_id": "T_TEST", "query": "summarize swarm status"},
    ]

    for agent, payload in zip(agents, payloads):
        res = await agent.execute(payload)
        assert "success" in res
        assert "logs" in res
        assert "output" in res
        assert res["success"] is True


@pytest.mark.asyncio
async def test_agent_router_dispatch_bridge():
    """Ensure the router maps the ID to class, runs execute, and fires COMPLETED."""
    bus = SystemEventBus()
    router = AgentRouter(bus)
    router.register_subscriptions()

    captured_completions = []

    async def trap_completion(event: SystemEvent):
        if event.event_type == EventType.SUBTASK_COMPLETED:
            captured_completions.append(event)

    bus.subscribe(EventType.SUBTASK_COMPLETED, trap_completion)
    await bus.start()

    layer_6_ctx = LayerContext(layer_number=6, module_name="SwarmOrchestrator")

    # Simulate an incoming dispatch order targeting agent_omega (our CodingAgent)
    dispatch_payload = {
        "plan_id": "pln_master",
        "sub_task_id": "T_LOGIC",
        "assigned_agent": "agent_omega",
        "capabilities": ["reasoning"],
    }

    dispatch_event = SystemEvent(
        event_type=EventType.AGENT_DISPATCH_REQUESTED,
        source_layer=layer_6_ctx,
        payload=dispatch_payload,
    )

    await bus.publish(dispatch_event)
    await asyncio.sleep(0.2)  # Give the mock agent's internal 0.1s sleep time to finish

    # Router should have caught it, routed it to omega, omega ran it, and fired this
    assert len(captured_completions) == 1
    assert captured_completions[0].payload["sub_task_id"] == "T_LOGIC"
    assert "result" in captured_completions[0].payload
    assert "code_diff" in captured_completions[0].payload["result"]["output"]  # Omega is a coder

    await bus.stop()


async def run_all_tests():
    print("Running Agent Swarm Layer 7 tests natively...")

    await test_agent_schemas()
    print("test_agent_schemas: PASSED")

    await test_agent_router_dispatch_bridge()
    print("test_agent_router_dispatch_bridge: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
