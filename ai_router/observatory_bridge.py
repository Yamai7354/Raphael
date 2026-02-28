"""
Observatory Event Bridge

Bridges the network_observatory's in-process EventBus to the
agent_ecosystem's Redis EventBus, forwarding sensor readings,
threat detections, and analysis events.
"""

import asyncio
import json
import logging
from typing import Optional, Any

logger = logging.getLogger("ai_router.observatory_bridge")

# Topic mapping: observatory local topic → Redis topic
TOPIC_MAP = {
    "sensor.reading": "observatory.sensor.reading",
    "sensor.error": "observatory.sensor.error",
    "threat.detected": "observatory.threat.detected",
    "analysis.complete": "observatory.analysis.complete",
    "analysis.finding": "observatory.analysis.finding",
    "command.executed": "observatory.command.executed",
    "command.rejected": "observatory.command.rejected",
    "circuit_breaker.opened": "observatory.circuit_breaker.opened",
    "circuit_breaker.closed": "observatory.circuit_breaker.closed",
}


class ObservatoryBridge:
    """
    Subscribes to the observatory's in-process EventBus and
    forwards events to the ecosystem's Redis EventBus.
    """

    def __init__(self):
        self._observatory_bus = None
        self._redis_bus = None
        self._running = False

    async def start(self, redis_bus: Any) -> None:
        """
        Connect to both event buses.

        Args:
            redis_bus: The ecosystem's RedisEventBus instance.
        """
        self._redis_bus = redis_bus

        try:
            import sys
            import os

            observatory_root = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                ),
                "projects",
                "network_observatory",
            )
            if observatory_root not in sys.path:
                sys.path.insert(0, observatory_root)

            from src.core.event_bus import EventBus

            self._observatory_bus = EventBus()

            # Subscribe to all mapped topics
            for local_topic in TOPIC_MAP:
                self._observatory_bus.subscribe(
                    local_topic, self._make_forwarder(local_topic)
                )

            self._running = True
            logger.info(
                "Observatory bridge started: %d topics mapped",
                len(TOPIC_MAP),
            )
        except ImportError as e:
            logger.warning("Observatory bridge: could not import EventBus: %s", e)
        except Exception as e:
            logger.error("Observatory bridge start error: %s", e)

    def _make_forwarder(self, local_topic: str):
        """Create a callback that forwards events to Redis."""
        redis_topic = TOPIC_MAP[local_topic]

        def forwarder(payload: Any) -> None:
            if self._redis_bus and self._running:
                try:
                    from raphael.core.bus.event_bus import Event

                    event = Event(
                        topic=redis_topic,
                        payload=payload
                        if isinstance(payload, dict)
                        else {"data": str(payload)},
                        source="network_observatory",
                    )
                    # Fire-and-forget async publish
                    asyncio.create_task(self._redis_bus.publish(event))
                except Exception as e:
                    logger.error("Bridge forward error topic=%s: %s", redis_topic, e)

        return forwarder

    @property
    def observatory_bus(self) -> Optional[Any]:
        """Expose the observatory bus for direct use by observatory components."""
        return self._observatory_bus

    async def stop(self) -> None:
        """Stop the bridge."""
        self._running = False
        logger.info("Observatory bridge stopped.")


# Singleton
observatory_bridge = ObservatoryBridge()
