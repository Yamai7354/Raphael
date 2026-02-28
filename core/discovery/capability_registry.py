"""
DISC-310 — Agent Capability Registry.

Maintains a registry of all available swarm capabilities and agent types.
Tracks agent class, capabilities, performance metrics, dependencies,
and version history. Searchable by agents.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.discovery.capability_registry")


@dataclass
class CapabilityRecord:
    """A registered swarm capability."""

    capability_id: str = field(default_factory=lambda: f"cap_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    agent_class: str = ""  # which agent type provides this
    performance_metrics: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    version: int = 1
    version_history: list[dict] = field(default_factory=list)
    active: bool = True
    registered_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "agent_class": self.agent_class,
            "performance_metrics": self.performance_metrics,
            "dependencies": self.dependencies,
            "version": self.version,
            "active": self.active,
        }


class CapabilityRegistry:
    """Central registry of all swarm capabilities."""

    def __init__(self):
        self._capabilities: dict[str, CapabilityRecord] = {}
        self._by_name: dict[str, str] = {}  # name -> id
        self._by_agent: dict[str, list[str]] = {}  # agent_class -> [ids]

    def register(
        self, name: str, description: str, agent_class: str, dependencies: list[str] | None = None
    ) -> CapabilityRecord:
        """Register a new capability."""
        if name in self._by_name:
            return self._capabilities[self._by_name[name]]

        cap = CapabilityRecord(
            name=name,
            description=description,
            agent_class=agent_class,
            dependencies=dependencies or [],
        )
        self._capabilities[cap.capability_id] = cap
        self._by_name[name] = cap.capability_id
        self._by_agent.setdefault(agent_class, []).append(cap.capability_id)
        logger.info(
            "capability_registered id=%s name=%s agent=%s", cap.capability_id, name, agent_class
        )
        return cap

    def update_version(self, capability_id: str, changes: str) -> None:
        """Bump version with a changelog entry."""
        cap = self._capabilities.get(capability_id)
        if not cap:
            return
        cap.version_history.append(
            {
                "version": cap.version,
                "changes": changes,
                "timestamp": time.time(),
            }
        )
        cap.version += 1
        cap.updated_at = time.time()

    def update_metrics(self, capability_id: str, metrics: dict) -> None:
        cap = self._capabilities.get(capability_id)
        if cap:
            cap.performance_metrics.update(metrics)
            cap.updated_at = time.time()

    def deactivate(self, capability_id: str) -> None:
        cap = self._capabilities.get(capability_id)
        if cap:
            cap.active = False

    def search(self, query: str) -> list[CapabilityRecord]:
        """Search capabilities by name or description."""
        q = query.lower()
        return [
            c
            for c in self._capabilities.values()
            if c.active and (q in c.name.lower() or q in c.description.lower())
        ]

    def get_by_agent(self, agent_class: str) -> list[CapabilityRecord]:
        ids = self._by_agent.get(agent_class, [])
        return [self._capabilities[cid] for cid in ids if cid in self._capabilities]

    def get_by_name(self, name: str) -> CapabilityRecord | None:
        cid = self._by_name.get(name)
        return self._capabilities.get(cid) if cid else None

    def get_all(self) -> list[dict]:
        return [c.to_dict() for c in self._capabilities.values() if c.active]

    def get_stats(self) -> dict:
        active = [c for c in self._capabilities.values() if c.active]
        agents = set(c.agent_class for c in active)
        return {
            "total_capabilities": len(active),
            "agent_classes": len(agents),
            "total_versions": sum(c.version for c in active),
        }
