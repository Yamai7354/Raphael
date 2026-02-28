"""
Global Runtime Policy for AI Router.

Codifies cluster-wide constraints that apply to all roles and nodes.
Policy is evaluated at startup and violations prevent server start.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from .roles import QuantizationPolicy
from core.understanding.schemas import Task, ExecutionMode
from .constraints import ethical_validator

logger = logging.getLogger("ai_router.policy")


class RiskScore(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RuntimePolicy:
    """
    Immutable cluster-wide policy constraints.
    Loaded at startup and enforced during routing.
    """

    # Context limits
    global_max_context_tokens: int = 32768

    # Quantization rules
    allowed_quantizations: tuple = (
        QuantizationPolicy.ANY,
        QuantizationPolicy.Q4_ONLY,
        QuantizationPolicy.Q8_ONLY,
        QuantizationPolicy.Q8_OR_HIGHER,
        QuantizationPolicy.FP16_ONLY,
    )
    default_quantization: QuantizationPolicy = QuantizationPolicy.Q8_OR_HIGHER

    # Safety constraints
    max_concurrent_requests_per_node: int = 2
    request_timeout_seconds: int = 120
    approval_required_threshold: RiskScore = RiskScore.HIGH

    # Forbidden mutations (things that cannot change at runtime)
    allow_runtime_role_changes: bool = False
    allow_runtime_policy_changes: bool = False

    # Ethical Enforcement
    ethical_enforcement_mode: str = "strict"  # strict, advisory, off


class PolicyValidator:
    """
    Validates configuration and requests against the runtime policy.
    """

    def __init__(self, policy: RuntimePolicy):
        self.policy = policy

    def validate_role_context(self, role_max_context: int) -> tuple[bool, str]:
        """
        Validate that a role's max_context_tokens doesn't exceed global limit.
        Returns (is_valid, error_message).
        """
        if role_max_context > self.policy.global_max_context_tokens:
            return (
                False,
                f"Role max_context_tokens ({role_max_context}) exceeds "
                f"global limit ({self.policy.global_max_context_tokens})",
            )
        return (True, "")

    def validate_request_context(self, token_count: int) -> tuple[bool, str]:
        """
        Validate that a request's token count doesn't exceed global limit.
        Returns (is_valid, error_message).
        """
        if token_count > self.policy.global_max_context_tokens:
            return (
                False,
                f"Request token count ({token_count}) exceeds "
                f"global limit ({self.policy.global_max_context_tokens})",
            )
        return (True, "")

    def validate_quantization(self, quant: QuantizationPolicy) -> tuple[bool, str]:
        """
        Validate that a quantization policy is allowed.
        Returns (is_valid, error_message).
        """
        if quant not in self.policy.allowed_quantizations:
            return (False, f"Quantization policy {quant.value} is not allowed")
        return (True, "")

    def evaluate_task_risk(
        self, task: Task, perception_context: Optional[dict] = None
    ) -> RiskScore:
        """
        Evaluate the risk level of a Task.
        Uses task analysis and perception context (e.g. system load).
        """
        role = task.agent_config.get("role", "general")
        task_id = getattr(task, "id", None) or getattr(task, "task_id", "unknown")
        base_risk = RiskScore.LOW

        # 1. CRITICAL: Safety-critical operations
        if role == "shell" or role == "sysadmin":
            return RiskScore.CRITICAL

        # 2. HIGH: Modifications to filesystem or state
        if task.execution_mode == ExecutionMode.COMMIT:
            base_risk = RiskScore.HIGH

        # 3. MEDIUM: Code generation, complex reasoning
        elif role == "coder" or role == "planner":
            base_risk = RiskScore.MEDIUM

        logger.info(
            f"debug_risk_eval task={task_id} role={role} exec_mode={task.execution_mode} base_risk={base_risk}"
        )

        # 4. Perception-based Risk Adjustment (Autonomous Risk Modeling)
        if perception_context:
            # Simple heuristic: If system is processing many events, it's "volatile"
            # In a real system, this would use anomaly scores or specific node load
            events_processed = perception_context.get("events_processed", 0)

            # If system is under heavy load, upgrade risk to ensure stricter validation/checks
            if events_processed > 100:
                if base_risk == RiskScore.LOW:
                    logger.warning(
                        f"risk_upgrade task={task_id} reason=high_system_load new_risk=MEDIUM"
                    )
                    return RiskScore.MEDIUM
                elif base_risk == RiskScore.MEDIUM:
                    logger.warning(
                        f"risk_upgrade task={task_id} reason=high_system_load new_risk=HIGH"
                    )
                    return RiskScore.HIGH

        return base_risk

    def requires_approval(self, risk_score: RiskScore) -> bool:
        """
        Check if a risk score requires manual approval.
        """
        threshold = self.policy.approval_required_threshold

        # Explicit numeric-like comparison for RiskScore
        risk_levels = {
            RiskScore.LOW: 0,
            RiskScore.MEDIUM: 1,
            RiskScore.HIGH: 2,
            RiskScore.CRITICAL: 3,
        }

        return risk_levels.get(risk_score, 0) >= risk_levels.get(threshold, 2)

    def validate_ethical_constraints(self, task: Task):
        """
        Validate task against ethical guardrails.
        """
        if self.policy.ethical_enforcement_mode == "off":
            from .constraints import ConstraintResult

            return ConstraintResult(is_safe=True)

        objective = getattr(task, "objective", None) or getattr(task, "description", "")
        constraints = getattr(task, "constraints", [])
        return ethical_validator.validate_objective(objective, constraints)


class PolicyRegistry:
    """
    Singleton registry for the runtime policy.
    Policy is loaded once at startup and is immutable.
    """

    def __init__(self):
        self._policy: Optional[RuntimePolicy] = None
        self._validator: Optional[PolicyValidator] = None
        self._loaded = False

    def load_from_config(self, policy_config: dict) -> None:
        """
        Load policy from configuration.
        Fails fast on any invalid configuration.
        """
        if self._loaded:
            raise RuntimeError("Policy already loaded. Registry is immutable.")

        try:
            # Parse quantization policies
            allowed_quants = policy_config.get("allowed_quantizations")
            if allowed_quants:
                parsed_quants = tuple(QuantizationPolicy(q) for q in allowed_quants)
            else:
                parsed_quants = RuntimePolicy.allowed_quantizations

            default_quant_str = policy_config.get(
                "default_quantization", "q8_or_higher"
            )
            default_quant = QuantizationPolicy(default_quant_str)

            self._policy = RuntimePolicy(
                global_max_context_tokens=policy_config.get(
                    "global_max_context_tokens", RuntimePolicy.global_max_context_tokens
                ),
                allowed_quantizations=parsed_quants,
                default_quantization=default_quant,
                max_concurrent_requests_per_node=policy_config.get(
                    "max_concurrent_requests_per_node",
                    RuntimePolicy.max_concurrent_requests_per_node,
                ),
                request_timeout_seconds=policy_config.get(
                    "request_timeout_seconds", RuntimePolicy.request_timeout_seconds
                ),
                approval_required_threshold=RiskScore(
                    policy_config.get("approval_required_threshold", "high")
                ),
                allow_runtime_role_changes=policy_config.get(
                    "allow_runtime_role_changes",
                    RuntimePolicy.allow_runtime_role_changes,
                ),
                allow_runtime_policy_changes=policy_config.get(
                    "allow_runtime_policy_changes",
                    RuntimePolicy.allow_runtime_policy_changes,
                ),
                ethical_enforcement_mode=policy_config.get(
                    "ethical_enforcement_mode",
                    RuntimePolicy.ethical_enforcement_mode,
                ),
            )

            self._validator = PolicyValidator(self._policy)
            self._loaded = True

            logger.info(
                "policy_loaded global_max_context=%d default_quant=%s timeout=%ds",
                self._policy.global_max_context_tokens,
                self._policy.default_quantization.value,
                self._policy.request_timeout_seconds,
            )

        except Exception as e:
            raise ValueError(f"Invalid policy configuration: {e}")

    def load_defaults(self) -> None:
        """Load default policy if no config provided."""
        if self._loaded:
            return
        self._policy = RuntimePolicy()
        self._validator = PolicyValidator(self._policy)
        self._loaded = True
        logger.info("policy_loaded_defaults")

    @property
    def policy(self) -> RuntimePolicy:
        """Get the active policy."""
        if not self._loaded:
            raise RuntimeError("Policy not loaded")
        return self._policy

    @property
    def validator(self) -> PolicyValidator:
        """Get the policy validator."""
        if not self._loaded:
            raise RuntimeError("Policy not loaded")
        return self._validator

    def is_loaded(self) -> bool:
        """Check if policy has been loaded."""
        return self._loaded


# Global singleton instance
policy_registry = PolicyRegistry()
