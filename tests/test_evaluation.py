import pytest
import asyncio
from core.evaluation.qa import QualityAssessor
from core.evaluation.critic import CriticAgent
from core.evaluation.sandbox import SandboxManager


def test_quality_assessor():
    qa = QualityAssessor()

    # Passing schema
    good_payload = {"status": "ok", "value": 42}
    result_good = qa.evaluate_output_schema(good_payload, required_keys=["status"])
    assert result_good["passed"] is True

    # Failing schema
    bad_payload = {"value": 42}
    result_bad = qa.evaluate_output_schema(bad_payload, required_keys=["status", "error_log"])
    assert result_bad["passed"] is False
    assert "Missing required keys" in result_bad["reason"]


async def test_critic_agent():
    critic = CriticAgent()

    # Good Output Target
    mock_good_task = {"target_output": {"data": "A well-written code block.", "quality": "high"}}

    good_eval = await critic.execute(mock_good_task)
    assert good_eval["success"] is True
    assert good_eval["output"]["retry_recommended"] is False

    # Flawed Output Target
    mock_bad_task = {"target_output": {"data": "import bug;", "flaw": True}}

    bad_eval = await critic.execute(mock_bad_task)
    assert bad_eval["success"] is False
    assert bad_eval["output"]["retry_recommended"] is True


def test_sandbox_manager():
    manager = SandboxManager(mode="mock")

    # Provisioning
    container_id = manager.provision_environment(image="python:latest")
    assert container_id.startswith("sbx-")
    assert container_id in manager.active_sandboxes

    # Execution
    result = manager.execute_in_sandbox(container_id, "echo test")
    assert result["exit_code"] == 0
    assert "Mock output" in result["stdout"]

    # Fails against missing sandbox
    fail_result = manager.execute_in_sandbox("invalid-id", "echo test")
    assert fail_result["exit_code"] == 1

    # Teardown
    assert manager.teardown_environment(container_id) is True
    assert container_id not in manager.active_sandboxes


async def run_all_tests():
    print("Running Evaluation Layer 9 tests natively...")

    test_quality_assessor()
    print("test_quality_assessor: PASSED")

    await test_critic_agent()
    print("test_critic_agent: PASSED")

    test_sandbox_manager()
    print("test_sandbox_manager: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
