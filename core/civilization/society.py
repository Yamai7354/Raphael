import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class SocietyManager:
    """
    Maintains the health and balance of the Agent Swarm, ensuring no single
    node or agent is overworked while others sit idle.
    """

    def __init__(self):
        self.max_concurrent_tasks_per_agent = 3

    def balance_workload(self, active_agents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes the current task distribution across the society and issues
        rebalancing directives if gross inequalities are detected.

        Expected active_agents dict format:
        { "agent_id": "alpha", "current_tasks": 4, "status": "active" }
        """
        commands = []

        if not active_agents:
            return {"status": "nominal", "rebalance_commands": commands}

        # Find overworked agents
        overworked = [
            a
            for a in active_agents
            if a.get("current_tasks", 0) > self.max_concurrent_tasks_per_agent
        ]

        # Find idle agents
        idle = [
            a
            for a in active_agents
            if a.get("current_tasks", 0) == 0 and a.get("status") == "active"
        ]

        for agent in overworked:
            if idle:
                helper = idle.pop(0)
                excess_tasks = agent["current_tasks"] - self.max_concurrent_tasks_per_agent

                commands.append(
                    {
                        "action": "reassign_tasks",
                        "from_agent": agent["agent_id"],
                        "to_agent": helper["agent_id"],
                        "task_count": excess_tasks,
                    }
                )
                logger.info(
                    f"SocietyManager: Issued rebalance from {agent['agent_id']} to {helper['agent_id']}"
                )
            else:
                logger.warning(
                    f"SocietyManager: Agent {agent['agent_id']} is overworked, but no idle agents are available!"
                )

        status = "rebalanced" if commands else "nominal"
        return {"status": status, "rebalance_commands": commands}
