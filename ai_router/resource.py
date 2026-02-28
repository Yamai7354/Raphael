import logging
from raphael.core.planning.resource_manager import ResourceManager
from .working_memory import working_memory
from . import bus
from raphael.core.bus.event_bus import Event

logger = logging.getLogger("ai_router.resource")

# Adapt WorkingMemory to expected interface if necessary
# ResourceManager expects .get(key) and .set(key, value)
# WorkingMemory has .get(key) and .put(key, value, ttl)
# We might need a wrapper or update ResourceManager to use .put


class ResourceManagerAdapter(ResourceManager):
    def __init__(self, memory, max_tasks=5):
        super().__init__(memory, max_tasks)
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("ResourceManager starting...")
        if bus.event_bus:
            await bus.event_bus.subscribe("task.routed", self._handle_task_routed)
            await bus.event_bus.subscribe("task.completed", self._handle_task_released)
            await bus.event_bus.subscribe("task.failed", self._handle_task_released)
            logger.info("ResourceManager subscribed to events.")

    async def stop(self):
        self._running = False
        logger.info("ResourceManager stopped.")

    async def _handle_task_routed(self, event: Event):
        payload = event.payload
        node_id = payload.get("node_id")
        task_id = payload.get("task_id")
        if node_id:
            await self.allocate_resources(node_id, task_id)

    async def _handle_task_released(self, event: Event):
        payload = event.payload
        node_id = payload.get("node_id")
        task_id = payload.get("task_id")
        if node_id:
            await self.release_resources(node_id, task_id)

    # Override modify methods to use memory.put instead of memory.set if needed
    # ResourceManager uses self.memory.set(key, value)
    # RedisWorkingMemory (from import) likely uses .set
    # ai_router.WorkingMemory uses .put(key, value, ttl)
    # We should override allocate/release to use self.memory.put or wrapper

    async def allocate_resources(self, agent_id: str, task_id: str):
        if not self.memory.client:
            logger.warning("Redis client not connected, skipping allocation")
            return

        tasks_key = f"agent_tasks:{agent_id}"

        # Atomic Idempotency: SADD returns 1 if new, 0 if exists
        added = await self.memory.client.sadd(tasks_key, task_id)
        if added:
            # Set TTL
            await self.memory.client.expire(tasks_key, 3600 * 24)
            current_load = await self.get_agent_load(agent_id)
            logger.info(f"Allocated resources for {agent_id} (Load: {current_load})")
        else:
            logger.debug(f"Task {task_id} already allocated for {agent_id}")

    async def release_resources(self, agent_id: str, task_id: str):
        if not self.memory.client:
            return

        tasks_key = f"agent_tasks:{agent_id}"

        removed = await self.memory.client.srem(tasks_key, task_id)
        if removed:
            current_load = await self.get_agent_load(agent_id)
            logger.info(f"Released resources for {agent_id} (Load: {current_load})")
        else:
            logger.debug(f"Task {task_id} already released for {agent_id}")

    async def get_agent_load(self, agent_id: str) -> int:
        if self.memory.client:
            tasks_key = f"agent_tasks:{agent_id}"
            return await self.memory.client.scard(tasks_key)
        else:
            # Fallback
            return await super().get_agent_load(agent_id)


# Singleton initialization
resource_manager = ResourceManagerAdapter(working_memory, max_tasks=5)
