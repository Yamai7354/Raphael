import logging
from typing import Dict, Any
from data.schemas import SystemEvent, EventType, LayerContext
from event_bus.event_bus import SystemEventBus
from core.perception.normalizer import InputNormalizer
from core.perception.models import MockVisionModel, MockSpeechModel, TextUnderstandingModel
from core.perception.attention import AttentionFilter

logger = logging.getLogger(__name__)


class PerceptionRouter:
    """
    The central coordinator for Layer 2.
    Subscribes to raw Layer 1 OBSERVATIONs, routes them through the
    Perception pipeline (Normalizer -> Modality Models -> Attention),
    and republishes a structural, prioritized semantic event back to the bus.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.normalizer = InputNormalizer()
        self.vision = MockVisionModel()
        self.speech = MockSpeechModel()
        self.text = TextUnderstandingModel()
        self.attention = AttentionFilter()

        self.layer_ctx = LayerContext(layer_number=2, module_name="PerceptionRouter")

    def register_subscriptions(self):
        """Binds the router to listen to Layer 1 environment outputs."""
        self.bus.subscribe(EventType.OBSERVATION, self.handle_raw_observation)

    async def handle_raw_observation(self, event: SystemEvent):
        """
        Callback triggered when a raw OBSERVATION hits the bus.
        Only process events originating from Layer 1 (Environment) to avoid infinite loops.
        """
        if event.source_layer.layer_number != 1:
            return

        try:
            # 1. Normalize
            raw_data = {
                "source": event.source_layer.module_name,
                "timestamp": event.timestamp,
                "payload": event.payload,
            }
            normalized = self.normalizer.process(raw_data)

            # 2. Extract Modality Semantics (Run through all models; in reality,
            # you'd route specifically or run concurrent specific pipelines)
            visual_ctx = self.vision.process(normalized["payload"])
            audio_ctx = self.speech.process(visual_ctx)
            semantic_ctx = self.text.process(audio_ctx)

            # 3. Apply Attention & Priority Filter
            final_payload = self.attention.process(semantic_ctx)

            # 4. Extract assigned priority from the filter
            routing_priority = final_payload.pop("attention_priority", 5)

            # 5. Republish as a clean, Layer 2 parsed event
            semantic_event = SystemEvent(
                event_type=EventType.OBSERVATION,  # Still an observation, but contextualized
                source_layer=self.layer_ctx,
                priority=routing_priority,
                payload=final_payload,
                correlation_id=event.event_id,  # Trace back to the raw source event
            )

            await self.bus.publish(semantic_event)
            logger.debug(
                f"Perception successfully parsed and routed event {semantic_event.event_id}"
            )

        except Exception as e:
            logger.error(f"Perception routing failed for event {event.event_id}: {e}")
            # Emit crash report for Layer 4 health monitoring
            crash_event = SystemEvent(
                event_type=EventType.CRASH_REPORT,
                source_layer=self.layer_ctx,
                priority=10,
                payload={"error": str(e), "failed_event_id": str(event.event_id)},
            )
            await self.bus.publish(crash_event)
