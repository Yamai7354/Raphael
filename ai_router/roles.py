"""
Agent Role Schema for AI Router.

Defines the formal schema for agent roles. Roles are the primary
scheduling unit - clients request roles, not models.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

logger = logging.getLogger("ai_router.roles")


class QuantizationPolicy(str, Enum):
    """Allowed quantization levels for a role."""

    ANY = "any"  # No restriction
    Q4_ONLY = "q4_only"  # 4-bit only (smallest)
    Q8_ONLY = "q8_only"  # 8-bit only
    FP16_ONLY = "fp16_only"  # Half precision
    Q8_OR_HIGHER = "q8_or_higher"  # 8-bit or better


@dataclass(frozen=True)
class AgentRole:
    """
    Immutable definition of an agent role.
    Roles are loaded at startup and cannot be modified at runtime.
    """

    role_id: str
    description: str
    max_context_tokens: int
    preferred_model_size_max: str  # e.g., "7B", "13B", "70B"
    quantization_policy: QuantizationPolicy = QuantizationPolicy.ANY
    default_temperature: float = 0.7
    latency_sensitive: bool = False

    def __post_init__(self):
        """Validate role configuration."""
        if not self.role_id:
            raise ValueError("role_id cannot be empty")
        if self.max_context_tokens <= 0:
            raise ValueError(
                f"max_context_tokens must be positive, got {self.max_context_tokens}"
            )
        if not 0.0 <= self.default_temperature <= 2.0:
            raise ValueError(
                f"default_temperature must be 0.0-2.0, got {self.default_temperature}"
            )


class RoleRegistry:
    """
    Registry of all configured agent roles.
    Roles are loaded once at startup and are immutable.
    """

    def __init__(self):
        self._roles: dict[str, AgentRole] = {}
        self._loaded = False

    def load_from_config(self, roles_config: List[dict]) -> None:
        """
        Load roles from configuration.
        Fails fast on any invalid role.
        """
        if self._loaded:
            raise RuntimeError("Roles already loaded. Registry is immutable.")

        for role_data in roles_config:
            try:
                # Parse quantization policy
                quant_str = role_data.get("quantization_policy", "any")
                try:
                    quant_policy = QuantizationPolicy(quant_str)
                except ValueError:
                    raise ValueError(f"Invalid quantization_policy: {quant_str}")

                role = AgentRole(
                    role_id=role_data["role_id"],
                    description=role_data.get("description", ""),
                    max_context_tokens=role_data["max_context_tokens"],
                    preferred_model_size_max=role_data.get(
                        "preferred_model_size_max", "7B"
                    ),
                    quantization_policy=quant_policy,
                    default_temperature=role_data.get("default_temperature", 0.7),
                    latency_sensitive=role_data.get("latency_sensitive", False),
                )

                if role.role_id in self._roles:
                    raise ValueError(f"Duplicate role_id: {role.role_id}")

                self._roles[role.role_id] = role
                logger.info(
                    "role_loaded role_id=%s max_context=%d latency_sensitive=%s",
                    role.role_id,
                    role.max_context_tokens,
                    role.latency_sensitive,
                )

            except KeyError as e:
                raise ValueError(f"Missing required field in role config: {e}")
            except Exception as e:
                raise ValueError(f"Invalid role configuration: {e}")

        self._loaded = True
        logger.info("role_registry_loaded total_roles=%d", len(self._roles))

    def get_role(self, role_id: str) -> Optional[AgentRole]:
        """Get a role by ID, or None if not found."""
        return self._roles.get(role_id)

    def get_all_roles(self) -> dict[str, AgentRole]:
        """Return all registered roles (read-only view)."""
        return dict(self._roles)

    def list_role_ids(self) -> List[str]:
        """Return list of all role IDs."""
        return list(self._roles.keys())

    def is_loaded(self) -> bool:
        """Check if roles have been loaded."""
        return self._loaded


# Global singleton instance
role_registry = RoleRegistry()
