import asyncio
import logging
import sys
import os

# Ensure the project root is in PYTHONPATH
project_root = "/Users/yamai/ai/Raphael"
sys.path.append(project_root)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

from agents.caretaker.controller import CaretakerController


async def main():
    print("--- Swarm Caretaker Suite (SCS) Test Run ---")

    # Initialize the Controller
    controller = CaretakerController()

    # Execute the Caretaking Cycle
    # We pass an empty payload as the controller handles its own sub-tasks
    result = await controller.execute({})

    print("\n--- Cycle Result ---")
    print(f"Status: {result['status']}")
    print(f"Report Location: {result['report']}")
    print(f"Suggestions Found: {result['suggestion_count']}")

    # Verify report existence
    if os.path.exists(result["report"]):
        print("\n--- Report Preview (Top 5 lines) ---")
        with open(result["report"], "r") as f:
            for i in range(5):
                print(f.readline().strip())
    else:
        print("\nERROR: Report was not generated.")


if __name__ == "__main__":
    asyncio.run(main())
