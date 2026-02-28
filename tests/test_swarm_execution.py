import asyncio
import logging
import httpx
from event_bus.event_bus import SystemEventBus
from data.schemas import SystemEvent, EventType, LayerContext
from swarm.router import SwarmRouter
from agents.router import AgentRouter

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TestSwarm")
logging.getLogger("raphael").setLevel(logging.DEBUG)


async def run_swarm_test():
    # 1. Register node and send heartbeat to NodeManager
    async with httpx.AsyncClient() as client:
        reg_data = {
            "node_id": "node_mac",
            "host": "localhost",
            "port": 7000,
            "role": "research",
            "models": ["bash", "python", "filesystem"],
        }
        logger.info("Registering node_mac...")
        await client.post("http://localhost:9000/swarm/register", json=reg_data)

        logger.info("Sending heartbeat for node_mac...")
        await client.post(
            "http://localhost:9000/swarm/heartbeat/node_mac",
            json={"gpu_load": 0.1, "queue_size": 0},
        )

        # Verify node is ONLINE
        nodes_resp = await client.get("http://localhost:9000/swarm/nodes")
        logger.info(f"Current nodes in manager: {nodes_resp.json()}")

    # 2. Setup Swarm Components
    bus = SystemEventBus()
    await bus.start()

    swarm_router = SwarmRouter(bus)
    agent_router = AgentRouter(bus)

    swarm_router.register_subscriptions()
    agent_router.register_subscriptions()

    # 3. Create and Publish Plan
    execution_plan = {
        "plan_metadata": {"id": "test_plan_final"},
        "sequence": [
            {
                "sub_task_id": "st_01",
                "description": "Verify environment.",
                "required_capabilities": ["bash"],
                "command": "ls -la",
                "dependencies": [],
            },
            {
                "sub_task_id": "st_02",
                "description": "Execute logic.",
                "required_capabilities": ["python"],
                "command": "print('Python Command Execution SUCCESS')",  # For CodingAgent fallback or similar
                "code_content": "print('Execution SUCCESS')",
                "dependencies": ["st_01"],
            },
        ],
    }

    plan_event = SystemEvent(
        event_type=EventType.PLAN_FINALIZED,
        source_layer=LayerContext(layer_number=5, module_name="TestPlanSource"),
        priority=5,
        payload=execution_plan,
    )

    completed_tasks = []

    async def on_completion(event: SystemEvent):
        st_id = event.payload.get("sub_task_id")
        logger.info(f"CAPTURED COMPLETION: {st_id}")
        completed_tasks.append(st_id)

    bus.subscribe(EventType.SUBTASK_COMPLETED, on_completion)

    logger.info("Publishing test plan...")
    await bus.publish(plan_event)

    # 4. Wait for results
    for i in range(40):
        if len(completed_tasks) == 2:
            break
        await asyncio.sleep(0.5)

    if "st_01" in completed_tasks and "st_02" in completed_tasks:
        logger.info("SUCCESS: All tasks in the plan were dispatched and completed.")
    else:
        logger.error(
            f"FAILURE: Expected 2 completions, got {len(completed_tasks)}: {completed_tasks}"
        )

    await bus.stop()


if __name__ == "__main__":
    asyncio.run(run_swarm_test())
