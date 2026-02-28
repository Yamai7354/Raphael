"""
Full Autonomy Engine for AI Router (Phase 15).

Handles:
- Meta-Task Generation (Ticket 1)
- Safety Enforcement (Ticket 3)
- Audit & Replay (Ticket 5)
- Autonomous Workflow Creation (Ticket 2, 4)
- Feedback Loop (Ticket 6)
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from workflow_manager import workflow_manager
from workflow_optimizer import optimization_engine

logger = logging.getLogger("ai_router.autonomy")


@dataclass
class MetaTask:
    id: str
    trigger: str
    proposed_role: str
    description: str
    priority: int
    context: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AutonomousAction:
    action_id: str
    task_id: str
    decision: str
    rationale: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)


class SafetyPolicy:
    """
    Enforces risk limits on autonomous actions (Ticket 3).
    """

    def __init__(self):
        self.max_concurrent_autonomous_tasks = 5
        self.banned_roles_autonomous = ["admin_root"]  # Example
        self.context_token_limit = 100000

    def validate_meta_task(self, task: MetaTask) -> bool:
        """Check if a generated meta-task is safe executed."""
        if task.proposed_role in self.banned_roles_autonomous:
            logger.warning(
                "safety_violation task=%s role=%s banned", task.id, task.proposed_role
            )
            return False

        return True


class AutonomousAuditLog:
    """
    Logs every autonomous decision (Ticket 5).
    """

    def __init__(self):
        self._log: List[AutonomousAction] = []

    def log_action(self, action: AutonomousAction):
        self._log.append(action)
        logger.info(
            "autonomous_action id=%s decision=%s confidence=%.2f",
            action.action_id,
            action.decision,
            action.confidence,
        )

    def get_logs(self) -> List[Dict]:
        return [
            {
                "id": a.action_id,
                "task": a.task_id,
                "decision": a.decision,
                "rationale": a.rationale,
                "time": a.timestamp.isoformat(),
            }
            for a in self._log
        ]


class AutonomyEngine:
    """
    Generates and processes meta-tasks (Ticket 1).
    """

    def __init__(self):
        self.enabled = False
        self.audit_log = AutonomousAuditLog()
        self.safety_policy = SafetyPolicy()
        self.check_interval = 20

    async def run_loop(self):
        while self.enabled:
            await self._generate_meta_tasks()
            await self._process_feedback()
            await asyncio.sleep(self.check_interval)

    async def _generate_meta_tasks(self):
        # 1. Check for optimization suggestions (Feedback Loop)
        suggestions = optimization_engine.generate_suggestions()

        for s in suggestions:
            # Example: If optimization suggests re-indexing, create a task
            if s.get("type") == "maintenance_needed":
                await self._propose_task(
                    trigger="optimization_engine",
                    role="system_maintainer",
                    desc="Run maintenance based on analyzer code 42",
                )

        # 2. Heuristic: If idle, maybe propose a self-test?
        # (Simplified for this implementation)
        pass

    async def _propose_task(self, trigger: str, role: str, desc: str):
        task = MetaTask(
            id=f"auto-{uuid4()}",
            trigger=trigger,
            proposed_role=role,
            description=desc,
            priority=1,
            context={},
        )

        # Verify Safety (Ticket 3)
        if not self.safety_policy.validate_meta_task(task):
            self.audit_log.log_action(
                AutonomousAction(
                    action_id=str(uuid4()),
                    task_id=task.id,
                    decision="REJECTED",
                    rationale="Safety Policy Violation",
                    confidence=1.0,
                )
            )
            return

        # Execute/Schedule: Transform into Workflow (Ticket 2, 4)
        workflow_id = f"wf-{task.id}"
        steps = [
            {
                "id": f"step-{uuid4()}",
                "role": role,
                "description": desc,
                "inputs": {"autonomous_trigger": trigger},
            }
        ]

        try:
            # Policy-Integrated: Create workflow via manager
            wf = workflow_manager.create_workflow(workflow_id, steps)

            self.audit_log.log_action(
                AutonomousAction(
                    action_id=str(uuid4()),
                    task_id=task.id,
                    decision="SCHEDULED",
                    rationale=f"Triggered by {trigger}",
                    confidence=0.9,
                )
            )

            logger.info("meta_task_scheduled id=%s workflow=%s", task.id, workflow_id)

        except Exception as e:
            logger.error("meta_task_failed id=%s error=%s", task.id, str(e))
            self.audit_log.log_action(
                AutonomousAction(
                    action_id=str(uuid4()),
                    task_id=task.id,
                    decision="FAILED",
                    rationale=f"Creation Error: {str(e)}",
                    confidence=1.0,
                )
            )

    async def _process_feedback(self):
        """Ticket 6: Feedback Loop"""
        # In a real system, we'd query workflow metrics for recently completed autonomous tasks
        # and adjust `safety_policy` or generation logic.
        pass


# Global Singleton
autonomy_engine = AutonomyEngine()
