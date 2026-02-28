from typing import Optional
from raphael.core.bus.redis_bus import RedisEventBus

# Global Event Bus instance
event_bus: Optional[RedisEventBus] = None
