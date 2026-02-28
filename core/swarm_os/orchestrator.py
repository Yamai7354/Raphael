"""
SOS-501 — Core Orchestration Engine.

Central coordinator integrating evolution, cognition, discovery,
and world model layers. Provides unified interface for task assignment,
agent monitoring, and memory updates.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.orchestrator")


@dataclass
class SystemState:
    """System-wide state snapshot."""

    timestamp: float = field(default_factory=time.time)
    active_agents: int = 0
    pending_tasks: int = 0
    running_experiments: int = 0
    memory_operations: int = 0
    discovery_cycles: int = 0
    cognition_cycles: int = 0
    health_score: float = 1.0

    def to_dict(self) -> dict:
        return {
            "active_agents": self.active_agents,
            "pending_tasks": self.pending_tasks,
            "running_experiments": self.running_experiments,
            "memory_operations": self.memory_operations,
            "discovery_cycles": self.discovery_cycles,
            "cognition_cycles": self.cognition_cycles,
            "health_score": round(self.health_score, 3),
        }


class SwarmOrchestrator:
    """Central orchestration engine for the swarm operating system."""

    def __init__(self):
        self._state = SystemState()
        self._engines: dict[str, object] = {}
        self._cycle_count = 0
        self._event_log: list[dict] = []
        self._running = False

    def register_engine(self, name: str, engine: object) -> None:
        """Register a subsystem engine (evolution, cognition, etc.)."""
        self._engines[name] = engine
        self._log_event("engine_registered", {"engine": name})
        logger.info("engine_registered name=%s", name)

    def get_engine(self, name: str) -> object | None:
        return self._engines.get(name)

    def start(self) -> None:
        self._running = True
        self._log_event("orchestrator_started", {})
        logger.info("orchestrator_started engines=%d", len(self._engines))

    def stop(self) -> None:
        self._running = False
        self._log_event("orchestrator_stopped", {})

    def is_running(self) -> bool:
        return self._running

    def tick(self) -> dict:
        """Execute one orchestration cycle."""
        if not self._running:
            return {"status": "stopped"}

        self._cycle_count += 1
        start = time.time()
        results: dict[str, str] = {}

        # Collect metrics from each engine
        for name, engine in self._engines.items():
            if hasattr(engine, "get_stats"):
                try:
                    stats = engine.get_stats()
                    results[name] = "ok"
                except Exception as e:
                    results[name] = f"error: {e}"
            else:
                results[name] = "no_stats"

        # Update system state
        self._state.timestamp = time.time()
        self._state.health_score = sum(1 for v in results.values() if v == "ok") / max(
            1, len(results)
        )

        duration = time.time() - start
        self._log_event(
            "tick", {"cycle": self._cycle_count, "duration_ms": round(duration * 1000, 1)}
        )
        return {
            "cycle": self._cycle_count,
            "engines": results,
            "health": round(self._state.health_score, 3),
            "duration_ms": round(duration * 1000, 1),
        }

    def update_state(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self._state, k):
                setattr(self._state, k, v)

    def get_state(self) -> dict:
        return self._state.to_dict()

    # --- Dashboard data (SOS-510) ---

    def get_dashboard(self) -> dict:
        """Full dashboard data combining all engine stats."""
        engine_stats: dict[str, dict] = {}
        for name, engine in self._engines.items():
            if hasattr(engine, "get_stats"):
                try:
                    engine_stats[name] = engine.get_stats()
                except Exception:
                    engine_stats[name] = {"error": "unavailable"}

        return {
            "system_state": self._state.to_dict(),
            "engines": engine_stats,
            "cycle_count": self._cycle_count,
            "running": self._running,
            "recent_events": self._event_log[-20:],
        }

    def get_stats(self) -> dict:
        return {
            "cycles": self._cycle_count,
            "engines": len(self._engines),
            "running": self._running,
            "health": round(self._state.health_score, 3),
        }

    def _log_event(self, event_type: str, data: dict) -> None:
        self._event_log.append(
            {
                "type": event_type,
                "data": data,
                "timestamp": time.time(),
            }
        )
        if len(self._event_log) > 1000:
            self._event_log = self._event_log[-500:]
