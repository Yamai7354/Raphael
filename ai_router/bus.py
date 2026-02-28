from typing import Optional
from event_bus.redis_bus import RedisEventBus

# Global Event Bus instance
event_bus: Optional[RedisEventBus] = None
