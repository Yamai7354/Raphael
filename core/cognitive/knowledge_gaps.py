"""
COG-201 — Knowledge Gap Detection Engine.

Analyzes swarm memory and embeddings to identify sparse clusters,
repeated failures, outdated nodes, and inconsistencies.
Generates gap reports and seeds research missions.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("swarm.cognition.knowledge_gaps")


class GapSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GapType(str, Enum):
    SPARSE = "sparse_cluster"
    INCONSISTENT = "inconsistent"
    FAILURE_PATTERN = "failure_pattern"
    OUTDATED = "outdated"
    MISSING = "missing"


@dataclass
class KnowledgeGap:
    """A detected gap in the swarm's collective knowledge."""

    gap_id: str
    domain: str
    gap_type: GapType
    severity: GapSeverity
    description: str
    evidence: list[str] = field(default_factory=list)
    failure_count: int = 0
    embedding_density: float = 0.0
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    mission_generated: bool = False

    def to_dict(self) -> dict:
        return {
            "gap_id": self.gap_id,
            "domain": self.domain,
            "gap_type": self.gap_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "failure_count": self.failure_count,
            "embedding_density": round(self.embedding_density, 2),
            "resolved": self.resolved,
            "mission_generated": self.mission_generated,
        }


class KnowledgeGapDetector:
    """Continuously analyzes swarm knowledge to detect gaps."""

    SPARSE_THRESHOLD = 0.2
    FAILURE_THRESHOLD = 3
    STALE_AGE_SECONDS = 604800  # 7 days

    def __init__(self):
        self._gaps: dict[str, KnowledgeGap] = {}
        self._domain_failures: dict[str, int] = {}
        self._scan_count: int = 0

    def record_failure(self, domain: str, context: str = "") -> None:
        self._domain_failures[domain] = self._domain_failures.get(domain, 0) + 1
        if self._domain_failures[domain] >= self.FAILURE_THRESHOLD:
            gap_id = f"gap_fail_{domain}"
            if gap_id not in self._gaps:
                self._gaps[gap_id] = KnowledgeGap(
                    gap_id=gap_id,
                    domain=domain,
                    gap_type=GapType.FAILURE_PATTERN,
                    severity=GapSeverity.HIGH,
                    description=f"Repeated failures in {domain} ({self._domain_failures[domain]} failures)",
                    failure_count=self._domain_failures[domain],
                    evidence=[context] if context else [],
                )
                logger.warning(
                    "gap_detected type=failure domain=%s count=%d",
                    domain,
                    self._domain_failures[domain],
                )

    def record_sparse_area(self, domain: str, density: float) -> None:
        if density < self.SPARSE_THRESHOLD:
            gap_id = f"gap_sparse_{domain}"
            self._gaps[gap_id] = KnowledgeGap(
                gap_id=gap_id,
                domain=domain,
                gap_type=GapType.SPARSE,
                severity=GapSeverity.MEDIUM if density > 0.1 else GapSeverity.HIGH,
                description=f"Sparse knowledge in {domain} (density={density:.2f})",
                embedding_density=density,
            )

    def flag_outdated(self, domain: str, last_update: float) -> None:
        age = time.time() - last_update
        if age > self.STALE_AGE_SECONDS:
            gap_id = f"gap_stale_{domain}"
            self._gaps[gap_id] = KnowledgeGap(
                gap_id=gap_id,
                domain=domain,
                gap_type=GapType.OUTDATED,
                severity=GapSeverity.MEDIUM,
                description=f"Knowledge in {domain} is {age / 86400:.0f} days old",
            )

    def flag_inconsistency(self, domain: str, description: str) -> None:
        gap_id = f"gap_inconsist_{domain}_{uuid.uuid4().hex[:6]}"
        self._gaps[gap_id] = KnowledgeGap(
            gap_id=gap_id,
            domain=domain,
            gap_type=GapType.INCONSISTENT,
            severity=GapSeverity.HIGH,
            description=description,
        )

    def flag_missing(self, domain: str, description: str) -> None:
        gap_id = f"gap_missing_{domain}_{uuid.uuid4().hex[:6]}"
        self._gaps[gap_id] = KnowledgeGap(
            gap_id=gap_id,
            domain=domain,
            gap_type=GapType.MISSING,
            severity=GapSeverity.CRITICAL,
            description=description,
        )

    def run_scan(
        self, domain_densities: dict[str, float] | None = None
    ) -> list[KnowledgeGap]:
        self._scan_count += 1
        new_gaps = []
        if domain_densities:
            for domain, density in domain_densities.items():
                if density < self.SPARSE_THRESHOLD:
                    gap_id = f"gap_sparse_{domain}"
                    if gap_id not in self._gaps:
                        self.record_sparse_area(domain, density)
                        new_gaps.append(self._gaps[gap_id])
        logger.info(
            "gap_scan cycle=%d total=%d new=%d",
            self._scan_count,
            len(self._gaps),
            len(new_gaps),
        )
        return new_gaps

    def resolve_gap(self, gap_id: str) -> None:
        gap = self._gaps.get(gap_id)
        if gap:
            gap.resolved = True

    def get_unresolved(self) -> list[KnowledgeGap]:
        return [g for g in self._gaps.values() if not g.resolved]

    def get_report(self) -> dict:
        unresolved = self.get_unresolved()
        return {
            "total_gaps": len(self._gaps),
            "unresolved": len(unresolved),
            "by_severity": {
                s.value: len([g for g in unresolved if g.severity == s])
                for s in GapSeverity
            },
            "by_type": {
                t.value: len([g for g in unresolved if g.gap_type == t])
                for t in GapType
            },
            "gaps": [g.to_dict() for g in unresolved],
        }
