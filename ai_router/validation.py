"""
Output Validation Framework for AI Router.

Validates subtask outputs against expected types and constraints.
Provides pass/fail per subtask with traceability to planner output.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum

logger = logging.getLogger("ai_router.validation")


# =============================================================================
# VALIDATION RESULT
# =============================================================================


class ValidationStatus(str, Enum):
    """Status of a validation check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    """Result of validating a subtask output."""

    status: ValidationStatus
    message: str
    subtask_id: str
    planner_output_id: Optional[str] = None
    checks_passed: int = 0
    checks_failed: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, message: str = "") -> None:
        """Add a validation check result."""
        self.details.append(
            {
                "check": name,
                "passed": passed,
                "message": message,
            }
        )
        if passed:
            self.checks_passed += 1
        else:
            self.checks_failed += 1

    def is_valid(self) -> bool:
        """Check if validation passed."""
        return self.status == ValidationStatus.PASSED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "status": self.status.value,
            "message": self.message,
            "subtask_id": self.subtask_id,
            "planner_output_id": self.planner_output_id,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "details": self.details,
        }


# =============================================================================
# VALIDATION RULES
# =============================================================================


class ValidationRule:
    """Base class for validation rules."""

    def __init__(self, name: str, required: bool = True):
        self.name = name
        self.required = required

    def validate(
        self, output: Dict[str, Any], context: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Validate output against this rule.
        Returns (passed, message).
        """
        raise NotImplementedError


class NotEmptyRule(ValidationRule):
    """Validates that output is not empty."""

    def __init__(self, field: str = "result"):
        super().__init__(f"not_empty_{field}")
        self.field = field

    def validate(
        self, output: Dict[str, Any], context: Dict[str, Any]
    ) -> tuple[bool, str]:
        value = output.get(self.field)
        if value is None:
            return (False, f"Field '{self.field}' is missing")
        if isinstance(value, str) and not value.strip():
            return (False, f"Field '{self.field}' is empty string")
        if isinstance(value, (list, dict)) and len(value) == 0:
            return (False, f"Field '{self.field}' is empty collection")
        return (True, f"Field '{self.field}' is not empty")


class TypeRule(ValidationRule):
    """Validates that a field has expected type."""

    def __init__(self, field: str, expected_type: type, allow_none: bool = False):
        super().__init__(f"type_{field}_{expected_type.__name__}")
        self.field = field
        self.expected_type = expected_type
        self.allow_none = allow_none

    def validate(
        self, output: Dict[str, Any], context: Dict[str, Any]
    ) -> tuple[bool, str]:
        value = output.get(self.field)
        if value is None:
            if self.allow_none:
                return (True, f"Field '{self.field}' is None (allowed)")
            return (False, f"Field '{self.field}' is None")
        if not isinstance(value, self.expected_type):
            return (
                False,
                f"Field '{self.field}' expected {self.expected_type.__name__}, got {type(value).__name__}",
            )
        return (True, f"Field '{self.field}' has correct type")


class RegexRule(ValidationRule):
    """Validates that a string field matches a regex pattern."""

    def __init__(self, field: str, pattern: str, description: str = ""):
        super().__init__(f"regex_{field}")
        self.field = field
        self.pattern = re.compile(pattern)
        self.description = description or f"match pattern {pattern}"

    def validate(
        self, output: Dict[str, Any], context: Dict[str, Any]
    ) -> tuple[bool, str]:
        value = output.get(self.field, "")
        if not isinstance(value, str):
            return (False, f"Field '{self.field}' is not a string")
        if not self.pattern.search(value):
            return (False, f"Field '{self.field}' does not {self.description}")
        return (True, f"Field '{self.field}' matches pattern")


class LengthRule(ValidationRule):
    """Validates string/list length bounds."""

    def __init__(self, field: str, min_len: int = 0, max_len: int = float("inf")):
        super().__init__(f"length_{field}")
        self.field = field
        self.min_len = min_len
        self.max_len = max_len

    def validate(
        self, output: Dict[str, Any], context: Dict[str, Any]
    ) -> tuple[bool, str]:
        value = output.get(self.field)
        if value is None:
            return (False, f"Field '{self.field}' is missing")
        try:
            length = len(value)
        except TypeError:
            return (False, f"Field '{self.field}' has no length")

        if length < self.min_len:
            return (False, f"Field '{self.field}' too short: {length} < {self.min_len}")
        if length > self.max_len:
            return (False, f"Field '{self.field}' too long: {length} > {self.max_len}")
        return (True, f"Field '{self.field}' length OK: {length}")


class CustomRule(ValidationRule):
    """Custom validation with a callable."""

    def __init__(self, name: str, validator: Callable[[Dict, Dict], tuple[bool, str]]):
        super().__init__(name)
        self.validator = validator

    def validate(
        self, output: Dict[str, Any], context: Dict[str, Any]
    ) -> tuple[bool, str]:
        return self.validator(output, context)


# =============================================================================
# OUTPUT VALIDATOR
# =============================================================================


class OutputValidator:
    """
    Validates subtask outputs against configurable rules.

    Default rules are applied to all outputs; additional rules
    can be registered per subtask role or type.
    """

    def __init__(self):
        self._default_rules: List[ValidationRule] = [
            NotEmptyRule("result"),
            TypeRule("status", str),
        ]
        self._role_rules: Dict[str, List[ValidationRule]] = {}
        self._custom_rules: Dict[str, List[ValidationRule]] = {}

    def add_default_rule(self, rule: ValidationRule) -> None:
        """Add a rule applied to all outputs."""
        self._default_rules.append(rule)

    def add_role_rule(self, role: str, rule: ValidationRule) -> None:
        """Add a rule for a specific role."""
        if role not in self._role_rules:
            self._role_rules[role] = []
        self._role_rules[role].append(rule)

    def add_subtask_rule(self, subtask_id: str, rule: ValidationRule) -> None:
        """Add a rule for a specific subtask."""
        if subtask_id not in self._custom_rules:
            self._custom_rules[subtask_id] = []
        self._custom_rules[subtask_id].append(rule)

    def validate(
        self,
        subtask_id: str,
        output: Dict[str, Any],
        role: Optional[str] = None,
        planner_output_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate a subtask output.

        Returns ValidationResult with pass/fail status and details.
        """
        context = context or {}
        result = ValidationResult(
            status=ValidationStatus.PASSED,
            message="",
            subtask_id=subtask_id,
            planner_output_id=planner_output_id,
        )

        # Collect applicable rules
        rules: List[ValidationRule] = list(self._default_rules)
        if role and role in self._role_rules:
            rules.extend(self._role_rules[role])
        if subtask_id in self._custom_rules:
            rules.extend(self._custom_rules[subtask_id])

        # Run each rule
        for rule in rules:
            try:
                passed, message = rule.validate(output, context)
                result.add_check(rule.name, passed, message)

                if not passed and rule.required:
                    result.status = ValidationStatus.FAILED
                    result.message = f"Required check failed: {rule.name}"

            except Exception as e:
                result.add_check(rule.name, False, f"Error: {str(e)}")
                if rule.required:
                    result.status = ValidationStatus.FAILED
                    result.message = f"Validation error in {rule.name}: {str(e)}"

        # Set success message if all passed
        if result.status == ValidationStatus.PASSED:
            result.message = f"All {result.checks_passed} checks passed"

        # Log result
        logger.info(
            "validation_%s subtask=%s checks=%d/%d planner=%s",
            result.status.value,
            subtask_id,
            result.checks_passed,
            result.checks_passed + result.checks_failed,
            planner_output_id or "unknown",
        )

        return result


# =============================================================================
# STEP OUTPUT VALIDATOR
# =============================================================================


def validate_step_output(
    step,  # Step from orchestration
    output: Dict[str, Any],
    planner_output_id: Optional[str] = None,
) -> ValidationResult:
    """
    Convenience function to validate a step's output.
    Uses global validator instance.
    """
    return output_validator.validate(
        subtask_id=step.subtask_id,
        output=output,
        role=step.role,
        planner_output_id=planner_output_id,
    )


def validate_task_outputs(task) -> List[ValidationResult]:
    """
    Validate all completed step outputs in a task.
    Returns list of ValidationResults.
    """
    results = []
    for step in task.steps:
        if step.output_data:
            result = validate_step_output(
                step=step,
                output=step.output_data,
                planner_output_id=task.planner_output_id,
            )
            results.append(result)
    return results


# Global validator instance
output_validator = OutputValidator()
