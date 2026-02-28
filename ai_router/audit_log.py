"""
Deterministic Logging & Replay for AI Router.

Provides structured audit logs for task execution with full traceability.
All steps are logged with timestamps, inputs, outputs, and plan references.
Supports replay of task execution for debugging and observability.
"""

import logging
import json
import hashlib
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger("ai_router.audit")


# =============================================================================
# LOG EVENT TYPES
# =============================================================================


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Task lifecycle
    TASK_CREATED = "task_created"
    TASK_PLANNING = "task_planning"
    TASK_PLANNED = "task_planned"
    TASK_EXECUTING = "task_executing"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # Step lifecycle
    STEP_STARTED = "step_started"
    STEP_CONTEXT_BUILT = "step_context_built"
    STEP_INVOKED = "step_invoked"
    STEP_VALIDATED = "step_validated"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_RETRYING = "step_retrying"
    STEP_ESCALATED = "step_escalated"

    # Context
    CONTEXT_TRUNCATED = "context_truncated"

    # Node selection & load
    NODE_SELECTED = "node_selected"
    NODE_SLOT_ACQUIRED = "node_slot_acquired"
    NODE_SLOT_RELEASED = "node_slot_released"
    NODE_UNAVAILABLE = "node_unavailable"

    # Queue events
    STEP_QUEUED = "step_queued"
    STEP_DEQUEUED = "step_dequeued"
    QUEUE_FULL = "queue_full"

    # Tool events
    TOOL_INVOKED = "tool_invoked"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"

    # Circuit breaker

    # Circuit breaker
    CIRCUIT_OPENED = "circuit_opened"
    CIRCUIT_CLOSED = "circuit_closed"
    CIRCUIT_HALF_OPEN = "circuit_half_open"

    # Validation
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"


# =============================================================================
# AUDIT LOG ENTRY
# =============================================================================


@dataclass
class AuditEntry:
    """A single audit log entry."""

    timestamp: str
    event_type: AuditEventType
    task_id: str

    # Optional fields
    subtask_id: Optional[str] = None
    planner_output_id: Optional[str] = None
    plan_hash: Optional[str] = None

    # Event details
    data: Dict[str, Any] = field(default_factory=dict)

    # Tracking
    sequence_id: int = 0
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "sequence_id": self.sequence_id,
        }
        if self.subtask_id:
            result["subtask_id"] = self.subtask_id
        if self.planner_output_id:
            result["planner_output_id"] = self.planner_output_id
        if self.plan_hash:
            result["plan_hash"] = self.plan_hash
        if self.data:
            result["data"] = self.data
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


# =============================================================================
# AUDIT LOG
# =============================================================================


class AuditLog:
    """
    In-memory audit log for task execution.

    Stores all events for a task in sequence for replay.
    Events are deterministically ordered by sequence_id.
    """

    def __init__(self, max_entries_per_task: int = 1000):
        self.max_entries_per_task = max_entries_per_task
        self._logs: Dict[str, List[AuditEntry]] = {}
        self._sequence: Dict[str, int] = {}

    def log(
        self,
        event_type: AuditEventType,
        task_id: str,
        subtask_id: Optional[str] = None,
        planner_output_id: Optional[str] = None,
        plan_hash: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ) -> AuditEntry:
        """
        Log an audit event.
        Returns the created entry.
        """
        # Initialize task log if needed
        if task_id not in self._logs:
            self._logs[task_id] = []
            self._sequence[task_id] = 0

        # Create entry
        self._sequence[task_id] += 1
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            task_id=task_id,
            subtask_id=subtask_id,
            planner_output_id=planner_output_id,
            plan_hash=plan_hash,
            data=data or {},
            sequence_id=self._sequence[task_id],
            duration_ms=duration_ms,
        )

        # Store entry
        self._logs[task_id].append(entry)

        # Trim if over limit
        if len(self._logs[task_id]) > self.max_entries_per_task:
            self._logs[task_id] = self._logs[task_id][-self.max_entries_per_task :]

        # Also emit to standard logger
        logger.info(
            "audit_%s task_id=%s subtask=%s seq=%d",
            event_type.value,
            task_id,
            subtask_id or "-",
            entry.sequence_id,
        )

        return entry

    def get_task_log(self, task_id: str) -> List[AuditEntry]:
        """Get all log entries for a task."""
        return self._logs.get(task_id, [])

    def get_task_log_json(self, task_id: str) -> List[Dict[str, Any]]:
        """Get task log as JSON-serializable list."""
        return [e.to_dict() for e in self.get_task_log(task_id)]

    def get_replay_sequence(self, task_id: str) -> Dict[str, Any]:
        """
        Get task execution as replay sequence.
        Includes task metadata and ordered events.
        """
        entries = self.get_task_log(task_id)
        if not entries:
            return {"task_id": task_id, "events": [], "error": "No log entries"}

        # Extract metadata from first entry
        first = entries[0]

        return {
            "task_id": task_id,
            "planner_output_id": first.planner_output_id,
            "plan_hash": first.plan_hash,
            "event_count": len(entries),
            "first_event": first.timestamp,
            "last_event": entries[-1].timestamp if entries else None,
            "events": [e.to_dict() for e in entries],
        }

    def compute_execution_hash(self, task_id: str) -> str:
        """
        Compute deterministic hash of task execution.
        Same inputs + same planner version = same hash.
        """
        entries = self.get_task_log(task_id)
        if not entries:
            return ""

        # Include only deterministic fields
        hash_data = []
        for entry in entries:
            hash_data.append(
                {
                    "type": entry.event_type.value,
                    "task": entry.task_id,
                    "subtask": entry.subtask_id,
                    "seq": entry.sequence_id,
                }
            )

        hash_str = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_str.encode()).hexdigest()[:16]

    def clear_task_log(self, task_id: str) -> bool:
        """Clear log entries for a task."""
        if task_id in self._logs:
            del self._logs[task_id]
            del self._sequence[task_id]
            return True
        return False


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


# Global audit log instance
audit_log = AuditLog()


def log_task_event(
    event_type: AuditEventType,
    task,  # Task from orchestration
    data: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[float] = None,
) -> AuditEntry:
    """Log a task-level event."""
    return audit_log.log(
        event_type=event_type,
        task_id=task.task_id,
        planner_output_id=task.planner_output_id,
        plan_hash=task.plan_hash,
        data=data,
        duration_ms=duration_ms,
    )


def log_step_event(
    event_type: AuditEventType,
    task,  # Task from orchestration
    step,  # Step from orchestration
    data: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[float] = None,
) -> AuditEntry:
    """Log a step-level event."""
    return audit_log.log(
        event_type=event_type,
        task_id=task.task_id,
        subtask_id=step.subtask_id,
        planner_output_id=task.planner_output_id,
        plan_hash=task.plan_hash,
        data=data,
        duration_ms=duration_ms,
    )


def get_task_audit(task_id: str) -> Dict[str, Any]:
    """Get full audit log for a task."""
    return audit_log.get_replay_sequence(task_id)
