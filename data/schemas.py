from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class EventType(str, Enum):
    OBSERVATION = "OBSERVATION"
    TASK_SPAWNED = "TASK_SPAWNED"
    TASK_CREATED = "TASK_CREATED"
    TASK_EVALUATED = "TASK_EVALUATED"
    CRASH_REPORT = "CRASH_REPORT"
    REWARD_SIGNAL = "REWARD_SIGNAL"
    MEMORY_RETRIEVAL = "MEMORY_RETRIEVAL"
    AGENT_DECISION = "AGENT_DECISION"
    EXECUTION_APPROVED = "EXECUTION_APPROVED"
    PLAN_FINALIZED = "PLAN_FINALIZED"
    AGENT_DISPATCH_REQUESTED = "AGENT_DISPATCH_REQUESTED"
    SUBTASK_COMPLETED = "SUBTASK_COMPLETED"


class LayerContext(BaseModel):
    layer_number: int = Field(..., description="The architectural layer number (1-13)")
    module_name: str = Field(
        ..., description="The specific module emitting the event, e.g., 'Vision Model'"
    )


class SystemEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the event")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of the event"
    )
    event_type: EventType = Field(..., description="The category of the event")
    source_layer: LayerContext = Field(
        ..., description="The layer and module that spawned this event"
    )
    priority: int = Field(
        default=5, ge=1, le=10, description="Priority of the event from 1 (lowest) to 10 (highest)"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Flexible JSON body containing the event data"
    )
    correlation_id: Optional[UUID] = Field(
        default=None, description="Optional UUID for tracing multi-step agent actions workflows"
    )
