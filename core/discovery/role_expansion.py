"""
DISC-311 — Adaptive Role Expansion.

Allows the swarm to expand role categories when new capability
types emerge. Dynamically creates roles and assigns agents
based on skill compatibility.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.discovery.role_expansion")


@dataclass
class SwarmRole:
    """A role in the swarm taxonomy."""

    role_id: str = field(default_factory=lambda: f"role_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    required_skills: list[str] = field(default_factory=list)
    tool_access: list[str] = field(default_factory=list)
    auto_created: bool = False
    created_at: float = field(default_factory=time.time)
    agent_count: int = 0

    def to_dict(self) -> dict:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "description": self.description,
            "required_skills": self.required_skills,
            "auto_created": self.auto_created,
            "agent_count": self.agent_count,
        }


class RoleExpansion:
    """Manages dynamic role creation and agent assignment."""

    # Base roles that always exist
    BASE_ROLES = ["Researcher", "Analyst", "Creative Coder", "Communicator", "Explorer"]

    def __init__(self):
        self._roles: dict[str, SwarmRole] = {}
        # Initialize base roles
        for name in self.BASE_ROLES:
            role = SwarmRole(name=name, description=f"Core swarm role: {name}")
            self._roles[role.role_id] = role

    def create_role(
        self,
        name: str,
        description: str,
        required_skills: list[str] | None = None,
        tool_access: list[str] | None = None,
    ) -> SwarmRole:
        """Create a new role if it doesn't already exist."""
        existing = self.get_by_name(name)
        if existing:
            return existing

        role = SwarmRole(
            name=name,
            description=description,
            required_skills=required_skills or [],
            tool_access=tool_access or [],
            auto_created=True,
        )
        self._roles[role.role_id] = role
        logger.info("role_created name=%s auto=True skills=%s", name, required_skills)
        return role

    def create_from_capability(
        self, capability_name: str, tools: list[str], scope: list[str]
    ) -> SwarmRole:
        """Auto-create a role from a discovered capability."""
        role_name = capability_name.replace("_", " ").title()
        return self.create_role(
            name=role_name,
            description=f"Auto-created role for capability: {capability_name}",
            required_skills=scope,
            tool_access=tools,
        )

    def find_compatible_role(self, agent_skills: list[str]) -> SwarmRole | None:
        """Find the best matching role for an agent's skill set."""
        best_match: SwarmRole | None = None
        best_score = 0.0

        for role in self._roles.values():
            if not role.required_skills:
                continue
            skill_set = set(s.lower() for s in agent_skills)
            required = set(s.lower() for s in role.required_skills)
            overlap = len(skill_set & required)
            score = overlap / max(1, len(required))
            if score > best_score:
                best_score = score
                best_match = role

        return best_match if best_score >= 0.3 else None

    def assign_agent(self, role_name: str) -> None:
        role = self.get_by_name(role_name)
        if role:
            role.agent_count += 1

    def remove_agent(self, role_name: str) -> None:
        role = self.get_by_name(role_name)
        if role:
            role.agent_count = max(0, role.agent_count - 1)

    def get_by_name(self, name: str) -> SwarmRole | None:
        for role in self._roles.values():
            if role.name.lower() == name.lower():
                return role
        return None

    def get_all(self) -> list[dict]:
        return [r.to_dict() for r in self._roles.values()]

    def get_auto_created(self) -> list[SwarmRole]:
        return [r for r in self._roles.values() if r.auto_created]

    def get_stats(self) -> dict:
        auto = [r for r in self._roles.values() if r.auto_created]
        return {
            "total_roles": len(self._roles),
            "base_roles": len(self.BASE_ROLES),
            "auto_created": len(auto),
            "total_agents": sum(r.agent_count for r in self._roles.values()),
        }
