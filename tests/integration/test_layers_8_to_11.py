import pytest
from agents.coder import CodingAgent
from core.execution.tool_registry import ToolRegistry
from core.execution.tools import BashExecutionTool, PythonExecutionTool


@pytest.mark.asyncio
async def test_layer_8_to_11_execution_sandbox():
    """
    Test the Execution and Sandbox layers (8-11).
    Proves that a worker Agent (Layer 7) can dynamically invoke the
    Execution Sandboxes (Layer 8-11) to run tests and debug output.
    """
    # 1. Setup the Tool Environment (Execution Sandboxes)
    registry = ToolRegistry()
    registry.register_tool(BashExecutionTool())
    registry.register_tool(PythonExecutionTool())

    # 2. Setup the target Agent
    coder = CodingAgent(agent_id="agent_omega", tool_registry=registry)

    # 3. Create a mock dispatch payload that commands the agent to test logic
    test_payload = {
        "sub_task_id": "test_logic_run_1",
        "plan_id": "plan_999",
        "test_command": "echo 'pytest tests/mock_test.py... PASSED'",
    }

    # 4. Trigger the agent's execute directly
    # In a real scenario, this is called by AgentRouter handling an event
    result = await coder.execute(test_payload)

    # 5. Assertions
    assert result["success"] is True, "The agent should report a successful execution."
    logs = result["logs"]
    assert any("Executing debugging command" in log for log in logs), (
        "Logs should indicate tool usage."
    )
    assert any("Successfully validated logic via test suite." in log for log in logs), (
        "Logs should indicate success branch."
    )

    output = result["output"]
    tool_result = output.get("tool_result")

    assert tool_result is not None, (
        "Agent should have received a tool result from the Execution Sandbox."
    )
    assert tool_result["exit_code"] == 0, "Fake pytest command should exit 0."
    assert tool_result["stdout"] == "pytest tests/mock_test.py... PASSED", (
        "Stdout should match the bash echo."
    )
