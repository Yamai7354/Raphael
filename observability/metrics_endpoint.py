"""
Network Observatory — Prometheus metrics for swarm health.

Metrics to track:
  - task_success_rate   — swarm health
  - agent_response_time — bottlenecks
  - memory_growth       — graph health
  - model_usage         — GPU optimization

Mount this router on the FastAPI app: app.include_router(metrics_router, prefix="/metrics")
Or expose /metrics that returns Prometheus text format.
"""

from __future__ import annotations

from typing import Dict, Any

# In-memory counters for development; replace with real storage (Redis, Neo4j) in production.
_metrics: Dict[str, Any] = {
    "tasks_total": 0,
    "tasks_success": 0,
    "agent_response_seconds": [],  # list of floats for avg
    "memory_nodes_count": 0,
    "model_inference_count": 0,
}


def record_task_success(success: bool):
    _metrics["tasks_total"] += 1
    if success:
        _metrics["tasks_success"] += 1


def record_agent_response_time(seconds: float):
    _metrics["agent_response_seconds"].append(seconds)
    # Keep last 1000 for rolling avg
    if len(_metrics["agent_response_seconds"]) > 1000:
        _metrics["agent_response_seconds"] = _metrics["agent_response_seconds"][-1000:]


def set_memory_nodes_count(count: int):
    _metrics["memory_nodes_count"] = count


def record_model_inference():
    _metrics["model_inference_count"] += 1


def get_task_success_rate() -> float:
    total = _metrics["tasks_total"]
    if total == 0:
        return 0.0
    return _metrics["tasks_success"] / total


def get_agent_response_time_avg() -> float:
    times = _metrics["agent_response_seconds"]
    if not times:
        return 0.0
    return sum(times) / len(times)


def prometheus_text() -> str:
    """Return metrics in Prometheus exposition format."""
    rate = get_task_success_rate()
    avg_time = get_agent_response_time_avg()
    lines = [
        "# HELP raphael_task_success_rate Swarm task success rate (0-1).",
        "# TYPE raphael_task_success_rate gauge",
        f"raphael_task_success_rate {rate}",
        "# HELP raphael_tasks_total Total tasks processed.",
        "# TYPE raphael_tasks_total counter",
        f"raphael_tasks_total {_metrics['tasks_total']}",
        "# HELP raphael_agent_response_time_seconds Average agent response time in seconds.",
        "# TYPE raphael_agent_response_time_seconds gauge",
        f"raphael_agent_response_time_seconds {avg_time}",
        "# HELP raphael_memory_nodes_count Knowledge graph node count.",
        "# TYPE raphael_memory_nodes_count gauge",
        f"raphael_memory_nodes_count {_metrics['memory_nodes_count']}",
        "# HELP raphael_model_inference_total Total model inference calls.",
        "# TYPE raphael_model_inference_total counter",
        f"raphael_model_inference_total {_metrics['model_inference_count']}",
    ]
    return "\n".join(lines) + "\n"


def metrics_router():
    """Returns a FastAPI APIRouter for /metrics (GET)."""
    from fastapi import APIRouter
    from fastapi.responses import PlainTextResponse
    router = APIRouter(tags=["observability"])

    @router.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        return prometheus_text()

    return router
