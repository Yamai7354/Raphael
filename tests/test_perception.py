import pytest
import asyncio
from datetime import datetime, timezone
from core.perception.normalizer import InputNormalizer
from core.perception.models import MockVisionModel, MockSpeechModel, TextUnderstandingModel
from core.perception.attention import AttentionFilter
from core.perception.router import PerceptionRouter
from event_bus.event_bus import SystemEventBus
from data.schemas import SystemEvent, EventType, LayerContext


def test_input_normalizer():
    normalizer = InputNormalizer()

    # Test valid timestamp parsing
    raw_event = {"payload": "test", "timestamp": "2026-01-01T12:00:00Z"}
    processed = normalizer.process(raw_event)
    assert processed["timestamp"] == "2026-01-01T12:00:00+00:00"

    # Test unstructured payload wrapped into dict
    raw_event_string = {"payload": "Just a string log."}
    processed_str = normalizer.process(raw_event_string)
    assert processed_str["payload"] == {"raw_text": "Just a string log."}


def test_modality_models():
    # Vision
    v_model = MockVisionModel()
    v_out = v_model.process({"raw_text": "visual: looking at desk"})
    assert v_out["modality"] == "vision"
    assert "detected_objects" in v_out

    # Speech
    s_model = MockSpeechModel()
    s_out = s_model.process({"raw_text": "speech: Hello Raphael"})
    assert s_out["modality"] == "speech"
    assert s_out["transcription"] == "Hello Raphael"

    # Text Understanding (Intent)
    t_model = TextUnderstandingModel()
    t_out_cmd = t_model.process({"raw_text": "user_command: deploy the server"})
    assert t_out_cmd["modality"] == "text"
    assert t_out_cmd["intent"] == "user_directive"

    t_out_err = t_model.process({"raw_text": "kernel exception occurred!"})
    assert t_out_err["intent"] == "system_alert"


def test_attention_filter():
    attention = AttentionFilter()

    # Background log -> drops priority to 2
    bg_payload = {"intent": "background_info", "modality": "text"}
    assert attention.calculate_priority(bg_payload) == 2

    # Voice command -> rockets priority to 9
    voice_payload = {"intent": "user_directive", "modality": "speech"}
    assert attention.calculate_priority(voice_payload) == 9

    # System crash -> critical priority 9
    crash_payload = {"intent": "system_alert", "modality": "text"}
    assert attention.calculate_priority(crash_payload) == 9


async def test_perception_router_pipeline():
    bus = SystemEventBus()
    router = PerceptionRouter(bus)
    router.register_subscriptions()

    captured_semantic_events = []

    async def trap_l2_events(event: SystemEvent):
        # We only want to capture the output coming out of Layer 2
        if event.source_layer.layer_number == 2:
            captured_semantic_events.append(event)

    bus.subscribe(EventType.OBSERVATION, trap_l2_events)
    await bus.start()

    # Simulate an incoming raw event from Layer 1 (Environment)
    layer_1_ctx = LayerContext(layer_number=1, module_name="NetworkAccessor")
    raw_env_event = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=layer_1_ctx,
        payload={
            "raw_text": "user_command: open browser to github"
        },  # Messy string payload wrapped safely
    )

    await bus.publish(raw_env_event)
    await asyncio.sleep(0.1)  # Let the async bus pipe it through L2

    # Assertions
    assert len(captured_semantic_events) == 1
    l2_event = captured_semantic_events[0]

    # The normalizer wrapped the messy string
    assert "raw_text" in l2_event.payload
    # The text model recognized the intent
    assert l2_event.payload["intent"] == "user_directive"
    # The attention filter set the priority correctly for a typed command
    assert l2_event.priority == 8
    # The correlation ID maps back to the raw source
    assert l2_event.correlation_id == raw_env_event.event_id

    await bus.stop()


async def run_all_tests():
    print("Running Perception Layer 2 tests natively...")

    test_input_normalizer()
    print("test_input_normalizer: PASSED")

    test_modality_models()
    print("test_modality_models: PASSED")

    test_attention_filter()
    print("test_attention_filter: PASSED")

    await test_perception_router_pipeline()
    print("test_perception_router_pipeline: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
