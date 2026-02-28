import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class NodeRole(str, Enum):
    BRAIN = "brain"
    CODE_INTEL = "code_intel"
    RESEARCH = "research"
    TRAINING = "training"


class NodeHealth(BaseModel):
    is_online: bool = True
    gpu_load: float = 0.0
    queue_size: int = 0
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)


class NodeRegistration(BaseModel):
    node_id: str
    host: str
    port: int
    role: NodeRole
    models: List[str] = Field(default_factory=list)
    health: NodeHealth = Field(default_factory=NodeHealth)


class NodeManager:
    """Tracks and coordinates machines across the distributed swarm."""

    def __init__(self, heartbeat_timeout_seconds: int = 30):
        self.nodes: Dict[str, NodeRegistration] = {}
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background monitor to prune dead nodes."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("NodeManager health monitor started.")

    async def stop(self):
        """Stop the background monitor."""
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
            logger.info("NodeManager health monitor stopped.")

    async def _monitor_loop(self):
        while True:
            try:
                self.check_health()
                await asyncio.sleep(self.heartbeat_timeout / 2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in NodeManager monitor: {e}")

    def register_node(self, registration: NodeRegistration) -> dict:
        self.nodes[registration.node_id] = registration
        logger.info(
            f"Registered new node: {registration.node_id} (Role: {registration.role}, Host: {registration.host}:{registration.port})"
        )
        return {"status": "success", "message": f"Node {registration.node_id} registered."}

    def deregister_node(self, node_id: str) -> dict:
        if node_id in self.nodes:
            del self.nodes[node_id]
            logger.info(f"Deregistered node: {node_id}")
            return {"status": "success", "message": f"Node {node_id} deregistered."}
        return {"status": "error", "message": f"Node {node_id} not found."}

    def heartbeat(self, node_id: str, gpu_load: float, queue_size: int) -> dict:
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.health.is_online = True
            node.health.gpu_load = gpu_load
            node.health.queue_size = queue_size
            node.health.last_heartbeat = datetime.utcnow()
            logger.debug(f"Heartbeat from {node_id}: Load {gpu_load}, Queue {queue_size}")
            return {"status": "success", "message": "Heartbeat updated."}
        else:
            return {"status": "error", "message": f"Unregistered node: {node_id}"}

    def check_health(self):
        """Mark nodes offline if they haven't sent a heartbeat within the timeout."""
        now = datetime.utcnow()
        for node_id, node in self.nodes.items():
            if node.health.is_online:
                delta = (now - node.health.last_heartbeat).total_seconds()
                if delta > self.heartbeat_timeout:
                    node.health.is_online = False
                    logger.warning(f"Node {node_id} marked OFFLINE (No heartbeat in {delta:.1f}s)")

    def get_available_nodes(self, role: Optional[NodeRole] = None) -> List[NodeRegistration]:
        """Return all online nodes, optionally filtered by role, sorted by queue size."""
        online = [n for n in self.nodes.values() if n.health.is_online]
        if role:
            online = [n for n in online if n.role == role]

        # Sort by queue size (least busy first)
        return sorted(online, key=lambda n: n.health.queue_size)

    def route_task(
        self, role: NodeRole, required_model: Optional[str] = None
    ) -> Optional[NodeRegistration]:
        """Find the best node for a task based on role, models available, and load."""
        candidates = self.get_available_nodes(role=role)

        if required_model:
            candidates = [c for c in candidates if required_model in c.models]

        if candidates:
            # Pick the one with the smallest queue
            best_node = candidates[0]
            logger.info(f"Task routed to node {best_node.node_id} (Role: {role})")
            return best_node

        logger.warning(f"No suitable nodes found for role {role} and model {required_model}")
        return None
