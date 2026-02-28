import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from event_bus.event_bus import SystemEventBus
# Note: SystemEvent, EventType, LayerContext removed if truly unused in main.py,
# but they might be used in type hints if I missed them.
# Checking... they don't seem used in the provided snippet.

# Import Routers
from core.environment.router import EnvironmentRouter
from core.perception.router import PerceptionRouter
from core.understanding.router import UnderstandingRouter
from spine.router import SpineRouter
from core.cognitive.router import CognitiveRouter
from swarm.router import SwarmRouter
from agents.router import AgentRouter
from core.execution.router import ExecutionRouter
from core.evaluation.router import EvaluationRouter
from core.learning.router import LearningRouter
from core.research.router import ResearchRouter
from core.strategy.router import StrategyRouter
from core.civilization.router import CivilizationRouter

# Import Interfaces
from interfaces.api.api_interface import run_api
from ai_router.main import app as ai_router_app
import uvicorn

# Configure Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RaphaelRuntime")


class RaphaelOS:
    """
    The main runtime for Raphael OS.
    Orchestrates the lifecycle of all 13 architectural layers.
    """

    def __init__(self):
        self.bus = SystemEventBus()
        self.routers = {}
        self._stop_event = asyncio.Event()

    async def boot(self):
        logger.info("Initializing Raphael OS Architecture...")

        # 1. Instantiate Routers
        self.routers["L1"] = EnvironmentRouter(self.bus)
        self.routers["L2"] = PerceptionRouter(self.bus)
        self.routers["L3"] = UnderstandingRouter(self.bus)
        self.routers["L4"] = SpineRouter(self.bus)
        self.routers["L5"] = CognitiveRouter(self.bus)
        self.routers["L6"] = SwarmRouter(self.bus)
        self.routers["L7"] = AgentRouter(self.bus)
        self.routers["L8"] = ExecutionRouter(self.bus)
        self.routers["L9"] = EvaluationRouter(self.bus)
        self.routers["L10"] = LearningRouter(self.bus)
        self.routers["L11"] = ResearchRouter(self.bus)
        self.routers["L12"] = StrategyRouter(self.bus)
        self.routers["L13"] = CivilizationRouter(self.bus)

        # 2. Register Subscriptions
        for name, router in self.routers.items():
            if hasattr(router, "register_subscriptions"):
                router.register_subscriptions()
                logger.debug(f"Registered subscriptions for {name}")

        # 3. Start Event Bus
        await self.bus.start()

        # 4. Start API Server in a separate thread/task
        logger.info("Initializing API Interface on port 8001...")
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, run_api, self.bus, 8001)

        # 4.5 Start AI Router Server (FastAPI) in a separate thread
        logger.info("Initializing Node Manager (AI Router) on port 9000...")

        def run_ai_router():
            uvicorn.run(ai_router_app, host="0.0.0.0", port=9000, log_level="warning")

        loop.run_in_executor(None, run_ai_router)

        # 5. Start Autonomous Background Loops
        tasks = []
        if hasattr(self.routers["L1"], "start_polling"):
            tasks.append(asyncio.create_task(self.routers["L1"].start_polling(interval=10)))

        if hasattr(self.routers["L12"], "autonomous_loop"):
            tasks.append(asyncio.create_task(self.routers["L12"].autonomous_loop(interval=60)))

        if hasattr(self.routers["L13"], "stewardship_ritual"):
            tasks.append(asyncio.create_task(self.routers["L13"].stewardship_ritual(interval=300)))

        if hasattr(self.routers["L13"], "reporting_ritual"):
            tasks.append(asyncio.create_task(self.routers["L13"].reporting_ritual(interval=3600)))

        logger.info("✅ Raphael OS is fully operational and autonomous.")

        # Wait for shutdown signal
        await self._stop_event.wait()

        # Cleanup
        logger.info("Shutting down Raphael OS...")
        for task in tasks:
            task.cancel()
        await self.bus.stop()

    def shutdown(self, *args):
        self._stop_event.set()


async def main():
    system = RaphaelOS()

    # Handle OS signals for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, system.shutdown)

    await system.boot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
