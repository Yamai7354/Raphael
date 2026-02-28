import psutil
import asyncio
from datetime import datetime, timezone
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus


class SystemMonitor:
    """
    Periodically collects internal telemetry (CPU, Memory, Activity) and
    emits it to the SystemEventBus for Layer 4 (Health) self-modeling.
    """

    def __init__(self, bus: SystemEventBus, poll_interval: float = 60.0):
        self.bus = bus
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._layer_context = LayerContext(layer_number=1, module_name="SystemMonitor")

    async def start(self):
        """Starts the background telemetry collection loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stops telemetry collection."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def collect_metrics(self) -> dict:
        """Gathers system and process telemetry."""
        process = psutil.Process()
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "process_cpu_percent": process.cpu_percent(interval=None),
            "memory_usage_mb": process.memory_info().rss / (1024 * 1024),
            "virtual_memory_percent": psutil.virtual_memory().percent,
            "active_threads": process.num_threads(),
        }

    async def emit_telemetry(self):
        """Builds and publishes the telemetry event."""
        metrics = await self.collect_metrics()

        event = SystemEvent(
            event_type=EventType.OBSERVATION,
            source_layer=self._layer_context,
            priority=8,  # Slightly lower priority than direct actions
            payload={"metric_type": "telemetry", "data": metrics},
        )

        await self.bus.publish(event)

    async def _monitor_loop(self):
        """Background loop executing the data pull."""
        while self._running:
            try:
                await self.emit_telemetry()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Issue emergency crash notification
                error_event = SystemEvent(
                    event_type=EventType.CRASH_REPORT,
                    source_layer=self._layer_context,
                    priority=10,  # Max priority
                    payload={"error": str(e), "component": "SystemMonitor"},
                )
                await self.bus.publish(error_event)
