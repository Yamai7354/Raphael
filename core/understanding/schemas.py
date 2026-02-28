from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    COMMIT = "COMMIT"
    DRY_RUN = "DRY_RUN"
    SIMULATE = "SIMULATE"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class SubTask(BaseModel):
    """
    An executable dependency of a larger goal. Sent to Layer 6/7 for execution.
    """

    sub_task_id: UUID = Field(default_factory=uuid4, description="Unique ID for this subtask")
    parent_task_id: UUID = Field(..., description="ID of the parent goal resolving to")
    description: str = Field(..., description="Actionable description of the subtask")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    dependencies: List[UUID] = Field(
        default_factory=list, description="List of sub_task_ids that must finish first"
    )
    required_capabilities: List[str] = Field(
        default_factory=list, description="Skills needed (e.g., 'bash', 'python')"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Context parameters for the executing agent"
    )
    result: Optional[str] = Field(default=None, description="Outcome of the execution")


class Task(BaseModel):
    """
    A high-level user goal or system objective generated from Perception intents.
    """

    task_id: UUID = Field(default_factory=uuid4, description="Unique goal identifier")
    original_intent: str = Field(..., description="Source reasoning or raw command text")
    priority: int = Field(
        default=5, ge=1, le=10, description="Priority inherited from the semantic observation"
    )
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sub_tasks: List[SubTask] = Field(
        default_factory=list, description="Decomposed graph of execution steps"
    )
    correlation_id: Optional[UUID] = Field(
        default=None, description="Trace back to the original Layer 1 raw event"
    )
