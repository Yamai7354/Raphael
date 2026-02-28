import pytest
import asyncio
from src.raphael.learning.rewards import RewardGenerator
from src.raphael.learning.skill_engine import SkillManager
from src.raphael.learning.policy_engine import PolicyManager


def test_reward_generator():
    gen = RewardGenerator()

    # Success Case
    good_task = {
        "success": True,
        "duration_ms": 250,  # fast bonus
        "logs": ["info: all clear"],
        "agent_id": "agent_alpha",
        "capability_used": "bash",
    }
    good_sig = gen.compute_signal(good_task)
    assert good_sig["score"] == 12.0  # +10 base, +2 bonus

    # Failure Case
    bad_task = {
        "success": False,
        "duration_ms": 6000,  # slow penalty
        "logs": ["exception occurred: segfault"],  # 1 error log penalty
        "agent_id": "agent_alpha",
        "capability_used": "bash",
    }
    bad_sig = gen.compute_signal(bad_task)
    assert bad_sig["score"] == -13.5  # -10 base, -2 penalty, -1.5 exception log


def test_skill_manager():
    manager = SkillManager()

    # Send a positive bump
    mock_good_sig = {"agent_id": "agent_omega", "task_capability": "python", "score": 10.0}
    val = manager.process_reward_signal(mock_good_sig)
    assert val > 1.0  # Should be 1.01

    # Ensure it's tracked natively
    recorded = manager.get_proficiency("agent_omega", "python")
    assert recorded == val

    # Drop it with a major penalty
    mock_bad_sig = {"agent_id": "agent_omega", "task_capability": "python", "score": -100.0}
    val_down = manager.process_reward_signal(mock_bad_sig)
    assert val_down < 1.0


def test_policy_manager():
    initial = {"model": "default"}
    mgr = PolicyManager(initial)

    assert mgr.current_version == 1
    assert mgr.current_policy["model"] == "default"

    # Update
    mgr.update_policy({"model": "new_experimental", "timeout": 5})
    assert mgr.current_version == 2
    assert mgr.current_policy["model"] == "new_experimental"

    # Simulate failed stability (e.g. 3 negative globals in a row)
    rollback = False
    for i in [-5.0, -10.0, -2.0]:  # Tripping the rollback_threshold
        rollback = mgr.evaluate_system_stability(i)

    assert rollback is True
    assert mgr.current_version == 1  # Verify rollback
    assert "timeout" not in mgr.current_policy  # Ensure new keys are gone


async def run_all_tests():
    print("Running Learning Layer 10 tests natively...")

    test_reward_generator()
    print("test_reward_generator: PASSED")

    test_skill_manager()
    print("test_skill_manager: PASSED")

    test_policy_manager()
    print("test_policy_manager: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
