"""
Task Orchestration State Model for AI Router.

Defines Task & Step structures for multi-step execution.
Every task references a planner_output_id for traceability.
"""

import logging
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from raphael.core.models.task import ExecutionMode

logger = logging.getLogger("ai_router.orchestration")


# =============================================================================
# STATUS ENUMS
# =============================================================================


class TaskStatus(str, Enum):
    """Status of a task lifecycle."""

    PENDING = "pending"  # Created, awaiting planning
    PLANNING = "planning"  # Calling planner endpoint
    READY = "ready"  # Planner complete, awaiting execution
    AWAITING_APPROVAL = "awaiting_approval"  # Halted for safety review
    EXECUTING = "executing"  # Subtasks being processed
    COMPLETED = "completed"  # All subtasks done successfully
    FAILED = "failed"  # Task failed after retries
    CANCELLED = "cancelled"  # User cancelled


class StepStatus(str, Enum):
    """Status of an individual step/subtask."""

    PENDING = "pending"  # Awaiting execution
    BLOCKED = "blocked"  # Waiting on dependencies
    EXECUTING = "executing"  # Currently running
    COMPLETED = "completed"  # Finished successfully
    FAILED = "failed"  # Failed after retries
    RETRYING = "retrying"  # Retry in progress
    SKIPPED = "skipped"  # Skipped (e.g., on cancel)


# =============================================================================
# RETRY & ESCALATION POLICY
# =============================================================================


@dataclass
class RetryPolicy:
    """Configurable retry policy for steps."""

    max_attempts: int = 3
    backoff_base_sec: float = 1.0
    backoff_max_sec: float = 30.0
    escalate_on_failure: bool = True
    escalate_to_role: Optional[str] = None  # Role to escalate to

    def get_backoff_sec(self, attempt: int) -> float:
        """Calculate exponential backoff time."""
        backoff = self.backoff_base_sec * (2 ** (attempt - 1))
        return min(backoff, self.backoff_max_sec)


# Default retry policy
DEFAULT_RETRY_POLICY = RetryPolicy()


# =============================================================================
# STEP MODEL
# =============================================================================


@dataclass
class Step:
    """
    A single execution step derived from planner subtask.

    Specialists only see this step, never the full task objective.
    """

    subtask_id: str
    description: str
    role: str  # suggested_node_role from planner
    required_context: List[str] = field(default_factory=list)
    can_run_parallel: bool = False

    # Execution state
    status: StepStatus = StepStatus.PENDING
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # Retry configuration
    retry_policy: RetryPolicy = field(default_factory=lambda: DEFAULT_RETRY_POLICY)
    attempt_count: int = 0
    escalated: bool = False
    escalated_from_role: Optional[str] = None

    # Tracking
    assigned_node_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def mark_executing(self, node_id: str) -> None:
        """Mark step as executing on a node."""
        self.status = StepStatus.EXECUTING
        self.assigned_node_id = node_id
        self.started_at = datetime.now()
        self.attempt_count += 1
        logger.info(
            "step_executing subtask_id=%s node=%s attempt=%d",
            self.subtask_id,
            node_id,
            self.attempt_count,
        )

    def mark_completed(self, output: Dict[str, Any]) -> None:
        """Mark step as completed with output."""
        self.status = StepStatus.COMPLETED
        self.output_data = output
        self.completed_at = datetime.now()
        logger.info(
            "step_completed subtask_id=%s duration_sec=%.2f",
            self.subtask_id,
            (self.completed_at - self.started_at).total_seconds()
            if self.started_at
            else 0,
        )

    def mark_failed(self, error: str) -> None:
        """Mark step as failed, potentially triggering retry or escalation."""
        max_attempts = self.retry_policy.max_attempts

        if self.attempt_count < max_attempts:
            self.status = StepStatus.RETRYING
            logger.warning(
                "step_retrying subtask_id=%s attempt=%d/%d error=%s",
                self.subtask_id,
                self.attempt_count,
                max_attempts,
                error,
            )
        else:
            # Check if escalation is configured
            if self.retry_policy.escalate_on_failure and not self.escalated:
                self.status = StepStatus.RETRYING  # Allow escalated retry
                self.escalated = True
                self.escalated_from_role = self.role
                if self.retry_policy.escalate_to_role:
                    self.role = self.retry_policy.escalate_to_role
                logger.warning(
                    "step_escalating subtask_id=%s from_role=%s to_role=%s",
                    self.subtask_id,
                    self.escalated_from_role,
                    self.role,
                )
            else:
                self.status = StepStatus.FAILED
                self.error_message = error
                self.completed_at = datetime.now()
                logger.error(
                    "step_failed subtask_id=%s attempts=%d error=%s",
                    self.subtask_id,
                    self.attempt_count,
                    error,
                )

    def can_retry(self) -> bool:
        """Check if step can be retried."""
        max_attempts = self.retry_policy.max_attempts
        # Allow extra attempt if escalating
        effective_max = max_attempts + (1 if self.escalated else 0)
        return self.attempt_count < effective_max and self.status == StepStatus.RETRYING

    def get_backoff_sec(self) -> float:
        """Get current backoff wait time."""
        return self.retry_policy.get_backoff_sec(self.attempt_count)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "subtask_id": self.subtask_id,
            "description": self.description,
            "role": self.role,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "assigned_node_id": self.assigned_node_id,
            "output": self.output_data,
            "error": self.error_message,
        }


