import pytest
from swarm.dynamics import SwarmMetabolism, AgentGenerationManager
from agents.base import BaseAgent

# Dummy Agent for testing
class DummyAgent(BaseAgent):
    def __init__(self, agent_id: str, role_group: str, capabilities: list[str] = None):
        super().__init__(agent_id, capabilities or [])
        self.role_group = role_group

    async def execute(self, payload):
        success = payload.get("success", True)
        return self._standard_response(success, ["Executed dummy payload."])

def test_metabolism_energy_tracking():
    metabolism = SwarmMetabolism(initial_energy=100)
    
    # Test deduction
    metabolism.deduct_exploration_cost()
    assert metabolism.energy == 90
    
    # Test rewards
    metabolism.add_memory_reward()
    assert metabolism.energy == 105
    
    metabolism.add_task_reward()
    assert metabolism.energy == 110

def test_agent_generation_ratios():
    agents = [
        DummyAgent("r1", "Researcher"),
        DummyAgent("b1", "Builder"),
        DummyAgent("e1", "Evaluator")
    ]
    
    # We have 1 of each of top 3, but no Memory or Explorer. The deficit is highest for Memory or Explorer (0.10 target vs 0.0 current)
    # However, Researcher/Builder have 0.33 vs 0.30 target -> surplus.
    next_role = AgentGenerationManager.determine_next_agent_role(agents)
    assert next_role in ["Memory/Archivist", "Explorer"]
    
@pytest.mark.asyncio
async def test_specialization_drift():
    agent = DummyAgent("d1", "Builder", ["basic_build"])
    
    # Threshold is 5. Let's send 4 successful requests
    for i in range(4):
        await agent.run({"sub_task_id": str(i), "domain": "debugging", "success": True})
        
    assert "expert_debugging" not in agent.capabilities
    
    # 5th request should trigger specialization
    await agent.run({"sub_task_id": "5", "domain": "debugging", "success": True})
    assert "expert_debugging" in agent.capabilities
    assert agent.specialization_threshold > 5 # It should scale up
