"""
Workflow Manager for AI Router (Phase 13).

Defines structured multi-agent workflows and handles inter-agent communication.
Enforces deterministic execution and dependency management.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("ai_router.workflow")


class WorkflowStepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class WorkflowStep:
    step_id: str
    role: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)

    # Runtime state
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    output: Optional[Any] = None
    assigned_node: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class Workflow:
    workflow_id: str
    steps: Dict[str, WorkflowStep]
    status: str = "PENDING"
    created_at: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)  # Shared workflow memory

    def get_runnable_steps(self) -> List[WorkflowStep]:
        """Get steps that are PENDING and have all dependencies met."""
        runnable = []
        for step in self.steps.values():
            if step.status != WorkflowStepStatus.PENDING:
                continue

            deps_met = True
            for dep_id in step.dependencies:
                dep = self.steps.get(dep_id)
                if not dep or dep.status != WorkflowStepStatus.COMPLETED:
                    deps_met = False
                    break

            if deps_met:
                runnable.append(step)
        return runnable

    def update_step(
        self,
        step_id: str,
        status: WorkflowStepStatus,
        output: Any = None,
        error: str = None,
    ):
        step = self.steps.get(step_id)
        if not step:
            return

        step.status = status
        if output:
            step.output = output
            if isinstance(output, dict):
                self.context.update(output)  # Merge into shared context (controlled)

        if error:
            step.error = error

        if status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.FAILED):
            step.completed_at = datetime.now()


class AgentMessage:
    """Inter-agent communication message (Ticket 2)."""

    def __init__(
        self, sender_role: str, receiver_role: str, content: Any, workflow_id: str
    ):
        self.id = f"msg-{int(datetime.now().timestamp() * 1000)}"
        self.sender_role = sender_role
        self.receiver_role = receiver_role
        self.content = content
        self.workflow_id = workflow_id
        self.timestamp = datetime.now()


class WorkflowManager:
    """
    Orchestrates multi-agent workflows (Ticket 1).
    """

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._message_log: List[AgentMessage] = []
        self._lock = asyncio.Lock()

    def create_workflow(self, workflow_id: str, steps_def: List[Dict]) -> Workflow:
        """Define a new workflow."""
        steps = {}
        for s_def in steps_def:
            step = WorkflowStep(
                step_id=s_def["id"],
                role=s_def["role"],
                description=s_def["description"],
                dependencies=s_def.get("dependencies", []),
                inputs=s_def.get("inputs", {}),
            )
            steps[step.step_id] = step

        wf = Workflow(workflow_id=workflow_id, steps=steps)
        self._workflows[workflow_id] = wf
        logger.info("workflow_created id=%s steps=%d", workflow_id, len(steps))
        return wf

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self._workflows.get(workflow_id)

    async def send_message(
        self, workflow_id: str, sender: str, receiver: str, content: Any
    ):
        """Send a message between agents (Ticket 2)."""
        wf = self.get_workflow(workflow_id)
        if not wf:
            logger.warning("message_discarded invalid_workflow=%s", workflow_id)
            return

        msg = AgentMessage(sender, receiver, content, workflow_id)
        async with self._lock:
            self._message_log.append(msg)

        logger.info(
            "agent_message workflow=%s from=%s to=%s", workflow_id, sender, receiver
        )
        # In a real system, this would trigger a callback or queue event for the receiver agent mechanism

    def get_messages(self, workflow_id: str) -> List[Dict]:
        return [
            {
                "id": m.id,
                "from": m.sender_role,
                "to": m.receiver_role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in self._message_log
            if m.workflow_id == workflow_id
        ]


# Global singleton
workflow_manager = WorkflowManager()
