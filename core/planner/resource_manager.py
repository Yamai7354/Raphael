import logging
from typing import Dict
from ..memory.working.redis_buffer import RedisWorkingMemory

logger = logging.getLogger("resource_manager")


class ResourceManager:
    """RAPHAEL-502: Load & Cost Optimization Manager.
    Tracks agent utilization and enforces limits.
    """

    def __init__(self, memory: RedisWorkingMemory, max_concurrent_tasks: int = 5):
        self.memory = memory
        self.max_tasks = max_concurrent_tasks
        # Simple local cache for task counts, ideally synced via Redis
        self.agent_load: Dict[str, int] = {}

    async def can_accept_task(self, agent_id: str) -> bool:
        """Check if agent has capacity for a new task."""
        current_load = await self.get_agent_load(agent_id)
        if current_load >= self.max_tasks:
            logger.warning(
                f"Agent {agent_id} is overloaded ({current_load}/{self.max_tasks})"
            )
            return False
        return True

    async def allocate_resources(self, agent_id: str, task_id: str):
        """Register task start for an agent."""
        key = f"agent_load:{agent_id}"
        # Atomic increment in Redis (simulated with get/set for now as RedisWorkingMemory might not expose INCR)
        # Ideally we should extend RedisWorkingMemory to support atomic operations or access the underlying client
        # For MVP, get/set is acceptable but race-prone.
        # But wait, RedisWorkingMemory likely wraps redis.
        # Let's check if we can access atomic incr.
        # If not, we'll do get/set.
        current = await self.get_agent_load(agent_id)
        new_load = current + 1
        await self.memory.set(key, new_load)
        logger.info(f"Allocated resources for {agent_id} (Load: {new_load})")

    async def release_resources(self, agent_id: str, task_id: str):
        """Register task completion."""
        key = f"agent_load:{agent_id}"
        current = await self.get_agent_load(agent_id)
        if current > 0:
            new_load = current - 1
            await self.memory.set(key, new_load)
            logger.info(f"Released resources for {agent_id} (Load: {new_load})")
        else:
            # harness against negative load
            await self.memory.set(key, 0)

    async def get_agent_load(self, agent_id: str) -> int:
        """Get current active task count."""
        key = f"agent_load:{agent_id}"
        load = await self.memory.get(key)
        return int(load) if load else 0

    async def get_cost_estimate(self, agent_id: str, task_type: str) -> float:
        """Estimate token cost for a task.
        Future: dynamic based on model pricing.
        """
        # Placeholder static cost
        return 0.05
