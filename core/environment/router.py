import logging
import asyncio
from data.schemas import SystemEvent, EventType, LayerContext
from event_bus.event_bus import SystemEventBus
from core.environment.monitor import SystemMonitor

logger = logging.getLogger(__name__)


class EnvironmentRouter:
    """
    Layer 1 Router: The system's sensory input.
    Polls hardware and software telemetry and publishes it as OBSERVATION events.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.monitor = SystemMonitor(self.bus)
        self.layer_ctx = LayerContext(layer_number=1, module_name="EnvironmentMonitor")
        self._running = False

    async def start_polling(self, interval: int = 5):
        """Continuously poll system state and emit telemetry."""
        self._running = True
        logger.info("Environment Layer observation loop started.")
        while self._running:
            try:
                telemetry = await self.monitor.collect_metrics()
                event = SystemEvent(
                    event_type=EventType.OBSERVATION,
                    source_layer=self.layer_ctx,
                    priority=3,
                    payload=telemetry,
                )
                await self.bus.publish(event)
            except Exception as e:
                logger.error(f"Error in environment polling: {e}")
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False
