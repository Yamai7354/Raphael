import pytest
import asyncio
from src.raphael.strategy.strategy_engine import StrategyEngine
from src.raphael.strategy.tech_radar import TechRadar
from src.raphael.strategy.forecaster import CapabilityForecaster
from src.raphael.strategy.self_model import SystemSelfModel


def test_strategy_engine():
    engine = StrategyEngine()

    goal = "Create a scalable network observatory"
    strat = engine.generate_strategy(goal)

    assert strat["global_goal"] == goal
    assert len(strat["phases"]) == 3
    assert strat["phases"][0]["status"] == "pending"


def test_tech_radar():
    radar = TechRadar()

    topics = ["Docker Containers", "Rust Programming", "Network Security Protocols"]
    goal = "Establish strong Network boundaries"

    evaluations = radar.evaluate_topics(topics, goal)

    assert len(evaluations) == 3

    # "Network Security Protocols" has the word "Network" in common with the goal
    top_result = evaluations[0]
    assert top_result["topic"] == "Network Security Protocols"
    assert top_result["aligned_with_goal"] is True
    assert top_result["relevance_score"] > 0.1  # higher than baseline

    # The other topics share no keywords with the goal and remain at base 0.1
    assert evaluations[1]["aligned_with_goal"] is False
    assert evaluations[1]["relevance_score"] == 0.1
    assert evaluations[2]["aligned_with_goal"] is False
    assert evaluations[2]["relevance_score"] == 0.1


def test_capability_forecaster():
    forecaster = CapabilityForecaster()

    # Mock linear memory growth telemetry
    mock_history = [
        {"memory_mb": 14000, "active_tasks": 50},
        {"memory_mb": 15000, "active_tasks": 60},
        {
            "memory_mb": 15500,
            "active_tasks": 95,
        },  # Growth of 500, cap is 16000. 1 tick remaining. Task capacity near 90%.
    ]

    forecast = forecaster.forecast_bottlenecks(mock_history)

    assert forecast["status"] == "critical"
    assert len(forecast["warnings"]) == 2
    assert any("CRITICAL:" in w for w in forecast["warnings"])
    assert any("WARNING:" in w for w in forecast["warnings"])


def test_system_self_model():
    model = SystemSelfModel()

    health = {"status": "nominal", "flags": ["cpu_spike"]}
    agents = {"node_mac": 1, "agent_omega": 1}
    policy = {"mode": "aggressive"}

    state = model.compile_state(health, agents, policy)

    assert state["identity"] == "Raphael OS Layer 12"
    assert state["system_health"] == "nominal"
    assert state["workforce"]["total_active_agents"] == 2
    assert state["active_directives"]["mode"] == "aggressive"


async def run_all_tests():
    print("Running Strategy Layer 12 tests natively...")

    test_strategy_engine()
    print("test_strategy_engine: PASSED")

    test_tech_radar()
    print("test_tech_radar: PASSED")

    test_capability_forecaster()
    print("test_capability_forecaster: PASSED")

    test_system_self_model()
    print("test_system_self_model: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
