import asyncio
import httpx
from datetime import datetime


async def test_node_manager():
    async with httpx.AsyncClient() as client:
        print("1. Registering laptop node...")
        res = await client.post(
            "http://localhost:9000/swarm/register",
            json={
                "node_id": "laptop-m4",
                "host": "100.66.48.16",
                "port": 9200,
                "role": "code_embedding",
                "models": ["nomic-embed-code:latest"],
            },
        )
        print(f"Register Response: {res.json()}")

        print("\n2. Getting cluster topology...")
        res = await client.get("http://localhost:9000/swarm/nodes")
        print(f"Cluster Topology: {res.json()}")

        print("\n3. Sending heartbeat...")
        res = await client.post(
            "http://localhost:9000/swarm/heartbeat/laptop-m4",
            json={"gpu_load": 0.35, "queue_size": 1},
        )
        print(f"Heartbeat Response: {res.json()}")

        print("\n4. Getting updated cluster topology...")
        res = await client.get("http://localhost:9000/swarm/nodes")
        print(f"Updated Topology: {res.json()}")


if __name__ == "__main__":
    asyncio.run(test_node_manager())
