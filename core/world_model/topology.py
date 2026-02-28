"""
WORLD-410 — System Topology Mapping.

Maps network structure and relationships: machine connections,
service dependencies, communication pathways, data pipelines.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.world_model.topology")


@dataclass
class TopologyLink:
    """A connection between two components."""

    link_id: str = field(default_factory=lambda: f"link_{uuid.uuid4().hex[:8]}")
    source: str = ""
    target: str = ""
    link_type: str = "network"  # network, dependency, data_flow, api_call
    latency_ms: float = 0
    bandwidth_mbps: float = 0
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.link_type,
            "latency_ms": round(self.latency_ms, 1),
            "bandwidth_mbps": round(self.bandwidth_mbps, 1),
        }


@dataclass
class TopologyNode:
    """A component in the topology."""

    name: str = ""
    component_type: str = "machine"  # machine, service, database, queue
    properties: dict = field(default_factory=dict)


class TopologyMap:
    """Graph-based topology of system components and their connections."""

    def __init__(self):
        self._nodes: dict[str, TopologyNode] = {}
        self._links: dict[str, TopologyLink] = {}
        self._adjacency: dict[str, set[str]] = {}  # node -> set of neighbor nodes

    def add_node(
        self, name: str, component_type: str = "machine", properties: dict | None = None
    ) -> TopologyNode:
        if name not in self._nodes:
            self._nodes[name] = TopologyNode(
                name=name,
                component_type=component_type,
                properties=properties or {},
            )
            self._adjacency.setdefault(name, set())
        return self._nodes[name]

    def add_link(
        self,
        source: str,
        target: str,
        link_type: str = "network",
        latency_ms: float = 0,
        bandwidth_mbps: float = 0,
        properties: dict | None = None,
    ) -> TopologyLink:
        # Auto-create nodes if needed
        self.add_node(source)
        self.add_node(target)

        link = TopologyLink(
            source=source,
            target=target,
            link_type=link_type,
            latency_ms=latency_ms,
            bandwidth_mbps=bandwidth_mbps,
            properties=properties or {},
        )
        self._links[link.link_id] = link
        self._adjacency[source].add(target)
        self._adjacency[target].add(source)
        return link

    def get_neighbors(self, name: str) -> list[str]:
        return list(self._adjacency.get(name, set()))

    def get_path(self, source: str, target: str) -> list[str] | None:
        """BFS shortest path between two nodes."""
        if source not in self._nodes or target not in self._nodes:
            return None
        visited: set[str] = {source}
        queue: list[list[str]] = [[source]]
        while queue:
            path = queue.pop(0)
            node = path[-1]
            if node == target:
                return path
            for neighbor in self._adjacency.get(node, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def get_dependencies(self, name: str) -> list[str]:
        """Get all services that this component depends on."""
        deps: list[str] = []
        for link in self._links.values():
            if link.source == name and link.link_type == "dependency":
                deps.append(link.target)
        return deps

    def get_data_pipelines(self) -> list[dict]:
        return [l.to_dict() for l in self._links.values() if l.link_type == "data_flow"]

    def get_all_nodes(self) -> list[dict]:
        return [{"name": n.name, "type": n.component_type} for n in self._nodes.values()]

    def get_all_links(self) -> list[dict]:
        return [l.to_dict() for l in self._links.values()]

    def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        for n in self._nodes.values():
            by_type[n.component_type] = by_type.get(n.component_type, 0) + 1
        return {
            "total_nodes": len(self._nodes),
            "total_links": len(self._links),
            "by_type": by_type,
        }
