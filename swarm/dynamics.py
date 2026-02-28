import logging

logger = logging.getLogger(__name__)


class SwarmMetabolism:
    """
    Tracks and manages global energy for the Swarm.
    """

    def __init__(self, initial_energy: int = 100):
        self.energy = initial_energy
        self.exploration_cost = 10
        self.accepted_memory_reward = 15
        self.completed_task_reward = 5

    def deduct_exploration_cost(self):
        self.energy -= self.exploration_cost
        logger.info(f"Metabolism: Deducted exploration cost. New energy: {self.energy}")

    def add_memory_reward(self):
        self.energy += self.accepted_memory_reward
        logger.info(f"Metabolism: Added memory reward. New energy: {self.energy}")

    def add_task_reward(self):
        self.energy += self.completed_task_reward
        logger.info(f"Metabolism: Added task completion reward. New energy: {self.energy}")


class AgentGenerationManager:
    """
    Manages generation of new agents, enforcing target domain ratios.
    """

    TARGET_RATIOS = {
        "Researcher": 0.30,
        "Builder": 0.30,
        "Evaluator": 0.20,
        "Memory/Archivist": 0.10,
        "Explorer": 0.10,
    }

    @staticmethod
    def get_role_distribution(agents: list) -> dict[str, float]:
        """Calculates current ratio of each role."""
        if not agents:
            return {role: 0.0 for role in AgentGenerationManager.TARGET_RATIOS.keys()}

        counts = {role: 0 for role in AgentGenerationManager.TARGET_RATIOS.keys()}
        total = len(agents)

        for agent in agents:
            # Assume agent has a 'role_group' or similar property
            group = getattr(agent, "role_group", "Unknown")
            if group in counts:
                counts[group] += 1

        return {role: count / total for role, count in counts.items()}

    @staticmethod
    def determine_next_agent_role(agents: list) -> str:
        """Returns the role that is currently most underrepresented."""
        distribution = AgentGenerationManager.get_role_distribution(agents)

        greatest_deficit = -1.0
        target_role = "Researcher"  # fallback

        for role, target in AgentGenerationManager.TARGET_RATIOS.items():
            current = distribution.get(role, 0.0)
            deficit = target - current
            if deficit > greatest_deficit:
                greatest_deficit = deficit
                target_role = role

        return target_role
