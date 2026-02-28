import asyncio
import logging
import signal
import os
import json
import time
from typing import Any
from event_bus.event_bus import SystemEventBus
from core.civilization.router import CivilizationRouter
from core.civilization.society import SocietyManager
from core.civilization.infrastructure import InfrastructureManager
from core.civilization.knowledge import KnowledgeManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("CivilizationController")


class CivilizationController:
    """
    The central heart of the Raphael Swarm.
    Orchestrates the System Event Bus and triggers the rituals of civilization.
    """

    def __init__(self, stats_file: str, initial_priority: list[str] | None = None):
        self.bus = SystemEventBus()
        self.router = CivilizationRouter(self.bus)
        self.society = SocietyManager()
        self.infrastructure = InfrastructureManager()
        self.knowledge = KnowledgeManager()
        self.stats_file = stats_file
        self.last_wake_time = int(time.time())
        self.last_ritual_time = "--:--:--"
        self._running = False

    def _update_dashboard(self, status: str, council_val: str):
        """Writes civilization state to the shared dashboard stats file."""
        try:
            data = {}
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r") as f:
                    data = json.load(f)

            data["civilization"] = {
                "status": status,
                "council": council_val,
                "last_ritual": self.last_ritual_time,
                "timestamp": time.strftime("%H:%M:%S"),
            }

            with open(self.stats_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Dashboard Update Error (Civ): {e}")

    async def start(self):
        """Starts the event bus and the civilization rituals."""
        logger.info("Initializing Raphael Civilization Controller...")

        # Start the Bus
        await self.bus.start()

        self._running = True

        # Start Civilization Rituals in the background
        ritual_tasks = [
            asyncio.create_task(
                self.router.stewardship_ritual(interval=60)
            ),  # Every minute for demonstration
            asyncio.create_task(
                self.router.reporting_ritual(interval=300)
            ),  # Every 5 minutes for demonstration
            asyncio.create_task(self._society_pulse(interval=30)),  # Swarm health check
            asyncio.create_task(self._infrastructure_pulse(interval=120)),  # Resource evaluation
        ]

        logger.info("Civilization rituals active. Raphael is now 'Living'.")

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            self.stop()
            for task in ritual_tasks:
                task.cancel()

    def stop(self):
        """Stops all processes."""
        logger.info("Stopping Civilization Controller...")
        self._running = False
        self.router.stop()
        asyncio.create_task(self.bus.stop())

    async def _society_pulse(self, interval: int):
        """Regularly checks swarm health and balances workload."""
        while self._running:
            # In a real system, we'd gather active agent stats from the bus or memory
            # For this MVP, we simulate nominal state
            mock_agents = [
                {"agent_id": "voice_orchestrator", "current_tasks": 1, "status": "active"},
                {"agent_id": "graph_optimizer", "current_tasks": 0, "status": "active"},
            ]
            balance_result = self.society.balance_workload(mock_agents)
            if balance_result["status"] == "rebalanced":
                logger.info(f"Society rebalanced: {balance_result['rebalance_commands']}")

            self.last_ritual_time = time.strftime("%H:%M:%S")
            self._update_dashboard("Balancing", "Nominal")
            await asyncio.sleep(interval)

    async def _infrastructure_pulse(self, interval: int):
        """Regularly evaluates if system needs evolution."""
        while self._running:
            # Simulate historical utilization
            mock_usage = [0.4, 0.5, 0.45, 0.6, 0.55]
            evo_needs = self.infrastructure.evaluate_evolution_needs(mock_usage)
            if evo_needs["action"] != "none":
                logger.info(f"Infrastructure evolution needed: {evo_needs['reason']}")

            await asyncio.sleep(interval)


if __name__ == "__main__":
    stats_path = os.path.join(os.getcwd(), "swarm-dashboard", "public", "stats.json")
    controller = CivilizationController(stats_file=stats_path)

    # Handle termination signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, controller.stop)

    try:
        asyncio.run(controller.start())
    except KeyboardInterrupt:
        pass
