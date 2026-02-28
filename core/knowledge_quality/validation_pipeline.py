"""
KQ-604 — Knowledge Validation Pipeline.

Requires validation before knowledge becomes trusted:
multi-agent agreement, experiment results, source verification.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.knowledge_quality.validation")


class ValidationMethod(str, Enum):
    AGENT_AGREEMENT = "agent_agreement"
    EXPERIMENT = "experiment"
    SOURCE_VERIFICATION = "source_verification"
    MANUAL_REVIEW = "manual_review"


class ValidationStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    VALIDATED = "validated"
    REJECTED = "rejected"


@dataclass
class ValidationRecord:
    """A validation attempt for a knowledge node."""

    record_id: str = field(default_factory=lambda: f"vr_{uuid.uuid4().hex[:8]}")
    node_id: str = ""
    method: ValidationMethod = ValidationMethod.AGENT_AGREEMENT
    status: ValidationStatus = ValidationStatus.PENDING
    validators: list[str] = field(default_factory=list)  # agents who validated
    required_validators: int = 2
    confidence: float = 0.0
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "method": self.method.value,
            "status": self.status.value,
            "validators": self.validators,
            "confidence": round(self.confidence, 3),
        }


class ValidationPipeline:
    """Manages the knowledge validation workflow."""

    def __init__(self, required_validators: int = 2, min_confidence_for_validation: float = 0.6):
        self.required_validators = required_validators
        self.min_confidence = min_confidence_for_validation
        self._records: dict[str, ValidationRecord] = {}
        self._by_node: dict[str, str] = {}  # node_id -> record_id

    def submit(
        self, node_id: str, method: ValidationMethod = ValidationMethod.AGENT_AGREEMENT
    ) -> ValidationRecord:
        """Submit knowledge for validation."""
        if node_id in self._by_node:
            return self._records[self._by_node[node_id]]

        record = ValidationRecord(
            node_id=node_id,
            method=method,
            required_validators=self.required_validators,
        )
        self._records[record.record_id] = record
        self._by_node[node_id] = record.record_id
        logger.info("validation_submitted node=%s method=%s", node_id, method.value)
        return record

    def add_validation(
        self, node_id: str, validator: str, confidence: float, approve: bool
    ) -> ValidationRecord | None:
        """An agent provides a validation vote."""
        rid = self._by_node.get(node_id)
        if not rid or rid not in self._records:
            return None
        record = self._records[rid]
        if record.status in (ValidationStatus.VALIDATED, ValidationStatus.REJECTED):
            return record

        record.status = ValidationStatus.IN_REVIEW
        if validator not in record.validators:
            record.validators.append(validator)

        # Update confidence as running average
        n = len(record.validators)
        record.confidence = ((record.confidence * (n - 1)) + confidence) / n

        # Check if enough validators have weighed in
        if n >= record.required_validators:
            if approve and record.confidence >= self.min_confidence:
                record.status = ValidationStatus.VALIDATED
                record.completed_at = time.time()
                logger.info(
                    "knowledge_validated node=%s confidence=%.2f", node_id, record.confidence
                )
            elif not approve:
                record.status = ValidationStatus.REJECTED
                record.completed_at = time.time()

        return record

    def get_status(self, node_id: str) -> str:
        rid = self._by_node.get(node_id)
        if not rid:
            return "unvalidated"
        record = self._records.get(rid)
        return record.status.value if record else "unvalidated"

    def get_pending(self) -> list[ValidationRecord]:
        return [
            r
            for r in self._records.values()
            if r.status in (ValidationStatus.PENDING, ValidationStatus.IN_REVIEW)
        ]

    def get_stats(self) -> dict:
        by_status: dict[str, int] = {}
        for r in self._records.values():
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        return {"total": len(self._records), "by_status": by_status}
