import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from agents.system_monitor_agent import SystemMonitorAgent
from data.schemas import SystemEvent, EventType, LayerContext

@pytest.mark.asyncio
async def test_system_monitor_agent_subscription():
    # Mock Event Bus
    mock_bus = MagicMock()

    agent = SystemMonitorAgent(agent_id="TestMonitor")
    await agent.start(mock_bus)

    # Verify subscriptions
    assert mock_bus.subscribe.call_count == 2
    mock_bus.subscribe.assert_any_call(EventType.CRASH_REPORT, agent._handle_crash_report)
    mock_bus.subscribe.assert_any_call(EventType.OBSERVATION, agent._handle_observation)

@pytest.mark.asyncio
async def test_system_monitor_agent_execute():
    agent = SystemMonitorAgent(agent_id="TestMonitor")
    payload = {"task": "check_health"}
    result = await agent.execute(payload)

    assert result["success"] is True
    assert "status" in result["output"]
    assert result["output"]["status"] == "monitoring_active"

@pytest.mark.asyncio
async def test_handle_crash_report(caplog):
    agent = SystemMonitorAgent(agent_id="TestMonitor")
    event = SystemEvent(
        event_type=EventType.CRASH_REPORT,
        source_layer=LayerContext(layer_number=1, module_name="Test"),
        payload={"error": "Something went wrong"}
    )

    with caplog.at_level("ERROR"):
        await agent._handle_crash_report(event)

    assert "SystemMonitor: Received CRASH_REPORT" in caplog.text
    assert "Something went wrong" in caplog.text

@pytest.mark.asyncio
async def test_handle_observation(caplog):
    agent = SystemMonitorAgent(agent_id="TestMonitor")
    event = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=LayerContext(layer_number=1, module_name="SystemMonitor"),
        payload={"metric_type": "telemetry", "data": {"cpu": 50}}
    )

    with caplog.at_level("DEBUG"):
        await agent._handle_observation(event)

    assert "SystemMonitor: Received telemetry" in caplog.text
    assert "50" in caplog.text
