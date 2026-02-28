"""
WORLD-404 — Tool & API Registry.

Registry of tools, APIs, and integrations with capabilities,
usage limits, supported roles, cost, and reliability.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.world_model.tool_registry")


@dataclass
class ToolRecord:
    """A tool or API available to the swarm."""

    tool_id: str = field(default_factory=lambda: f"tool_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    tool_type: str = "tool"  # tool, api, integration
    capabilities: list[str] = field(default_factory=list)
    supported_roles: list[str] = field(default_factory=list)
    usage_limit_per_hour: int = 0  # 0 = unlimited
    cost_per_call: float = 0.0
    reliability_score: float = 1.0  # 0-1
    endpoint: str = ""
    auth_required: bool = False
    available: bool = True
    call_count: int = 0
    error_count: int = 0
    registered_at: float = field(default_factory=time.time)

    @property
    def error_rate(self) -> float:
        return self.error_count / max(1, self.call_count)

    def to_dict(self) -> dict:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "type": self.tool_type,
            "capabilities": self.capabilities,
            "roles": self.supported_roles,
            "limit": self.usage_limit_per_hour,
            "cost": self.cost_per_call,
            "reliability": round(self.reliability_score, 3),
            "available": self.available,
        }


class ToolRegistry:
    """Registry of available tools and APIs."""

    def __init__(self):
        self._tools: dict[str, ToolRecord] = {}
        self._by_name: dict[str, str] = {}
        self._hourly_calls: dict[str, list[float]] = {}

    def register(self, name: str, description: str = "", **kwargs) -> ToolRecord:
        if name in self._by_name:
            t = self._tools[self._by_name[name]]
            for k, v in kwargs.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            return t

        t = ToolRecord(name=name, description=description, **kwargs)
        self._tools[t.tool_id] = t
        self._by_name[name] = t.tool_id
        logger.info("tool_registered name=%s type=%s caps=%s", name, t.tool_type, t.capabilities)
        return t

    def can_use(self, name: str) -> bool:
        """Check if tool is available and within rate limits."""
        tid = self._by_name.get(name)
        if not tid:
            return False
        tool = self._tools[tid]
        if not tool.available:
            return False
        if tool.usage_limit_per_hour <= 0:
            return True  # unlimited

        now = time.time()
        calls = self._hourly_calls.get(name, [])
        recent = [t for t in calls if t > now - 3600]
        return len(recent) < tool.usage_limit_per_hour

    def record_call(self, name: str, success: bool) -> None:
        tid = self._by_name.get(name)
        if not tid:
            return
        tool = self._tools[tid]
        tool.call_count += 1
        if not success:
            tool.error_count += 1
        # Update reliability (EMA)
        tool.reliability_score = tool.reliability_score * 0.95 + (1.0 if success else 0.0) * 0.05

        self._hourly_calls.setdefault(name, []).append(time.time())

    def discover_for_role(self, role: str) -> list[ToolRecord]:
        """Discover tools available for a given agent role."""
        return [
            t
            for t in self._tools.values()
            if t.available and (not t.supported_roles or role in t.supported_roles)
        ]

    def discover_by_capability(self, capability: str) -> list[ToolRecord]:
        cap = capability.lower()
        return [
            t
            for t in self._tools.values()
            if t.available and any(cap in c.lower() for c in t.capabilities)
        ]

    def get_by_name(self, name: str) -> ToolRecord | None:
        tid = self._by_name.get(name)
        return self._tools.get(tid) if tid else None

    def get_all(self) -> list[dict]:
        return [t.to_dict() for t in self._tools.values()]

    def get_stats(self) -> dict:
        available = [t for t in self._tools.values() if t.available]
        return {
            "total_tools": len(self._tools),
            "available": len(available),
            "total_calls": sum(t.call_count for t in self._tools.values()),
            "total_errors": sum(t.error_count for t in self._tools.values()),
        }
