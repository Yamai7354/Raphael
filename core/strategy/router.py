import logging
import asyncio
from uuid import uuid4
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.strategy.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


class StrategyRouter:
    """
    Layer 12 Router: Autonomous Goal Generation.
    Monitors system state and spawns background tasks to ensure continuous improvement.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.engine = StrategyEngine()
        self.layer_ctx = LayerContext(layer_number=12, module_name="StrategicIntelligence")
        self._running = False

    def register_subscriptions(self):
        # Layer 12 also listens to high-level system health
        self.bus.subscribe(EventType.OBSERVATION, self.evaluate_strategic_needs)

    async def evaluate_strategic_needs(self, event: SystemEvent):
        """Analyzes environment observations to see if background research is needed."""
        # Only process telemetry from SystemMonitor
        if event.source_layer.module_name != "EnvironmentMonitor":
            return

        # Logic to decide if an autonomous task should spawn
        # e.g., if CPU is low and no user tasks are active, spawn Research
        pass

    async def autonomous_loop(self, interval: int = 60):
        """Periodically evaluates long-term goals."""
        self._running = True
        logger.info("Strategy Layer autonomous goal loop started.")
        while self._running:
            goal = self.engine.generate_autonomous_goal()
            if goal:
                logger.info(f"Layer 12 spawning autonomous goal: {goal['title']}")
                task_event = SystemEvent(
                    event_id=uuid4(),
                    event_type=EventType.TASK_SPAWNED,
                    source_layer=self.layer_ctx,
                    priority=2,  # Lower priority than user tasks
                    payload=goal,
                )
                await self.bus.publish(task_event)
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False
