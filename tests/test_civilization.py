import pytest
import asyncio
from src.raphael.civilization.council import GovernanceCouncil
from src.raphael.civilization.infrastructure import InfrastructureManager
from src.raphael.civilization.innovation import InnovationEngine
from src.raphael.civilization.society import SocietyManager
from src.raphael.civilization.knowledge import KnowledgeManager


def test_governance_council():
    council = GovernanceCouncil()

    requests = [
        {"request_id": "r1", "category": "idle_optimization"},  # Priority 4
        {"request_id": "r2", "category": "system_health"},  # Priority 0
        {"request_id": "r3", "category": "autonomous_research"},  # Priority 3
    ]

    resolution = council.resolve_conflict(requests)

    assert resolution["approved_request_id"] == "r2"
    assert resolution["category"] == "system_health"


def test_infrastructure_manager():
    manager = InfrastructureManager()

    # Needs 5 ticks. 4 high doesn't trigger it.
    nominal_history = [0.9, 0.9, 0.9, 0.9, 0.5]
    res1 = manager.evaluate_evolution_needs(nominal_history)
    assert res1["action"] == "none"

    # 5 sustained ticks above 0.85 should trigger an upgrade recommendation
    critical_history = [0.86, 0.90, 0.95, 0.88, 0.99]
    res2 = manager.evaluate_evolution_needs(critical_history)
    assert res2["action"] == "recommend_upgrade"
    assert res2["recommended_baseline_mb"] == 24000  # 16000 * 1.5


def test_innovation_engine():
    engine = InnovationEngine()

    research = [
        {
            "concept": "Minor UI tweak",
            "discoverer": "ui_agent",
            "estimated_impact": 2,
            "integration_friction": 1,
        },
        {
            "concept": "Quantum Routing",
            "discoverer": "research_alpha",
            "estimated_impact": 9,
            "integration_friction": 8,
        },
    ]

    ranked = engine.prioritize_discoveries(research)

    # ROI = Impact - (Friction * 0.5)
    # Quantum: 9 - 4 = 5.0
    # UI Tweak: 2 - 0.5 = 1.5
    assert len(ranked) == 2
    assert ranked[0]["concept"] == "Quantum Routing"
    assert ranked[0]["innovation_roi"] == 5.0
    assert ranked[0]["status"] == "pending_acquisition"

    assert ranked[1]["concept"] == "Minor UI tweak"
    assert ranked[1]["status"] == "archived"


def test_society_manager():
    manager = SocietyManager()

    agents = [
        {"agent_id": "overworked", "current_tasks": 6, "status": "active"},  # Max is 3
        {"agent_id": "idle_1", "current_tasks": 0, "status": "active"},
        {"agent_id": "offline_1", "current_tasks": 0, "status": "offline"},
    ]

    res = manager.balance_workload(agents)
    assert res["status"] == "rebalanced"

    cmds = res["rebalance_commands"]
    assert len(cmds) == 1
    assert cmds[0]["from_agent"] == "overworked"
    assert cmds[0]["to_agent"] == "idle_1"
    assert cmds[0]["task_count"] == 6 - 3  # Excess tasks


def test_knowledge_manager():
    manager = KnowledgeManager()

    # Domain: "architecture_specs" requires clearance 3
    # Agent with level 2 should fail
    fail = manager.request_access("worker_2", 2, "architecture_specs")
    assert fail["access_granted"] is False

    # Agent with level 4 should pass
    pass_req = manager.request_access("sys_admin", 4, "architecture_specs")
    assert pass_req["access_granted"] is True
    assert "token" in pass_req


async def run_all_tests():
    print("Running Civilization Layer 13 tests natively...")

    test_governance_council()
    print("test_governance_council: PASSED")

    test_infrastructure_manager()
    print("test_infrastructure_manager: PASSED")

    test_innovation_engine()
    print("test_innovation_engine: PASSED")

    test_society_manager()
    print("test_society_manager: PASSED")

    test_knowledge_manager()
    print("test_knowledge_manager: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
