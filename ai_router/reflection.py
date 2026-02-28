"""
Performance Reflection Engine for AI Router.

Performs deep analysis of historical execution data from SQLite memory
to identify bottlenecks and suggest strategic optimizations.
"""

# Reflection system for Phase 7
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .database import db_manager
from .bus import event_bus
from event_bus.event_bus import Event

logger = logging.getLogger("ai_router.reflection")


@dataclass
class OptimizationSuggestion:
    type: str  # 'policy', 'role', 'node'
    target: str
    action: str
    reason: str
    priority: int  # 1-10


class PerformanceReflectionEngine:
    def __init__(self, interval_hours: int = 1):
        self.interval_hours = interval_hours
        self.is_running = False
        self._last_analysis: Optional[datetime] = None

    async def start(self):
        """Start the background reflection loop."""
        if self.is_running:
            return
        self.is_running = True
        logger.info("PerformanceReflectionEngine started.")
        asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the reflection loop."""
        self.is_running = False
        logger.info("PerformanceReflectionEngine stopped.")

    async def _run_loop(self):
        while self.is_running:
            try:
                await self.run_reflection()
                self._last_analysis = datetime.now()
            except Exception as e:
                logger.error(f"Error in reflection loop: {e}")

            await asyncio.sleep(self.interval_hours * 3600)

    async def run_reflection(self) -> Dict[str, Any]:
        """Perform a full reflection cycle."""
        logger.info("Starting performance reflection cycle...")

        # 1. Analyze Task Success Rates
        success_stats = await self._analyze_success_rates()

        # 2. Analyze Latency Trends
        latency_stats = await self._analyze_latency()

        # 3. Generate Suggestions
        suggestions = self._generate_suggestions(success_stats, latency_stats)

        # 4. Save and Publish Report
        report = {
            "timestamp": datetime.now().isoformat(),
            "success_stats": success_stats,
            "latency_stats": latency_stats,
            "suggestions": [asdict(s) for s in suggestions],
        }

        await self._publish_report(report)
        return report

    async def _analyze_success_rates(self) -> List[Dict[str, Any]]:
        """Query SQLite for success rates per role and status."""
        query = """
            SELECT status, count(*) as count
            FROM tasks
            WHERE created_at > ?
            GROUP BY status
        """
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        rows = await db_manager.fetch_all(query, (yesterday,))
        return [dict(r) for r in rows]

    async def _analyze_latency(self) -> List[Dict[str, Any]]:
        """Query events for latency-related topics."""
        # This is a simplified query; in production we'd correlate task events
        query = """
            SELECT topic, count(*) as count
            FROM events
            WHERE topic LIKE 'task.%' AND timestamp > ?
            GROUP BY topic
        """
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        rows = await db_manager.fetch_all(query, (yesterday,))
        return [dict(r) for r in rows]

    def _generate_suggestions(
        self, success: List[Dict], latency: List[Dict]
    ) -> List[OptimizationSuggestion]:
        """Heuristic-based suggestion generation."""
        suggestions = []

        # Find failure count
        failed_count = next((r["count"] for r in success if r["status"] == "FAILED"), 0)
        total_count = sum(r["count"] for r in success)

        if total_count > 0 and (failed_count / total_count) > 0.1:
            suggestions.append(
                OptimizationSuggestion(
                    type="policy",
                    target="strict_mode",
                    action="RELAX",
                    reason=f"High failure rate ({failed_count}/{total_count}). System may be too strict or nodes unstable.",
                    priority=8,
                )
            )

        # Check for many 'awaiting_approval' events
        awaiting = next(
            (r["count"] for r in latency if r["topic"] == "task.awaiting_approval"), 0
        )
        if awaiting > 5:
            suggestions.append(
                OptimizationSuggestion(
                    type="policy",
                    target="approval_threshold",
                    action="INCREASE",
                    reason="Frequent human-in-the-loop gating observed. Consider increasing auto-approval threshold for low-risk tasks.",
                    priority=5,
                )
            )

        return suggestions

    async def _publish_report(self, report: Dict[str, Any]):
        """Emit report event and log summary."""
        if event_bus:
            event = Event(
                topic="reflection.report_ready",
                payload=report,
                source="reflection-engine",
            )
            await event_bus.publish(event)

        logger.info(
            f"Performance reflection complete. Generated {len(report['suggestions'])} suggestions."
        )


# Singleton
reflection_engine = PerformanceReflectionEngine()
