"""
HabitatMetrics — Tracks and stores habitat performance data.

Collects:
  - completion_time: seconds from deploy to task done
  - compute_cost: estimated resource-seconds consumed
  - success_rate: rolling window of success/failure
  - agent_efficiency: tasks completed per agent

Stores metrics in the knowledge graph:
  (HabitatBlueprint)-[:PERFORMANCE]->(Metric)
  (Task)-[:SOLVED_BY]->(HabitatBlueprint)
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("director.habitat_metrics")


@dataclass
class MetricSnapshot:
    """A single performance measurement."""

    blueprint_name: str
    task_id: str
    success: bool
    completion_time_s: float = 0.0
    compute_cost: float = 0.0
    agent_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HabitatMetrics:
    """
    Collects habitat metrics and syncs them to the graph.

    Usage:
        metrics = HabitatMetrics(graph_store)
        metrics.start_tracking(task_id, blueprint_name)
        # ... habitat runs ...
        metrics.record_completion(task_id, success=True, agent_count=4)
        await metrics.sync_to_graph()
    """

    def __init__(self, graph_store):
        self._graph = graph_store
        self._active: dict[str, dict] = {}  # task_id → tracking info
        self._history: list[MetricSnapshot] = []

    def start_tracking(self, task_id: str, blueprint_name: str):
        """Begin tracking a task's habitat performance."""
        self._active[task_id] = {
            "blueprint_name": blueprint_name,
            "start_time": time.monotonic(),
        }
        logger.debug(f"Tracking started for task {task_id[:8]}")

    def record_completion(
        self, task_id: str, success: bool, agent_count: int = 0
    ) -> MetricSnapshot | None:
        """Record task completion and produce a metric snapshot."""
        tracking = self._active.pop(task_id, None)
        if not tracking:
            logger.warning(f"No active tracking for task {task_id[:8]}")
            return None

        elapsed = time.monotonic() - tracking["start_time"]
        compute_cost = elapsed * max(agent_count, 1)

        snapshot = MetricSnapshot(
            blueprint_name=tracking["blueprint_name"],
            task_id=task_id,
            success=success,
            completion_time_s=round(elapsed, 2),
            compute_cost=round(compute_cost, 2),
            agent_count=agent_count,
        )
        self._history.append(snapshot)
        logger.info(
            f"Task {task_id[:8]} completed: "
            f"{'✅' if success else '❌'} "
            f"{snapshot.completion_time_s}s, "
            f"cost={snapshot.compute_cost}"
        )
        return snapshot

    def get_blueprint_stats(self, blueprint_name: str) -> dict:
        """Compute aggregate statistics for a blueprint."""
        entries = [s for s in self._history if s.blueprint_name == blueprint_name]
        if not entries:
            return {
                "attempts": 0,
                "success_rate": 0.0,
                "avg_completion_s": 0.0,
                "avg_cost": 0.0,
                "efficiency": 0.0,
            }

        successes = sum(1 for s in entries if s.success)
        total_time = sum(s.completion_time_s for s in entries)
        total_cost = sum(s.compute_cost for s in entries)
        total_agents = sum(s.agent_count for s in entries)

        return {
            "attempts": len(entries),
            "success_rate": round(successes / len(entries), 3),
            "avg_completion_s": round(total_time / len(entries), 2),
            "avg_cost": round(total_cost / len(entries), 2),
            "efficiency": round(successes / max(total_agents, 1), 3),
        }

    async def sync_to_graph(self):
        """Push all unsynced metrics to the knowledge graph."""
        for snapshot in self._history:
            # (HabitatBlueprint)-[:PERFORMANCE]->(Metric)
            await self._graph.execute_cypher(
                """
                MATCH (h:HabitatBlueprint {name: $blueprint})
                MERGE (m:Metric {task_id: $task_id})
                SET m.completion_time_s = $time,
                    m.compute_cost = $cost,
                    m.success = $success,
                    m.agent_count = $agents,
                    m.timestamp = $ts,
                    m.memory_type = "metric",
                    m.promotion_score = 0.5
                MERGE (h)-[:PERFORMANCE]->(m)
                """,
                {
                    "blueprint": snapshot.blueprint_name,
                    "task_id": snapshot.task_id,
                    "time": snapshot.completion_time_s,
                    "cost": snapshot.compute_cost,
                    "success": snapshot.success,
                    "agents": snapshot.agent_count,
                    "ts": snapshot.timestamp,
                },
            )

            # (Task)-[:SOLVED_BY]->(HabitatBlueprint)
            if snapshot.success:
                await self._graph.execute_cypher(
                    """
                    MATCH (t:Task {name: $task_id})
                    MATCH (h:HabitatBlueprint {name: $blueprint})
                    MERGE (t)-[:SOLVED_BY]->(h)
                    """,
                    {
                        "task_id": snapshot.task_id,
                        "blueprint": snapshot.blueprint_name,
                    },
                )

        synced = len(self._history)
        self._history.clear()
        logger.info(f"Synced {synced} metric(s) to graph")

    @property
    def active_tracking_count(self) -> int:
        return len(self._active)
