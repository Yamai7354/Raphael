"""
Lifecycle Management for AI Router.

Provides graceful shutdown, state persistence, and restart recovery.
"""

import logging
import signal
import json
import asyncio
import atexit
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger("ai_router.lifecycle")


# =============================================================================
# SHUTDOWN STATE
# =============================================================================


@dataclass
class ShutdownState:
    """State to persist during shutdown."""

    shutdown_at: str
    active_tasks: List[str]  # task_ids
    pending_steps: List[Dict[str, str]]  # [{task_id, subtask_id}]
    node_states: Dict[str, str]  # {node_id: state}

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ShutdownState":
        return cls(**data)


# =============================================================================
# LIFECYCLE MANAGER
# =============================================================================


class LifecycleManager:
    """
    Manages graceful shutdown and restart recovery.
    """

    def __init__(
        self,
        state_file: str = "router_state.json",
    ):
        self.state_file = Path(state_file)
        self._shutdown_requested = False
        self._shutdown_callbacks: List[Callable] = []
        self._startup_callbacks: List[Callable] = []

    def register_shutdown_callback(self, callback: Callable) -> None:
        """Register a callback to run during shutdown."""
        self._shutdown_callbacks.append(callback)

    def register_startup_callback(self, callback: Callable) -> None:
        """Register a callback to run during startup."""
        self._startup_callbacks.append(callback)

    def setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        atexit.register(self._atexit_handler)
        logger.info("lifecycle_signals_registered")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info("shutdown_signal_received signal=%s", sig_name)
        self._shutdown_requested = True
        self._run_shutdown()

    def _atexit_handler(self) -> None:
        """Handle normal exit."""
        if not self._shutdown_requested:
            logger.info("shutdown_atexit")
            self._run_shutdown()

    def _run_shutdown(self) -> None:
        """Execute shutdown sequence."""
        logger.info(
            "shutdown_sequence_starting callbacks=%d", len(self._shutdown_callbacks)
        )

        for callback in self._shutdown_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error("shutdown_callback_failed error=%s", str(e))

        logger.info("shutdown_sequence_complete")

    def persist_state(
        self,
        active_tasks: List[str],
        pending_steps: List[Dict[str, str]],
        node_states: Dict[str, str],
    ) -> None:
        """Persist current state for restart recovery."""
        state = ShutdownState(
            shutdown_at=datetime.now().isoformat(),
            active_tasks=active_tasks,
            pending_steps=pending_steps,
            node_states=node_states,
        )

        self.state_file.write_text(json.dumps(state.to_dict(), indent=2))
        logger.info(
            "state_persisted tasks=%d steps=%d file=%s",
            len(active_tasks),
            len(pending_steps),
            self.state_file,
        )

    def load_persisted_state(self) -> Optional[ShutdownState]:
        """Load state from previous shutdown."""
        if not self.state_file.exists():
            return None

        try:
            data = json.loads(self.state_file.read_text())
            state = ShutdownState.from_dict(data)
            logger.info(
                "state_loaded shutdown_at=%s tasks=%d steps=%d",
                state.shutdown_at,
                len(state.active_tasks),
                len(state.pending_steps),
            )
            return state
        except Exception as e:
            logger.error("state_load_failed error=%s", str(e))
            return None

    def clear_persisted_state(self) -> None:
        """Clear persisted state after successful recovery."""
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info("state_file_cleared file=%s", self.state_file)

    async def recover_on_startup(self) -> Dict[str, Any]:
        """
        Check for and recover from previous shutdown.
        Returns recovery info.
        """
        state = self.load_persisted_state()
        if not state:
            return {"recovered": False}

        # Run startup callbacks
        for callback in self._startup_callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.error("startup_callback_failed error=%s", str(e))

        self.clear_persisted_state()

        return {
            "recovered": True,
            "shutdown_at": state.shutdown_at,
            "tasks_recovered": len(state.active_tasks),
            "steps_pending": len(state.pending_steps),
        }

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested


# Global singleton
lifecycle_manager = LifecycleManager()