# =============================================================================
# TASK MODEL
# =============================================================================


@dataclass
class Task:
    """
    A multi-step task with planner-derived subtasks.

    The task objective is only visible to the router/supervisor,
    never to individual specialist nodes.
    """

    task_id: str
    objective: str
    constraints: List[str] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    agent_config: Dict[str, Any] = field(default_factory=dict)
    execution_mode: ExecutionMode = ExecutionMode.COMMIT
    approved: bool = False
    ethical_violations: List[str] = field(default_factory=list)

    # Planner integration
    planner_output_id: Optional[str] = None
    plan_hash: Optional[str] = None

    # Execution state
    status: TaskStatus = TaskStatus.PENDING
    steps: List[Step] = field(default_factory=list)
    state_blob: Dict[str, Any] = field(default_factory=dict)  # Accumulated results

    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        """Generate planner_output_id if not provided."""
        if not self.planner_output_id:
            self.planner_output_id = f"plan-{uuid.uuid4().hex[:12]}"

    def set_steps_from_planner(self, subtasks: List[Dict[str, Any]]) -> None:
        """
        Create steps from planner output.
        Maps subtasks to Step objects.
        """
        self.steps = []
        for subtask in subtasks:
            step = Step(
                subtask_id=subtask["subtask_id"],
                description=subtask["description"],
                role=subtask.get("suggested_node_role", "fast_inference"),
                required_context=subtask.get("required_context", []),
                can_run_parallel=subtask.get("can_run_parallel", False),
            )
            self.steps.append(step)

        self.status = TaskStatus.READY
        logger.info(
            "task_steps_created task_id=%s step_count=%d", self.task_id, len(self.steps)
        )

    def get_pending_steps(self) -> List[Step]:
        """Get steps ready for execution."""
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    def get_executable_steps(self) -> List[Step]:
        """
        Get steps that can be executed now.
        Considers parallelism and dependencies.
        """
        executable = []
        has_executing = any(s.status == StepStatus.EXECUTING for s in self.steps)

        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue

            # Check if dependencies are met (required_context)
            if not self._dependencies_met(step):
                step.status = StepStatus.BLOCKED
                continue

            # If parallel execution allowed, add it
            if step.can_run_parallel:
                executable.append(step)
            elif not has_executing:
                # Sequential step, only if nothing else executing
                executable.append(step)
                break  # Only one sequential step at a time

        return executable

    def _dependencies_met(self, step: Step) -> bool:
        """Check if all required context is available in state_blob."""
        for req in step.required_context:
            # Simple heuristic: check if required context key exists
            if req not in self.state_blob and req not in [
                "objective",
                "constraints",
                "context",
            ]:
                # Check if a step with output containing this exists
                found = False
                for prev_step in self.steps:
                    if (
                        prev_step.status == StepStatus.COMPLETED
                        and prev_step.output_data
                    ):
                        found = True
                        break
                if not found and req not in ["query"]:
                    return False
        return True

    def update_state(self, step: Step) -> None:
        """Update state_blob with step output."""
        if step.output_data:
            self.state_blob[step.subtask_id] = step.output_data

    def check_completion(self) -> bool:
        """Check if all steps are complete."""
        all_done = all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps
        )
        any_failed = any(s.status == StepStatus.FAILED for s in self.steps)

        if any_failed:
            self.status = TaskStatus.FAILED
            self.completed_at = datetime.now()
            logger.error("task_failed task_id=%s", self.task_id)
            return True

        if all_done:
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now()
            logger.info(
                "task_completed task_id=%s duration_sec=%.2f",
                self.task_id,
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at
                else 0,
            )
            return True

        return False

    def cancel(self) -> None:
        """Cancel the task and all pending steps."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.BLOCKED):
                step.status = StepStatus.SKIPPED
        logger.info("task_cancelled task_id=%s", self.task_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "status": self.status.value,
            "planner_output_id": self.planner_output_id,
            "plan_hash": self.plan_hash,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "error": self.error_message,
        }


# =============================================================================
# TASK REGISTRY
# =============================================================================


class TaskRegistry:
    """
    In-memory registry for task state.
    Single source of truth for task lifecycle.
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._lock = False  # Simple mutex for critical sections

    def create_task(
        self,
        task_id: str,
        objective: str,
        constraints: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """Create a new task."""
        if task_id in self._tasks:
            raise ValueError(f"Task already exists: {task_id}")

        task = Task(
            task_id=task_id,
            objective=objective,
            constraints=constraints or [],
            context=context,
        )
        self._tasks[task_id] = task
        logger.info("task_created task_id=%s objective=%s", task_id, objective[:50])
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def delete_task(self, task_id: str) -> bool:
        """Delete a task (only if completed/failed/cancelled)."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status not in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ):
            raise ValueError(f"Cannot delete active task: {task_id}")
        del self._tasks[task_id]
        logger.info("task_deleted task_id=%s", task_id)
        return True

    def get_task_count(self) -> int:
        """Get total task count."""
        return len(self._tasks)

    def get_active_tasks(self) -> List[Task]:
        """Get tasks that are currently executing."""
        return [
            t
            for t in self._tasks.values()
            if t.status in (TaskStatus.PLANNING, TaskStatus.READY, TaskStatus.EXECUTING)
        ]


# Global singleton
task_registry = TaskRegistry()
