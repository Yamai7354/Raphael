import asyncio
import sys
from agent import AssistantAgent


async def main():
    print("Initializing Agent...")
    agent = AssistantAgent()

    print("Connecting to Client...")
    await agent.client.connect()

    query = "Run a shell command to echo 'Hello World'"
    print(f"Sending query: {query}")

    try:
        await agent.process_request(query)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await agent.client.disconnect()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
