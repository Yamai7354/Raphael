import pytest
from uuid import uuid4
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext


def test_system_event_initialization():
    layer_context = LayerContext(layer_number=2, module_name="Vision Model")
    event = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=layer_context,
        payload={"object": "coffee cup", "confidence": 0.98},
    )

    assert event.event_id is not None
    assert event.timestamp is not None
    assert event.event_type == EventType.OBSERVATION
    assert event.source_layer.layer_number == 2
    assert event.source_layer.module_name == "Vision Model"
    assert event.priority == 5
    assert event.payload["object"] == "coffee cup"


def test_system_event_validation_failure():
    with pytest.raises(ValueError):
        # Missing required fields
        SystemEvent()


def test_priority_bounds():
    layer_context = LayerContext(layer_number=1, module_name="Test")
    with pytest.raises(ValueError):
        SystemEvent(
            event_type=EventType.OBSERVATION,
            source_layer=layer_context,
            priority=11,  # Above max
        )
