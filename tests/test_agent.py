import asyncio
import sys


async def main():
    from agents.system import SystemAgent

    print("Initializing Agent...")
    agent = SystemAgent()

    query = "Run a shell command to echo 'Hello World'"
    print(f"Sending query: {query}")

    try:
        await agent.execute({"sub_task_id": "manual_test", "query": query})
    except Exception as e:
        print(f"Error: {e}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
