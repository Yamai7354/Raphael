"""
WORLD-401 — World Model Core Schema.

Defines the core schema for representing the swarm's environment
within the knowledge graph: machines, GPUs, CPUs, storage, models,
APIs, tools, networks, data sources, and agents.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.world_model.schema")


class NodeType(str, Enum):
    MACHINE = "Machine"
    GPU = "GPU"
    CPU = "CPU"
    STORAGE = "Storage"
    MODEL = "Model"
    API = "API"
    TOOL = "Tool"
    NETWORK = "Network"
    DATA_SOURCE = "DataSource"
    AGENT = "Agent"
    SERVICE = "Service"


class RelType(str, Enum):
    RUNS_ON = "RUNS_ON"  # agent → machine
    REQUIRES_HW = "REQUIRES_HW"  # model → hardware
    USES_RESOURCE = "USES_RESOURCE"  # task → resource
    COMPATIBLE = "COMPATIBLE"  # tool → agent
    CONNECTED_TO = "CONNECTED_TO"  # machine → machine
    HAS_GPU = "HAS_GPU"  # machine → GPU
    HAS_CPU = "HAS_CPU"  # machine → CPU
    HAS_STORAGE = "HAS_STORAGE"  # machine → storage
    HOSTS_MODEL = "HOSTS_MODEL"  # machine → model
    PROVIDES = "PROVIDES"  # service → API
    DEPENDS_ON = "DEPENDS_ON"  # service → service


@dataclass
class WorldNode:
    """A node in the world model graph."""

    node_id: str = field(default_factory=lambda: f"wn_{uuid.uuid4().hex[:8]}")
    node_type: NodeType = NodeType.MACHINE
    name: str = ""
    properties: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "type": self.node_type.value,
            "name": self.name,
            "properties": self.properties,
        }


@dataclass
class WorldRelationship:
    """A relationship in the world model graph."""

    rel_id: str = field(default_factory=lambda: f"wr_{uuid.uuid4().hex[:8]}")
    rel_type: RelType = RelType.CONNECTED_TO
    source_id: str = ""
    target_id: str = ""
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rel_id": self.rel_id,
            "type": self.rel_type.value,
            "source": self.source_id,
            "target": self.target_id,
            "properties": self.properties,
        }


class WorldModelSchema:
    """Core schema manager for the world model graph."""

    def __init__(self):
        self._nodes: dict[str, WorldNode] = {}
        self._relationships: dict[str, WorldRelationship] = {}
        self._by_type: dict[NodeType, list[str]] = {t: [] for t in NodeType}
        self._by_name: dict[str, str] = {}

    def add_node(self, node_type: NodeType, name: str, properties: dict | None = None) -> WorldNode:
        """Add a node to the world model."""
        if name in self._by_name:
            existing = self._nodes[self._by_name[name]]
            existing.properties.update(properties or {})
            existing.updated_at = time.time()
            return existing

        node = WorldNode(node_type=node_type, name=name, properties=properties or {})
        self._nodes[node.node_id] = node
        self._by_type[node_type].append(node.node_id)
        self._by_name[name] = node.node_id
        return node

    def add_relationship(
        self, rel_type: RelType, source_name: str, target_name: str, properties: dict | None = None
    ) -> WorldRelationship | None:
        src = self._by_name.get(source_name)
        tgt = self._by_name.get(target_name)
        if not src or not tgt:
            return None

        rel = WorldRelationship(
            rel_type=rel_type,
            source_id=src,
            target_id=tgt,
            properties=properties or {},
        )
        self._relationships[rel.rel_id] = rel
        return rel

    def get_node(self, name: str) -> WorldNode | None:
        nid = self._by_name.get(name)
        return self._nodes.get(nid) if nid else None

    def get_by_type(self, node_type: NodeType) -> list[WorldNode]:
        return [self._nodes[nid] for nid in self._by_type.get(node_type, []) if nid in self._nodes]

    def get_relationships_for(self, name: str) -> list[WorldRelationship]:
        nid = self._by_name.get(name)
        if not nid:
            return []
        return [r for r in self._relationships.values() if r.source_id == nid or r.target_id == nid]

    def get_neighbors(self, name: str) -> list[WorldNode]:
        nid = self._by_name.get(name)
        if not nid:
            return []
        neighbor_ids: set[str] = set()
        for r in self._relationships.values():
            if r.source_id == nid:
                neighbor_ids.add(r.target_id)
            elif r.target_id == nid:
                neighbor_ids.add(r.source_id)
        return [self._nodes[n] for n in neighbor_ids if n in self._nodes]

    def remove_node(self, name: str) -> None:
        nid = self._by_name.pop(name, None)
        if not nid:
            return
        node = self._nodes.pop(nid, None)
        if node:
            self._by_type[node.node_type] = [i for i in self._by_type[node.node_type] if i != nid]
        self._relationships = {
            k: v
            for k, v in self._relationships.items()
            if v.source_id != nid and v.target_id != nid
        }

    def get_all_nodes(self) -> list[dict]:
        return [n.to_dict() for n in self._nodes.values()]

    def get_all_relationships(self) -> list[dict]:
        return [r.to_dict() for r in self._relationships.values()]

    def get_stats(self) -> dict:
        by_type = {t.value: len(ids) for t, ids in self._by_type.items() if ids}
        return {
            "total_nodes": len(self._nodes),
            "total_relationships": len(self._relationships),
            "by_type": by_type,
        }
