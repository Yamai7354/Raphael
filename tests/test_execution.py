import pytest
import asyncio
from core.execution.tool_registry import BaseTool, ToolRegistry
from core.execution.system_control import SystemController
from core.execution.code_runner import SandboxedCodeRunner
from core.execution.automation import TaskAutomator


class MockCalculator(BaseTool):
    def __init__(self):
        super().__init__(name="math_calc", description="Adds numbers")

    def execute(self, params: dict):
        if "fail" in params:
            raise ValueError("Calculated crash.")
        return {"result": params.get("a", 0) + params.get("b", 0)}


def test_tool_registry():
    registry = ToolRegistry()
    registry.register_tool(MockCalculator())

    # Success Case
    good = registry.execute_tool("math_calc", {"a": 5, "b": 10})
    assert good.get("result") == 15

    # Missing Case
    miss = registry.execute_tool("weather_api", {})
    assert "error" in miss

    # Exception Case
    err = registry.execute_tool("math_calc", {"fail": True})
    assert "error" in err


def test_system_controller():
    controller = SystemController()

    # Safe Command
    safe = controller.execute_command("echo hello")
    assert safe["exit_code"] == 0
    assert safe["stdout"] == "hello"

    # Blocked Command
    blocked = controller.execute_command("rm -rf /test/something")
    assert blocked["exit_code"] == 1
    assert "BLOCKED" in blocked["stderr"]


def test_sandbox_code_runner():
    runner = SandboxedCodeRunner()

    # Good script
    good_src = 'print("hello from python")\n'
    out = runner.execute_script("python", good_src)
    assert out["exit_code"] == 0
    assert out["stdout"] == "hello from python"

    # Bad script Syntax
    bad_src = 'print("uh oh"'
    out_err = runner.execute_script("python", bad_src)
    assert out_err["exit_code"] == 1
    assert "SyntaxError" in out_err["stderr"]


async def test_automation_engine():
    automator = TaskAutomator(max_retries=2, initial_delay=0.1)

    fail_counter = 0

    async def flaky_operation():
        nonlocal fail_counter
        if fail_counter < 2:
            fail_counter += 1
            raise Exception("Mock timeout")
        return {"status": "success"}

    # Should fail twice, sleep, then succeed
    res = await automator.execute_with_retry(flaky_operation)
    assert res["status"] == "success"
    assert fail_counter == 2

    # Exhaust retries
    async def doomed_operation():
        raise Exception("Always fails")

    doom_res = await automator.execute_with_retry(doomed_operation)
    assert "error" in doom_res
    assert doom_res.get("retries_exhausted") is True


async def run_all_tests():
    print("Running Execution Layer 8 tests natively...")

    test_tool_registry()
    print("test_tool_registry: PASSED")

    test_system_controller()
    print("test_system_controller: PASSED")

    test_sandbox_code_runner()
    print("test_sandbox_code_runner: PASSED")

    await test_automation_engine()
    print("test_automation_engine: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
