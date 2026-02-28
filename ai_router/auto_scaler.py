"""
Auto-Scaling Engine for AI Router.

Monitors cluster load and predictive signals to dynamically scale resources.
Triggers node provisioning/deprovisioning managed by ClusterManager.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from .advanced_scheduler import advanced_scheduler
from .load_manager import load_manager
from .predictive_router import predictive_router
from .cluster_manager import cluster_manager
from .node_state import node_state_manager

logger = logging.getLogger("ai_router.autoscaler")


class AutoScaler:
    """
    Decides when to scale the cluster up or down.
    """

    def __init__(self):
        # Configuration
        self.scale_up_threshold_queue = 5  # avg items in queue
        self.scale_up_threshold_load = 0.8  # 80% utilization
        self.scale_down_threshold_load = 0.2  # 20% utilization
        self.cooldown_period = 60  # seconds between scaling events

        self.last_scale_event: Optional[datetime] = None
        self._enabled = True

    async def run_loop(self):
        """Main monitoring loop (to be run as background task)."""
        while self.enabled:
            try:
                await self.check_scaling_needs()
            except Exception as e:
                logger.error("autoscaler_error error=%s", str(e))
            await asyncio.sleep(10)  # Check every 10s

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def check_scaling_needs(self) -> None:
        """Check metrics and trigger scaling if needed."""
        # 0. Cooldown check
        if self.last_scale_event:
            elapsed = (datetime.now() - self.last_scale_event).total_seconds()
            if elapsed < self.cooldown_period:
                return

        # 1. Reactive Scaling (Ticket 2)
        # Check current queue depth
        stats = advanced_scheduler.get_queue_stats()
        pending_count = stats.get("pending", 0)

        # Check current load
        load_stats = load_manager.get_total_load()
        utilization = load_stats.get("utilization", 0.0)

        if (
            pending_count > self.scale_up_threshold_queue
            or utilization > self.scale_up_threshold_load
        ):
            await self.trigger_scale_up(
                "high_load", {"pending": pending_count, "util": utilization}
            )
            return

        # 2. Predictive Scaling (Ticket 4)
        # Check high-confidence upcoming tasks
        predictions = predictive_router.get_recent_predictions()
        if predictions:
            # Analyze last batch of predictions
            last_pred = predictions[-1]  # Simplification
            # If we predict a heavy role transition
            pass  # (Logic would go here to pre-scale specific GPU types)

    async def trigger_scale_up(self, reason: str, metrics: Dict) -> None:
        """Trigger adding a new node."""
        logger.info("scale_up_triggered reason=%s metrics=%s", reason, metrics)
        self.last_scale_event = datetime.now()

        # In a real system, this would call AWS/K8s API.
        # Here we simulate dynamic registration of a "cloud-burst" node.
        new_node_id = f"cloud-node-{int(datetime.now().timestamp())}"

        # Mocking external provisioner delay
        await asyncio.sleep(1)

        cluster_manager.register_node(
            node_id=new_node_id,
            capabilities={
                "vram_gb": 24,
                "max_context_length": 32768,
                "supported_model_sizes": ["7B", "13B"],
            },
        )

        # Rebalance (Ticket 3)
        await self.rebalance_tasks()

    async def rebalance_tasks(self) -> None:
        """
        Redistribute pending tasks to newly available nodes.
        """
        # AdvancedScheduler mostly handles this automatically because
        # get_next_runnable checks *all* available nodes.
        # So essentially, just by registering the node, the next schedule cycle
        # will pick it up.
        # However, we can log the event.
        logger.info("rebalancing_triggered actions=scheduler_updated_implicitly")


# Global singleton
auto_scaler = AutoScaler()
