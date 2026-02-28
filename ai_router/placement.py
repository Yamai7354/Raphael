"""
Runtime Placement State for AI Router.

Tracks which role/model combo is active on which node.
The router is the sole authority for placement state.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger("ai_router.placement")


class PlacementStatus(str, Enum):
    """Status of a role placement on a node."""

    LOADING = "loading"  # Model is being loaded
    READY = "ready"  # Model loaded and ready for inference
    DRAINING = "draining"  # No new requests, finishing existing ones
    UNLOADING = "unloading"  # Model is being unloaded


@dataclass
class RolePlacement:
    """
    Represents one role/model combo active on a node.
    """

    role_id: str
    model_id: str
    node_id: str
    status: PlacementStatus = PlacementStatus.LOADING
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)

    def mark_ready(self) -> None:
        """Mark the placement as ready for inference."""
        self.status = PlacementStatus.READY
        logger.info(
            "placement_ready role=%s model=%s node=%s",
            self.role_id,
            self.model_id,
            self.node_id,
        )

    def mark_draining(self) -> None:
        """Mark the placement as draining (no new requests)."""
        self.status = PlacementStatus.DRAINING
        logger.info(
            "placement_draining role=%s model=%s node=%s",
            self.role_id,
            self.model_id,
            self.node_id,
        )

    def touch(self) -> None:
        """Update last_used timestamp."""
        self.last_used = datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "role_id": self.role_id,
            "model_id": self.model_id,
            "node_id": self.node_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
        }


class PlacementRegistry:
    """
    Authoritative registry of all role placements.
    The router is the sole authority for this state.
    """

    def __init__(self):
        # Key: (node_id, role_id) -> RolePlacement
        self._placements: Dict[tuple, RolePlacement] = {}
        # Track exclusive roles per node (for concurrent_role_limit)
        self._node_roles: Dict[str, List[str]] = {}

    def create_placement(
        self, role_id: str, model_id: str, node_id: str
    ) -> RolePlacement:
        """
        Create a new placement. Fails if role already placed on node.
        """
        key = (node_id, role_id)
        if key in self._placements:
            existing = self._placements[key]
            if existing.status != PlacementStatus.DRAINING:
                raise ValueError(
                    f"Role {role_id} already placed on {node_id} with status {existing.status}"
                )

        placement = RolePlacement(
            role_id=role_id,
            model_id=model_id,
            node_id=node_id,
        )
        self._placements[key] = placement

        # Track on node
        if node_id not in self._node_roles:
            self._node_roles[node_id] = []
        if role_id not in self._node_roles[node_id]:
            self._node_roles[node_id].append(role_id)

        logger.info(
            "placement_created role=%s model=%s node=%s", role_id, model_id, node_id
        )
        return placement

    def get_placement(self, node_id: str, role_id: str) -> Optional[RolePlacement]:
        """Get a specific placement."""
        return self._placements.get((node_id, role_id))

    def get_placements_for_node(self, node_id: str) -> List[RolePlacement]:
        """Get all placements on a node."""
        return [p for (nid, _), p in self._placements.items() if nid == node_id]

    def get_placements_for_role(self, role_id: str) -> List[RolePlacement]:
        """Get all placements for a role across all nodes."""
        return [p for (_, rid), p in self._placements.items() if rid == role_id]

    def get_ready_placement_for_role(self, role_id: str) -> Optional[RolePlacement]:
        """Get a READY placement for a role (first available)."""
        for placement in self.get_placements_for_role(role_id):
            if placement.status == PlacementStatus.READY:
                return placement
        return None

    def remove_placement(self, node_id: str, role_id: str) -> bool:
        """Remove a placement. Returns True if removed."""
        key = (node_id, role_id)
        if key in self._placements:
            del self._placements[key]
            if node_id in self._node_roles and role_id in self._node_roles[node_id]:
                self._node_roles[node_id].remove(role_id)
            logger.info("placement_removed role=%s node=%s", role_id, node_id)
            return True
        return False

    def get_node_role_count(self, node_id: str) -> int:
        """Get number of roles currently on a node."""
        return len(self._node_roles.get(node_id, []))

    def to_dict(self) -> Dict:
        """Convert all placements to dictionary."""
        result = {}
        for (node_id, role_id), placement in self._placements.items():
            if node_id not in result:
                result[node_id] = {}
            result[node_id][role_id] = placement.to_dict()
        return result


# Global singleton instance
placement_registry = PlacementRegistry()
