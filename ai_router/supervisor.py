"""
Supervisor Execution Loop for AI Router.

Executes tasks step-by-step according to planner output.
Enforces role assignment, context limits, and execution order.
"""

import logging
import asyncio
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

from .orchestration import (
    Task,
    Step,
    TaskStatus,
    StepStatus,
)

logger = logging.getLogger("ai_router.supervisor")


# =============================================================================
# EXECUTION RESULT
# =============================================================================


@dataclass
class StepResult:
    """Result of executing a single step."""

    success: bool
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_sec: float = 0.0


@dataclass
class TaskResult:
    """Result of executing a complete task."""

    task_id: str
    success: bool
    status: TaskStatus
    steps_completed: int
    steps_failed: int
    total_duration_sec: float
    final_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# =============================================================================
# SUPERVISOR
# =============================================================================


class Supervisor:
    """
    Orchestrates multi-step task execution.

    Responsibilities:
    - Call planner endpoint for task decomposition
    - Execute steps in order respecting parallelism
    - Validate step outputs
    - Handle retries and escalation
    - Maintain task state
    """

    def __init__(
        self,
        max_concurrent_steps: int = 2,
        step_timeout_sec: float = 60.0,
    ):
        self.max_concurrent_steps = max_concurrent_steps
        self.step_timeout_sec = step_timeout_sec
        self._running_tasks: Dict[str, asyncio.Task] = {}

    async def plan_task(self, task: Task) -> bool:
        """
        Call planner endpoint for task decomposition.
        Returns True if planning succeeded.
        """
        task.status = TaskStatus.PLANNING
        task.started_at = datetime.now()

        logger.info(
            "task_planning task_id=%s objective=%s", task.task_id, task.objective[:50]
        )

        try:
            # Import here to avoid circular imports
            from .planner import PlanRequest, planner_registry, validate_plan

            # Build plan request
            plan_request = PlanRequest(
                task_id=task.task_id,
                objective=task.objective,
                constraints=task.constraints,
                context=task.context,
            )

            # Call planner (internal, not HTTP)
            planner_func = planner_registry.get_planner("1")
            plan = planner_func(plan_request, "1")

            # Validate plan
            is_valid, error = validate_plan(plan)
            if not is_valid:
                task.status = TaskStatus.FAILED
                task.error_message = f"Plan validation failed: {error}"
                logger.error(
                    "task_planning_failed task_id=%s error=%s", task.task_id, error
                )
                return False

            # Store plan info
            task.plan_hash = plan.metadata.plan_hash

            # Convert plan subtasks to steps
            subtasks = [s.model_dump() for s in plan.subtasks]
            task.set_steps_from_planner(subtasks)

            logger.info(
                "task_planned task_id=%s steps=%d hash=%s",
                task.task_id,
                len(task.steps),
                task.plan_hash,
            )
            return True

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Planning error: {str(e)}"
            logger.error(
                "task_planning_error task_id=%s error=%s", task.task_id, str(e)
            )
            return False

    async def execute_task(self, task: Task) -> TaskResult:
        """
        Execute all steps of a task.
        Returns TaskResult with final status.
        """
        # If the task is already approved, transition to READY if not already,
        # to allow execution to proceed without re-planning or re-approval.
        if task.approved and task.status != TaskStatus.READY:
            task.status = TaskStatus.READY

        if task.status != TaskStatus.READY:
            # Need to plan first
            if not await self.plan_task(task):
                return TaskResult(
                    task_id=task.task_id,
                    success=False,
                    status=task.status,
                    steps_completed=0,
                    steps_failed=1,
                    total_duration_sec=0,
                    error=task.error_message,
                )

        task.status = TaskStatus.EXECUTING
        task.started_at = datetime.now()

        from .policy import policy_registry
        from .perception import perception_service

        # Phase 6: Ethical Constraint Engine
        ethic_result = policy_registry.validator.validate_ethical_constraints(task)
        if not ethic_result.is_safe:
            task.ethical_violations = [v.value for v in ethic_result.violations]
            if policy_registry.policy.ethical_enforcement_mode == "strict":
                task.status = TaskStatus.FAILED
                task.error_message = (
                    f"Ethical policy violation: {ethic_result.reasoning}"
                )
                logger.error(
                    "task_ethical_blocked task_id=%s violations=%s",
                    task.task_id,
                    task.ethical_violations,
                )
                return TaskResult(
                    task_id=task.task_id,
                    success=False,
                    status=task.status,
                    steps_completed=0,
                    steps_failed=1,
                    total_duration_sec=0,
                    error=task.error_message,
                )
            elif policy_registry.policy.ethical_enforcement_mode == "advisory":
                if not task.approved:
                    task.status = TaskStatus.AWAITING_APPROVAL
                    logger.warning(
                        "task_ethical_advisory_awaiting_approval task_id=%s violations=%s",
                        task.task_id,
                        task.ethical_violations,
                    )
                    return TaskResult(
                        task_id=task.task_id,
                        success=False,
                        status=task.status,
                        steps_completed=0,
                        steps_failed=0,
                        total_duration_sec=0,
                        error=f"Task flagged for ethical review: {ethic_result.reasoning}",
                    )

        # Existing Risk Assessment
        risk_score = policy_registry.validator.evaluate_task_risk(
            task, perception_service.get_state()
        )

        if not task.approved and policy_registry.validator.requires_approval(
            risk_score
        ):
            task.status = TaskStatus.AWAITING_APPROVAL
            logger.warning(
                "task_approval_required task_id=%s risk=%s",
                task.task_id,
                risk_score.value,
            )
            return TaskResult(
                task_id=task.task_id,
                success=False,
                status=task.status,
                steps_completed=0,
                steps_failed=0,
                total_duration_sec=0,
                error="Task requires manual approval due to high risk",
            )

        logger.info("task_executing task_id=%s steps=%d", task.task_id, len(task.steps))

        # Execute steps in order
        while not task.check_completion():
            executable = task.get_executable_steps()

            if not executable:
                # Check if we're blocked or done
                pending = [
                    s
                    for s in task.steps
                    if s.status in (StepStatus.PENDING, StepStatus.BLOCKED)
                ]
                if pending:
                    # Still have pending but none executable - might be blocked
                    await asyncio.sleep(0.1)
                    continue
                break

            # Execute steps (respecting parallelism)
            if len(executable) > 1:
                # Parallel execution
                results = await asyncio.gather(
                    *[
                        self.execute_step(task, step)
                        for step in executable[: self.max_concurrent_steps]
                    ],
                    return_exceptions=True,
                )
                for step, result in zip(
                    executable[: self.max_concurrent_steps], results
                ):
                    if isinstance(result, Exception):
                        step.mark_failed(str(result))
                    # Results already applied in execute_step
            else:
                # Sequential execution
                await self.execute_step(task, executable[0])

        # Calculate final result
        completed = sum(1 for s in task.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in task.steps if s.status == StepStatus.FAILED)
        duration = (
            (task.completed_at - task.started_at).total_seconds()
            if task.completed_at and task.started_at
            else 0
        )

        return TaskResult(
            task_id=task.task_id,
            success=task.status == TaskStatus.COMPLETED,
            status=task.status,
            steps_completed=completed,
            steps_failed=failed,
            total_duration_sec=duration,
            final_output=task.state_blob,
            error=task.error_message,
        )

    async def execute_step(self, task: Task, step: Step) -> StepResult:
        """
        Execute a single step on an appropriate node.
        """
        start_time = datetime.now()

        try:
            # Build context for this step
            context = self.build_step_context(task, step)

            # Find compatible node for this step's role
            node_id = await self._select_node_for_step(step)

            if not node_id:
                step.mark_failed("No compatible node available")
                return StepResult(success=False, error="No compatible node")

            step.mark_executing(node_id)

            # Execute on node
            result = await self._invoke_role_on_node(
                node_id=node_id,
                role=step.role,
                subtask=step,
                context=context,
            )

            if result.success:
                # Validate output before marking complete
                from .validation import validate_step_output, ValidationStatus

                validation = validate_step_output(
                    step=step,
                    output=result.output or {},
                    planner_output_id=task.planner_output_id,
                )

                if validation.status == ValidationStatus.PASSED:
                    step.mark_completed(result.output or {})
                    task.update_state(step)
                else:
                    # Validation failed - treat as step failure
                    logger.warning(
                        "step_validation_failed subtask=%s reason=%s",
                        step.subtask_id,
                        validation.message,
                    )
                    step.mark_failed(f"Validation failed: {validation.message}")

                    if step.can_retry():
                        return await self.execute_step(task, step)
            else:
                step.mark_failed(result.error or "Unknown error")

                # Retry if possible
                if step.can_retry():
                    return await self.execute_step(task, step)

            return result

        except asyncio.TimeoutError:
            step.mark_failed("Step execution timeout")
            return StepResult(
                success=False,
                error="Timeout",
                duration_sec=(datetime.now() - start_time).total_seconds(),
            )
        except Exception as e:
            step.mark_failed(str(e))
            return StepResult(
                success=False,
                error=str(e),
                duration_sec=(datetime.now() - start_time).total_seconds(),
            )

    def build_step_context(self, task: Task, step: Step) -> Dict[str, Any]:
        """
        Build context for a step execution.
        Only includes required_context fields from task state.
        Enforces context size limits per step.
        """
        from .context import estimate_token_count
        import json

        context: Dict[str, Any] = {}
        max_context_tokens = 8192  # Default step context limit

        for req in step.required_context:
            if req == "objective":
                context["objective"] = task.objective
            elif req == "constraints":
                context["constraints"] = task.constraints
            elif req == "context":
                context["context"] = task.context
            elif req in task.state_blob:
                context[req] = task.state_blob[req]
            else:
                # Check completed steps for matching output
                for prev in task.steps:
                    if prev.status == StepStatus.COMPLETED and prev.output_data:
                        if prev.subtask_id in req or any(
                            k in req for k in prev.output_data.keys()
                        ):
                            context[req] = prev.output_data
                            break

        # Estimate and log context size
        context_str = json.dumps(context, default=str)
        context_tokens = estimate_token_count(context_str)

        # Truncate if over budget
        if context_tokens > max_context_tokens:
            logger.warning(
                "step_context_truncated subtask=%s tokens=%d limit=%d",
                step.subtask_id,
                context_tokens,
                max_context_tokens,
            )
            # Keep essential parts, truncate large outputs
            for key in list(context.keys()):
                if key not in ["objective", "constraints"]:
                    value_str = json.dumps(context[key], default=str)
                    if estimate_token_count(value_str) > max_context_tokens // 2:
                        # Truncate to first 4000 chars
                        if isinstance(context[key], str):
                            context[key] = context[key][:4000] + "... (truncated)"
                        elif (
                            isinstance(context[key], dict) and "result" in context[key]
                        ):
                            result = context[key]["result"]
                            if isinstance(result, str) and len(result) > 4000:
                                context[key]["result"] = (
                                    result[:4000] + "... (truncated)"
                                )

            context_tokens = estimate_token_count(json.dumps(context, default=str))

        logger.info(
            "step_context_built subtask=%s tokens=%d fields=%d",
            step.subtask_id,
            context_tokens,
            len(context),
        )

        return context

    async def _select_node_for_step(self, step: Step) -> Optional[str]:
        """
        Select appropriate node based on step's role.
        Uses load manager for capacity and circuit breaker for health.
        """
        try:
            from .state_cache import node_cache
            from .node_state import NodeState
            from .load_manager import load_manager
            from .circuit_breaker import circuit_breaker_registry

            # Get online nodes
            nodes = node_cache.list_online_nodes()
            if not nodes:
                logger.warning("no_online_nodes")
                return None

            # Filter to eligible node IDs (any state that isn't OFFLINE)
            eligible_ids = [n.node_id for n in nodes]

            # Filter by circuit breaker (remove nodes in cooldown)
            available_ids = circuit_breaker_registry.get_available_nodes(eligible_ids)
            if not available_ids:
                logger.warning("all_nodes_circuit_open eligible=%d", len(eligible_ids))
                return None

            # Use load manager to select best node
            selected = load_manager.select_best_node(available_ids)

            if selected:
                # Register node if not already tracked
                load_manager.register_node(selected)

            return selected

        except Exception as e:
            logger.error(
                "node_selection_failed step=%s error=%s", step.subtask_id, str(e)
            )
            return None

    async def _invoke_role_on_node(
        self,
        node_id: str,
        role: str,
        subtask: Step,
        context: Dict[str, Any],
    ) -> StepResult:
        """
        Invoke a specialist role on a node with subtask.
        Specialist only sees subtask description and context, never full objective.
        """
        import httpx
        import json

        try:
            # Get node URL from config
            config = self._get_config()
            node_url = None
            timeout = 30.0

            for node in config.get("nodes", []):
                if node["id"] == node_id:
                    node_url = node["url"]
                    timeout = node.get("timeout", 30.0)
                    break

            if not node_url:
                return StepResult(success=False, error=f"Node {node_id} not found")

            # Build request - specialist sees ONLY subtask, not full objective
            messages = [
                {
                    "role": "system",
                    "content": "You are a specialist executing a subtask. Focus only on the given task.",
                },
                {
                    "role": "user",
                    "content": f"Task: {subtask.description}\n\nContext: {json.dumps(context, indent=2)}",
                },
            ]

            # Resolve model
            model_id = None
            try:
                from .model_mapping import model_mapping_registry
                from .capabilities import capability_registry

                caps = capability_registry.get_capabilities(node_id)
                if caps:
                    model_spec = model_mapping_registry.select_model_for_role(
                        role, list(caps.hosted_models), caps.max_context_supported
                    )
                    if model_spec:
                        model_id = model_spec.model_id
            except Exception as e:
                logger.warning(
                    "model_resolution_failed node=%s role=%s error=%s",
                    node_id,
                    role,
                    str(e),
                )

            # Fallback to any hosted model if resolution fails
            if not model_id and caps and caps.hosted_models:
                model_id = caps.hosted_models[0]
                logger.warning(
                    "using_fallback_model node=%s model=%s", node_id, model_id
                )

            if not model_id:
                # If still no model, Ollama might fail with 400
                logger.warning("no_model_available node=%s role=%s", node_id, role)

            request_body = {
                "model": model_id,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
            }

            start = datetime.now()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{node_url.rstrip('/')}/chat/completions",
                    json=request_body,
                    timeout=timeout,
                )

                if response.status_code != 200:
                    return StepResult(
                        success=False,
                        error=f"Node returned {response.status_code}",
                        duration_sec=(datetime.now() - start).total_seconds(),
                    )

                result = response.json()

                # Extract output
                output = {
                    "result": result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", ""),
                    "status": "completed",
                    "node_id": node_id,
                }

                return StepResult(
                    success=True,
                    output=output,
                    duration_sec=(datetime.now() - start).total_seconds(),
                )

        except httpx.TimeoutException:
            return StepResult(success=False, error="Request timeout")
        except Exception as e:
            return StepResult(success=False, error=str(e))

    def _get_config(self) -> Dict[str, Any]:
        """Get config from main module."""
        try:
            from . import main

            return main.config
        except Exception:
            return {}


# Global singleton
supervisor = Supervisor()
