"""
Dedicated Planner Endpoint for AI Router.

Provides task decomposition with deterministic output.
Separates "thinking about tasks" from "doing tasks".
"""

import logging
import hashlib
import json
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator

logger = logging.getLogger("ai_router.planner")


# =============================================================================
# INPUT SCHEMA
# =============================================================================


class PlanRequest(BaseModel):
    """Input schema for /planner/plan endpoint."""

    task_id: str = Field(..., description="Unique identifier for the task")
    objective: str = Field(..., description="What needs to be accomplished")
    constraints: List[str] = Field(
        default_factory=list, description="Constraints to apply"
    )
    context: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None, description="Optional context (string or JSON state)"
    )

    @validator("task_id")
    def task_id_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("task_id cannot be empty")
        return v.strip()

    @validator("objective")
    def objective_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("objective cannot be empty")
        return v.strip()


# =============================================================================
# OUTPUT SCHEMA
# =============================================================================


class NodeRole(str, Enum):
    """Suggested node role for a subtask."""

    FAST_INFERENCE = "fast_inference"
    HEAVY_INFERENCE = "heavy_inference"


class Confidence(str, Enum):
    """Confidence level for the plan."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Subtask(BaseModel):
    """A single subtask in the execution plan."""

    subtask_id: str
    description: str
    required_context: List[str] = Field(default_factory=list)
    suggested_node_role: NodeRole = NodeRole.FAST_INFERENCE
    can_run_parallel: bool = False


class PlanMetadata(BaseModel):
    """Metadata about the generated plan."""

    estimated_total_steps: int
    confidence: Confidence
    plan_hash: Optional[str] = None  # For reproducibility verification


class PlanResponse(BaseModel):
    """Output schema for /planner/plan endpoint."""

    task_id: str
    subtasks: List[Subtask]
    metadata: PlanMetadata


# =============================================================================
# PLANNER LOGIC
# =============================================================================


class PlannerConfig:
    """Configuration for the planner."""

    MAX_SUBTASKS = 20
    MAX_CONTEXT_PER_SUBTASK = 8192
    SUPPORTED_VERSIONS = {"1", "2"}
    DEFAULT_VERSION = "1"


class PlanValidationError(Exception):
    """Raised when a plan fails validation."""

    pass


def compute_plan_hash(request: PlanRequest) -> str:
    """
    Compute deterministic hash for a plan request.
    Same input → same hash → same subtasks.
    """
    canonical = json.dumps(
        {
            "task_id": request.task_id,
            "objective": request.objective,
            "constraints": sorted(request.constraints),
            "context": str(request.context) if request.context else None,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def decompose_task(request: PlanRequest, version: str = "1") -> PlanResponse:
    """
    Deterministically decompose a task into subtasks.

    Rules:
    - Same input → same subtasks (deterministic)
    - Only uses provided context and constraints
    - No subtask exceeds context limits
    """
    plan_hash = compute_plan_hash(request)

    # Analyze objective for complexity estimation
    objective_lower = request.objective.lower()
    constraints = request.constraints

    subtasks: List[Subtask] = []

    # Deterministic decomposition based on objective patterns
    if any(kw in objective_lower for kw in ["analyze", "evaluate", "compare"]):
        # Analysis tasks: gather → analyze → summarize
        subtasks = [
            Subtask(
                subtask_id=f"{request.task_id}_gather",
                description="Gather relevant information and context",
                required_context=["objective", "constraints"],
                suggested_node_role=NodeRole.FAST_INFERENCE,
                can_run_parallel=False,
            ),
            Subtask(
                subtask_id=f"{request.task_id}_analyze",
                description="Perform detailed analysis",
                required_context=["gathered_info"],
                suggested_node_role=NodeRole.HEAVY_INFERENCE,
                can_run_parallel=False,
            ),
            Subtask(
                subtask_id=f"{request.task_id}_summarize",
                description="Synthesize findings into conclusions",
                required_context=["analysis_result"],
                suggested_node_role=NodeRole.FAST_INFERENCE,
                can_run_parallel=False,
            ),
        ]
        confidence = Confidence.HIGH

    elif any(kw in objective_lower for kw in ["create", "build", "implement", "write"]):
        # Creation tasks: plan → implement → verify
        subtasks = [
            Subtask(
                subtask_id=f"{request.task_id}_plan",
                description="Create implementation plan",
                required_context=["objective", "constraints"],
                suggested_node_role=NodeRole.HEAVY_INFERENCE,
                can_run_parallel=False,
            ),
            Subtask(
                subtask_id=f"{request.task_id}_implement",
                description="Execute the implementation",
                required_context=["implementation_plan"],
                suggested_node_role=NodeRole.HEAVY_INFERENCE,
                can_run_parallel=False,
            ),
            Subtask(
                subtask_id=f"{request.task_id}_verify",
                description="Verify implementation meets requirements",
                required_context=["implementation_result", "constraints"],
                suggested_node_role=NodeRole.FAST_INFERENCE,
                can_run_parallel=False,
            ),
        ]
        confidence = Confidence.HIGH

    elif any(kw in objective_lower for kw in ["search", "find", "lookup", "query"]):
        # Search tasks: can often parallelize
        subtasks = [
            Subtask(
                subtask_id=f"{request.task_id}_search",
                description="Execute search operation",
                required_context=["query", "constraints"],
                suggested_node_role=NodeRole.FAST_INFERENCE,
                can_run_parallel=True,
            ),
            Subtask(
                subtask_id=f"{request.task_id}_filter",
                description="Filter and rank results",
                required_context=["search_results"],
                suggested_node_role=NodeRole.FAST_INFERENCE,
                can_run_parallel=False,
            ),
        ]
        confidence = Confidence.HIGH

    else:
        # Generic task: single step execution
        subtasks = [
            Subtask(
                subtask_id=f"{request.task_id}_execute",
                description=f"Execute: {request.objective[:100]}",
                required_context=["objective", "context"],
                suggested_node_role=NodeRole.HEAVY_INFERENCE,
                can_run_parallel=False,
            ),
        ]
        confidence = Confidence.MEDIUM

    # Apply constraints modifiers
    if "urgent" in " ".join(constraints).lower():
        # Prioritize fast inference for urgent tasks
        for subtask in subtasks:
            if subtask.can_run_parallel:
                subtask.suggested_node_role = NodeRole.FAST_INFERENCE

    if "thorough" in " ".join(constraints).lower():
        # Use heavy inference for thorough analysis
        for subtask in subtasks:
            subtask.suggested_node_role = NodeRole.HEAVY_INFERENCE
        confidence = Confidence.HIGH

    # Create response
    response = PlanResponse(
        task_id=request.task_id,
        subtasks=subtasks,
        metadata=PlanMetadata(
            estimated_total_steps=len(subtasks),
            confidence=confidence,
            plan_hash=plan_hash,
        ),
    )

    logger.info(
        "plan_generated task_id=%s subtasks=%d confidence=%s hash=%s",
        request.task_id,
        len(subtasks),
        confidence.value,
        plan_hash,
    )

    return response


def validate_plan(plan: PlanResponse) -> tuple[bool, str]:
    """
    Validate a plan meets all requirements.
    Returns (is_valid, error_message).
    """
    # Check subtask count
    if len(plan.subtasks) > PlannerConfig.MAX_SUBTASKS:
        return (
            False,
            f"Too many subtasks: {len(plan.subtasks)} > {PlannerConfig.MAX_SUBTASKS}",
        )

    # Check for duplicate subtask IDs
    subtask_ids = [s.subtask_id for s in plan.subtasks]
    if len(subtask_ids) != len(set(subtask_ids)):
        return (False, "Duplicate subtask IDs detected")

    # Check for empty descriptions
    for subtask in plan.subtasks:
        if not subtask.description.strip():
            return (False, f"Subtask {subtask.subtask_id} has empty description")

    return (True, "")


# =============================================================================
# PLANNER REGISTRY (for version management)
# =============================================================================


class PlannerRegistry:
    """Manages planner versions and dispatching."""

    def __init__(self):
        self._planners: Dict[str, Any] = {
            "1": decompose_task,
            # Future: "2": decompose_task_v2,
        }

    def get_planner(self, version: str):
        """Get planner function for version."""
        if version not in self._planners:
            raise ValueError(f"Unsupported planner version: {version}")
        return self._planners[version]

    def supported_versions(self) -> List[str]:
        return list(self._planners.keys())


planner_registry = PlannerRegistry()
