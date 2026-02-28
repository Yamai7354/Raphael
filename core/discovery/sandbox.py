"""
DISC-304 — Prototype Execution Sandbox.

Isolated testing environment where prototype agents run without
affecting production. Results logged separately, resources monitored,
failures safely contained.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from .prototype_designer import PrototypeSpec

logger = logging.getLogger("core.discovery.sandbox")


@dataclass
class SandboxResult:
    """Result from running a prototype in the sandbox."""

    result_id: str = field(default_factory=lambda: f"sbx_{uuid.uuid4().hex[:8]}")
    prototype_id: str = ""
    tasks_attempted: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    avg_execution_ms: float = 0.0
    resource_usage: dict = field(default_factory=dict)  # cpu, memory, etc.
    errors: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    @property
    def success_rate(self) -> float:
        return self.tasks_succeeded / max(1, self.tasks_attempted)

    def to_dict(self) -> dict:
        return {
            "result_id": self.result_id,
            "prototype_id": self.prototype_id,
            "tasks_attempted": self.tasks_attempted,
            "tasks_succeeded": self.tasks_succeeded,
            "success_rate": round(self.success_rate, 3),
            "avg_execution_ms": round(self.avg_execution_ms, 1),
            "resource_usage": self.resource_usage,
            "errors": self.errors[-10:],
        }


class PrototypeSandbox:
    """Runs prototypes in isolation and collects performance data."""

    def __init__(self, max_tasks: int = 20, timeout_ms: float = 30000, memory_limit_mb: int = 512):
        self.max_tasks = max_tasks
        self.timeout_ms = timeout_ms
        self.memory_limit_mb = memory_limit_mb
        self._results: dict[str, SandboxResult] = {}
        self._running: set[str] = set()

    def start(self, prototype: PrototypeSpec) -> SandboxResult:
        """Initialize a sandbox session for a prototype."""
        result = SandboxResult(prototype_id=prototype.prototype_id)
        self._results[result.result_id] = result
        self._running.add(result.result_id)
        logger.info(
            "sandbox_started result_id=%s prototype=%s", result.result_id, prototype.prototype_id
        )
        return result

    def record_task(
        self, result_id: str, success: bool, execution_ms: float, error: str | None = None
    ) -> None:
        """Record the outcome of a single task execution."""
        r = self._results.get(result_id)
        if not r or result_id not in self._running:
            return

        r.tasks_attempted += 1
        if success:
            r.tasks_succeeded += 1
        else:
            r.tasks_failed += 1
            if error:
                r.errors.append(error)

        # Running average
        n = r.tasks_attempted
        r.avg_execution_ms = r.avg_execution_ms + (execution_ms - r.avg_execution_ms) / n

        r.logs.append(f"task_{n}: {'ok' if success else 'fail'} {execution_ms:.0f}ms")

        # Check resource limits
        if execution_ms > self.timeout_ms:
            r.errors.append(
                f"task_{n} exceeded timeout ({execution_ms:.0f}ms > {self.timeout_ms}ms)"
            )

        # Auto-stop if max tasks reached
        if r.tasks_attempted >= self.max_tasks:
            self.stop(result_id)

    def record_resources(self, result_id: str, cpu_pct: float, memory_mb: float) -> None:
        r = self._results.get(result_id)
        if r:
            r.resource_usage = {"cpu_pct": round(cpu_pct, 1), "memory_mb": round(memory_mb, 1)}
            if memory_mb > self.memory_limit_mb:
                r.errors.append(
                    f"Memory limit exceeded: {memory_mb:.0f}MB > {self.memory_limit_mb}MB"
                )
                self.stop(result_id)

    def stop(self, result_id: str) -> SandboxResult | None:
        r = self._results.get(result_id)
        if r:
            r.completed_at = time.time()
            self._running.discard(result_id)
            logger.info(
                "sandbox_stopped result_id=%s tasks=%d success_rate=%.2f",
                result_id,
                r.tasks_attempted,
                r.success_rate,
            )
        return r

    def is_running(self, result_id: str) -> bool:
        return result_id in self._running

    def get_result(self, result_id: str) -> SandboxResult | None:
        return self._results.get(result_id)

    def get_all_results(self) -> list[dict]:
        return [r.to_dict() for r in self._results.values()]

    def get_stats(self) -> dict:
        return {
            "total_runs": len(self._results),
            "currently_running": len(self._running),
            "completed": len(self._results) - len(self._running),
        }
