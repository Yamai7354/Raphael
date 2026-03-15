"""
ClusterRouter — Multi-cluster habitat deployment.

Supports routing tasks to:
  - Local workstation (k3d, development)
  - GPU server (dedicated inference)
  - Cloud burst (overflow / heavy compute)

Selection criteria:
  - Task complexity (simple → local, heavy → GPU/cloud)
  - Resource requirements (GPU → GPU cluster)
  - Cost optimization (prefer local, burst to cloud)
  - Current utilization
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("director.cluster_router")


class ClusterType(Enum):
    LOCAL = "local"
    GPU = "gpu"
    CLOUD = "cloud"


@dataclass
class ClusterConfig:
    """Configuration for a Kubernetes cluster."""

    name: str
    cluster_type: ClusterType
    kubeconfig_path: str
    namespace: str = "habitats"
    max_concurrent_habitats: int = 5
    cost_per_hour: float = 0.0  # local = free, cloud = $$
    has_gpu: bool = False
    gpu_vram_gb: int = 0
    current_habitats: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def available_capacity(self) -> int:
        return self.max_concurrent_habitats - self.current_habitats

    @property
    def utilization(self) -> float:
        return self.current_habitats / max(self.max_concurrent_habitats, 1)


class ClusterRouter:
    """
    Routes habitat deployments to the optimal cluster.

    Priority order:
      1. GPU clusters for GPU-required tasks
      2. Local cluster for development/simple tasks
      3. Cloud burst for overflow or heavy workloads
    """

    # Complexity thresholds for routing decisions
    CLOUD_COMPLEXITY_THRESHOLD = 8  # priority 1-3 = heavy
    LOCAL_CAPACITY_RESERVE = 1  # keep 1 slot free on local

    def __init__(self):
        self._clusters: dict[str, ClusterConfig] = {}

    def register_cluster(self, config: ClusterConfig):
        """Register a cluster for habitat routing."""
        self._clusters[config.name] = config
        logger.info(
            f"Registered cluster '{config.name}' "
            f"(type={config.cluster_type.value}, "
            f"capacity={config.max_concurrent_habitats})"
        )

    def unregister_cluster(self, name: str):
        """Remove a cluster from the routing pool."""
        self._clusters.pop(name, None)

    def select_cluster(
        self,
        needs_gpu: bool = False,
        task_priority: int = 5,
        preferred_type: ClusterType | None = None,
    ) -> ClusterConfig | None:
        """
        Select the best cluster for a task.

        Args:
            needs_gpu: Whether the task requires GPU resources
            task_priority: 1 (highest) to 10 (lowest)
            preferred_type: Optional preferred cluster type
        """
        candidates = list(self._clusters.values())

        if not candidates:
            logger.warning("No clusters registered")
            return None

        # Filter: GPU requirement
        if needs_gpu:
            candidates = [c for c in candidates if c.has_gpu]
            if not candidates:
                logger.warning("No GPU clusters available")
                return None

        # Filter: capacity
        candidates = [c for c in candidates if c.available_capacity > 0]
        if not candidates:
            logger.warning("All clusters at capacity")
            return None

        # Preferred type gets priority
        if preferred_type:
            preferred = [c for c in candidates if c.cluster_type == preferred_type]
            if preferred:
                candidates = preferred

        # Score each candidate
        scored = []
        for cluster in candidates:
            score = self._score_cluster(cluster, task_priority, needs_gpu)
            scored.append((score, cluster))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        logger.info(
            f"Selected cluster '{best.name}' for task (gpu={needs_gpu}, priority={task_priority})"
        )
        return best

    def _score_cluster(self, cluster: ClusterConfig, priority: int, needs_gpu: bool) -> float:
        """Score a cluster (higher = better)."""
        score = 0.0

        # Prefer local (free) over cloud (expensive)
        if cluster.cluster_type == ClusterType.LOCAL:
            score += 50.0
        elif cluster.cluster_type == ClusterType.GPU:
            score += 40.0
        else:  # CLOUD
            score += 10.0

        # Capacity bonus
        score += cluster.available_capacity * 5.0

        # Cost penalty (cloud costs money)
        score -= cluster.cost_per_hour * 10.0

        # GPU match bonus
        if needs_gpu and cluster.has_gpu:
            score += 30.0 + (cluster.gpu_vram_gb * 0.5)

        # High-priority tasks get cloud boost (faster)
        if priority <= 3 and cluster.cluster_type == ClusterType.CLOUD:
            score += 20.0

        # Utilization penalty (prefer less loaded clusters)
        score -= cluster.utilization * 15.0

        return round(score, 2)

    def record_deployment(self, cluster_name: str):
        """Record that a habitat was deployed to a cluster."""
        if cluster_name in self._clusters:
            self._clusters[cluster_name].current_habitats += 1

    def record_removal(self, cluster_name: str):
        """Record that a habitat was removed from a cluster."""
        if cluster_name in self._clusters:
            self._clusters[cluster_name].current_habitats = max(
                0, self._clusters[cluster_name].current_habitats - 1
            )

    @property
    def cluster_summary(self) -> list[dict]:
        """Return a summary of all registered clusters."""
        return [
            {
                "name": c.name,
                "type": c.cluster_type.value,
                "capacity": f"{c.current_habitats}/{c.max_concurrent_habitats}",
                "utilization": f"{c.utilization:.0%}",
                "gpu": c.has_gpu,
                "cost": f"${c.cost_per_hour}/hr",
            }
            for c in self._clusters.values()
        ]
