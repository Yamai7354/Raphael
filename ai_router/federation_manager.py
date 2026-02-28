"""
Federation Manager for AI Router (Phase 11).

Manages registration, discovery, and health monitoring of federated clusters.
Enables multi-cluster coordination.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger("ai_router.federation")


@dataclass
class FederatedCluster:
    """Represents a remote cluster in the federation."""

    cluster_id: str
    endpoint_url: str  # Base URL, e.g., "http://10.0.1.5:9000"
    region: str
    capabilities: Dict
    status: str = "ONLINE"  # ONLINE, OFFLINE, DEGRADED
    last_heartbeat: datetime = field(default_factory=datetime.now)
    latency_ms: float = 0.0

    # Auth token for inter-cluster communication (placeholder)
    auth_token: Optional[str] = None

    def mark_heartbeat(self, latency: float = 0.0):
        self.last_heartbeat = datetime.now()
        self.latency_ms = latency
        self.status = "ONLINE"


class FederationManager:
    """
    Central controller for federation logic.
    """

    def __init__(self, local_cluster_id: str = "cluster-primary"):
        self.local_cluster_id = local_cluster_id
        self._clusters: Dict[str, FederatedCluster] = {}
        self._http_client = httpx.AsyncClient(timeout=5.0)
        self.monitor_task = None
        self.enabled = True

    async def start_monitoring(self):
        """Start the health check background loop."""
        while self.enabled:
            await self._check_health()
            await asyncio.sleep(30)  # Check every 30s

    async def register_cluster(
        self,
        cluster_id: str,
        endpoint_url: str,
        region: str,
        capabilities: Dict,
    ) -> bool:
        """Register a remote cluster."""
        if cluster_id == self.local_cluster_id:
            logger.warning("cannot_register_self cluster_id=%s", cluster_id)
            return False

        cluster = FederatedCluster(
            cluster_id=cluster_id,
            endpoint_url=endpoint_url.rstrip("/"),
            region=region,
            capabilities=capabilities,
        )
        self._clusters[cluster_id] = cluster
        logger.info("cluster_registered id=%s region=%s", cluster_id, region)
        return True

    def get_cluster(self, cluster_id: str) -> Optional[FederatedCluster]:
        return self._clusters.get(cluster_id)

    def get_all_clusters(self) -> List[Dict]:
        return [
            {
                "id": c.cluster_id,
                "status": c.status,
                "region": c.region,
                "latency_ms": c.latency_ms,
                "last_seen": c.last_heartbeat.isoformat(),
            }
            for c in self._clusters.values()
        ]

    async def _check_health(self):
        """Ping all registered clusters."""
        for cid, cluster in self._clusters.items():
            try:
                start = datetime.now()
                # Assuming standard health endpoint exists
                status_url = f"{cluster.endpoint_url}/admin/cluster/status"
                resp = await self._http_client.get(status_url)

                if resp.status_code == 200:
                    latency = (datetime.now() - start).total_seconds() * 1000
                    cluster.mark_heartbeat(latency)
                    logger.debug("cluster_health_check_ok id=%s latency=%.1fms", cid, latency)
                else:
                    self._mark_unhealthy(cluster, f"status_code_{resp.status_code}")

            except Exception as e:
                self._mark_unhealthy(cluster, str(e))

    def _mark_unhealthy(self, cluster: FederatedCluster, reason: str):
        cluster.status = "OFFLINE"
        logger.warning("cluster_health_check_failed id=%s reason=%s", cluster.cluster_id, reason)


# Global singleton
federation_manager = FederationManager()
