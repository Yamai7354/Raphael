import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from ..knowledge.manager import KnowledgeManager
from ..policy.engine import PolicyEngine
from ..models.task import Task, TaskPriority

logger = logging.getLogger("delegation_planner")


class DelegationPlanner:
    """RAPHAEL-501: Multi-Agent Delegation Planner.
    Selects the best agent for a task using Knowledge Graph data.
    """

    def __init__(
        self, knowledge_manager: KnowledgeManager, policy_engine: PolicyEngine
    ):
        self.knowledge = knowledge_manager
        self.policy = policy_engine

    async def select_agents(self, task: Task, limit: int = 3) -> List[Dict[str, Any]]:
        """Suggests agents for a task based on semantic matching and policy checks."""

        # 1. Semantic Search for Capabilities
        # We query the knowledge graph for agents that have handled similar tasks or have relevant capability tags
        query = f"Agent capable of {task.title} {task.description}"

        candidates = await self.knowledge.query_knowledge(query, limit=limit * 2)

        valid_agents = []
        for candidate in candidates:
            # candidate structure from KnowledgeManager:
            # { "concept": {...}, "score": float, "context": [...] }

            agent_data = candidate["concept"]
            # Ensure it's actually an agent
            if agent_data.get("label") != "Agent":
                continue

            agent_id = agent_data.get("properties", {}).get(
                "name"
            )  # Using name as ID for now
            if not agent_id:
                continue

            # 2. Risk/Policy Check
            # Can this agent handle this task priority/type?
            # We mock a policy context
            policy_context = {
                "agent_id": agent_id,
                "task_priority": task.priority,
                "task_start_time": None,
            }

            decision = await self.policy.evaluate_task(task, policy_context)

            if decision.allowed:
                valid_agents.append(
                    {
                        "agent_id": agent_id,
                        "score": candidate["score"],
                        "reasoning": f"Graph match ({candidate['score']:.2f}). Policy: {decision.reasoning}",
                    }
                )
            else:
                logger.debug(
                    f"Agent {agent_id} rejected by policy: {decision.reasoning}"
                )

        # Sort by score
        valid_agents.sort(key=lambda x: x["score"], reverse=True)
        return valid_agents[:limit]
