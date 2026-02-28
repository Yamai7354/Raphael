"""
Node Metrics Collection for AI Router.

Tracks per-node health, latency, and resource usage.
Metrics influence routing decisions and support monitoring.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from statistics import mean, quantiles

logger = logging.getLogger("ai_router.metrics")


# =============================================================================
# LATENCY STATS
# =============================================================================


@dataclass
class LatencyStats:
    """Latency statistics with percentiles."""

    samples: List[float] = field(default_factory=list)
    max_samples: int = 100

    def record(self, latency_ms: float) -> None:
        """Record a latency sample."""
        self.samples.append(latency_ms)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples :]

    def p50(self) -> float:
        """Get 50th percentile (median)."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = len(sorted_samples) // 2
        return sorted_samples[idx]

    def p95(self) -> float:
        """Get 95th percentile."""
        if len(self.samples) < 2:
            return self.samples[0] if self.samples else 0.0
        try:
            return quantiles(self.samples, n=20)[18]  # 95th percentile
        except Exception:
            return max(self.samples)

    def p99(self) -> float:
        """Get 99th percentile."""
        if len(self.samples) < 2:
            return self.samples[0] if self.samples else 0.0
        try:
            return quantiles(self.samples, n=100)[98]  # 99th percentile
        except Exception:
            return max(self.samples)

    def avg(self) -> float:
        """Get average latency."""
        return mean(self.samples) if self.samples else 0.0

    def to_dict(self) -> Dict:
        return {
            "count": len(self.samples),
            "avg_ms": round(self.avg(), 2),
            "p50_ms": round(self.p50(), 2),
            "p95_ms": round(self.p95(), 2),
            "p99_ms": round(self.p99(), 2),
        }


# =============================================================================
# NODE METRICS
# =============================================================================


@dataclass
class NodeMetrics:
    """Metrics for a single node."""

    node_id: str

    # Health
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0

    # Resource usage (updated from node reports)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0

    # Latency
    latency_stats: LatencyStats = field(default_factory=LatencyStats)

    # Throughput
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0

    def record_request(
        self,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record a completed request."""
        self.requests_total += 1
        if success:
            self.requests_success += 1
            self.consecutive_failures = 0
        else:
            self.requests_failed += 1
            self.consecutive_failures += 1

        self.latency_stats.record(latency_ms)

    def update_resources(
        self,
        cpu_percent: float = 0.0,
        memory_percent: float = 0.0,
        vram_used_mb: float = 0.0,
        vram_total_mb: float = 0.0,
    ) -> None:
        """Update resource usage from node report."""
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent
        self.vram_used_mb = vram_used_mb
        self.vram_total_mb = vram_total_mb
        self.last_health_check = datetime.now()

    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.requests_total == 0:
            return 100.0
        return 100.0 * self.requests_success / self.requests_total

    def vram_usage_percent(self) -> float:
        """Get VRAM usage as percentage."""
        if self.vram_total_mb == 0:
            return 0.0
        return 100.0 * self.vram_used_mb / self.vram_total_mb

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "is_healthy": self.is_healthy,
            "last_health_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
            "consecutive_failures": self.consecutive_failures,
            "resources": {
                "cpu_percent": round(self.cpu_percent, 1),
                "memory_percent": round(self.memory_percent, 1),
                "vram_used_mb": round(self.vram_used_mb, 1),
                "vram_total_mb": round(self.vram_total_mb, 1),
                "vram_usage_percent": round(self.vram_usage_percent(), 1),
            },
            "latency": self.latency_stats.to_dict(),
            "throughput": {
                "total": self.requests_total,
                "success": self.requests_success,
                "failed": self.requests_failed,
                "success_rate": round(self.success_rate(), 2),
            },
        }


# =============================================================================
# METRICS REGISTRY
# =============================================================================


class MetricsRegistry:
    """Central registry for all node metrics."""

    def __init__(self):
        self._nodes: Dict[str, NodeMetrics] = {}
        self._role_latency: Dict[str, LatencyStats] = {}

    def get_node(self, node_id: str) -> NodeMetrics:
        """Get or create metrics for a node."""
        if node_id not in self._nodes:
            self._nodes[node_id] = NodeMetrics(node_id=node_id)
        return self._nodes[node_id]

    def record_request(
        self,
        node_id: str,
        role: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record a request to a node for a role."""
        # Node metrics
        node = self.get_node(node_id)
        node.record_request(success, latency_ms)

        # Role latency
        if role not in self._role_latency:
            self._role_latency[role] = LatencyStats()
        self._role_latency[role].record(latency_ms)

        logger.info(
            "request_recorded node=%s role=%s success=%s latency_ms=%.2f",
            node_id,
            role,
            success,
            latency_ms,
        )

    def update_node_resources(
        self,
        node_id: str,
        cpu_percent: float = 0.0,
        memory_percent: float = 0.0,
        vram_used_mb: float = 0.0,
        vram_total_mb: float = 0.0,
    ) -> None:
        """Update resource metrics from health check."""
        node = self.get_node(node_id)
        node.update_resources(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            vram_used_mb=vram_used_mb,
            vram_total_mb=vram_total_mb,
        )

    def get_all_node_metrics(self) -> Dict[str, Dict]:
        """Get metrics for all nodes."""
        return {node_id: metrics.to_dict() for node_id, metrics in self._nodes.items()}

    def get_role_latency(self) -> Dict[str, Dict]:
        """Get latency stats per role."""
        return {role: stats.to_dict() for role, stats in self._role_latency.items()}

    def get_summary(self) -> Dict:
        """Get aggregate metrics summary."""
        total_requests = sum(n.requests_total for n in self._nodes.values())
        total_success = sum(n.requests_success for n in self._nodes.values())

        all_latencies = []
        for n in self._nodes.values():
            all_latencies.extend(n.latency_stats.samples)

        return {
            "nodes_tracked": len(self._nodes),
            "roles_tracked": len(self._role_latency),
            "total_requests": total_requests,
            "total_success": total_success,
            "overall_success_rate": round(100.0 * total_success / total_requests, 2)
            if total_requests > 0
            else 100.0,
            "avg_latency_ms": round(mean(all_latencies), 2) if all_latencies else 0.0,
        }


# Global singleton
metrics_registry = MetricsRegistry()
