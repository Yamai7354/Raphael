import asyncio
import nats


async def connect_to_nats():
    """
    Initializes connection to the NATS message broker.
    NATS is ideal for the System Event Bus due to its high throughput and cloud-native architecture.
    """
    # Connect to NATS locally (assumes a running NATS server)
    try:
        nc = await nats.connect("nats://localhost:4222")
        print("Connected to NATS")
        return nc
    except Exception as e:
        print(f"Failed to connect to NATS: {e}")
        return None


# For JetStream (persistent queues, useful for TaskManager async jobs)
async def setup_jetstream(nc):
    js = nc.jetstream()
    # await js.add_stream(name="swarm_tasks", subjects=["tasks.*"])
    return js
