"""
Adaptive Policy Engine for AI Router (Phase 12).

Analyzes metrics and suggests/applies policy changes for:
- Scheduler (prioritization, concurrency)
- Auto-Scaler (thresholds)
- Federation (routing)
"""

import logging
import asyncio
from typing import Dict, Any

from .policy_manager import policy_manager
from .auto_scaler import auto_scaler
from .federation_router import federation_router

logger = logging.getLogger("ai_router.adaptive_engine")


class AdaptivePolicyEngine:
    """
    Central brain for adapting system policies based on metrics.
    """

    def __init__(self):
        self.enabled = True
        self.check_interval = 60  # seconds

    async def run_loop(self):
        """Analyze metrics and adapt policies."""
        while self.enabled:
            await self._analyze_and_adapt()
            await asyncio.sleep(self.check_interval)

    async def _analyze_and_adapt(self):
        """Core logic for adaptation."""
        # 1. Get recent trends
        trends = policy_manager.metrics.get_trend(window_minutes=5)
        if not trends:
            return

        avg_latency = trends.get("avg_latency", 0)
        avg_success = trends.get("avg_success", 1.0)

        current_policy = policy_manager.current_policy
        changes = {}

        # 2. Adaptive Scheduler Logic (Ticket 2)
        # If success rate is low, reduce concurrency to reduce contention
        if avg_success < 0.95:
            new_conc = max(1, current_policy.max_concurrent_tasks - 1)
            if new_conc != current_policy.max_concurrent_tasks:
                changes["max_concurrent_tasks"] = new_conc
                logger.info(
                    "adapting_scheduler reason=low_success new_concurrency=%d", new_conc
                )
        # If success high but latency acceptable, maybe increase concurrency
        elif avg_success > 0.99 and avg_latency < 200:
            new_conc = min(50, current_policy.max_concurrent_tasks + 1)
            if new_conc != current_policy.max_concurrent_tasks:
                changes["max_concurrent_tasks"] = new_conc
                logger.info(
                    "adapting_scheduler reason=high_performance new_concurrency=%d",
                    new_conc,
                )

        # 3. Dynamic Scaling Logic (Ticket 3)
        # If latency is high, lower the queue threshold to trigger scaling sooner
        if avg_latency > 1000:
            new_threshold = max(2, current_policy.scale_up_threshold_queue - 1)
            if new_threshold != current_policy.scale_up_threshold_queue:
                changes["scale_up_threshold_queue"] = new_threshold
                # Apply to live component
                auto_scaler.scale_up_threshold_queue = new_threshold
                logger.info(
                    "adapting_scaler reason=high_latency new_threshold=%d",
                    new_threshold,
                )

        # 4. Federation Logic (Ticket 4)
        # If local is struggling (high latency), lower offload threshold to send more away
        if avg_latency > 500:
            new_offload = max(5, current_policy.offload_queue_threshold - 2)
            if new_offload != current_policy.offload_queue_threshold:
                changes["offload_queue_threshold"] = new_offload
                # Apply to live component
                federation_router.offload_queue_threshold = new_offload
                logger.info(
                    "adapting_federation reason=latency new_offload=%d", new_offload
                )

        # 5. Apply changes via PolicyManager
        if changes:
            policy_manager.propose_change(changes)


# Global singleton
adaptive_engine = AdaptivePolicyEngine()
