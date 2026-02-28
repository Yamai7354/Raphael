"""
DISC-301 — Opportunity Detection Engine.

Monitors task failures, execution metrics, agent utilization,
and knowledge gaps to detect improvement opportunities.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.discovery.opportunities")


class OpportunityType(str, Enum):
    TASK_FAILURE = "task_failure"
    BOTTLENECK = "bottleneck"
    INEFFICIENCY = "inefficiency"
    MISSING_CAPABILITY = "missing_capability"
    KNOWLEDGE_GAP = "knowledge_gap"


class OpportunitySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Opportunity:
    """A detected improvement opportunity."""

    opportunity_id: str = field(default_factory=lambda: f"opp_{uuid.uuid4().hex[:8]}")
    opportunity_type: OpportunityType = OpportunityType.INEFFICIENCY
    severity: OpportunitySeverity = OpportunitySeverity.MEDIUM
    title: str = ""
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    impact_estimate: float = 0.5  # 0-1
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "type": self.opportunity_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "impact_estimate": round(self.impact_estimate, 3),
            "resolved": self.resolved,
        }


class OpportunityDetector:
    """Scans system signals to detect improvement opportunities."""

    def __init__(
        self,
        failure_threshold: int = 3,
        bottleneck_time_ms: float = 5000,
        utilization_low: float = 0.2,
    ):
        self.failure_threshold = failure_threshold
        self.bottleneck_time_ms = bottleneck_time_ms
        self.utilization_low = utilization_low
        self._opportunities: dict[str, Opportunity] = {}
        self._failure_counts: dict[str, int] = {}  # domain -> count
        self._execution_times: dict[str, list[float]] = {}  # task_type -> times

    def record_task_failure(
        self, domain: str, task_id: str, reason: str = ""
    ) -> Opportunity | None:
        """Record a failure — create opportunity if threshold reached."""
        self._failure_counts[domain] = self._failure_counts.get(domain, 0) + 1
        count = self._failure_counts[domain]

        if count >= self.failure_threshold:
            opp = Opportunity(
                opportunity_type=OpportunityType.TASK_FAILURE,
                severity=OpportunitySeverity.HIGH
                if count >= self.failure_threshold * 2
                else OpportunitySeverity.MEDIUM,
                title=f"Repeated failures in {domain} ({count} failures)",
                description=f"Domain '{domain}' has {count} failures. Latest: {reason}",
                evidence=[f"task:{task_id}", f"failures:{count}", f"reason:{reason}"],
                impact_estimate=min(1.0, count / (self.failure_threshold * 3)),
            )
            self._opportunities[opp.opportunity_id] = opp
            logger.info("opportunity_detected type=task_failure domain=%s count=%d", domain, count)
            return opp
        return None

    def record_execution_time(self, task_type: str, duration_ms: float) -> Opportunity | None:
        """Record task execution time — detect bottlenecks."""
        self._execution_times.setdefault(task_type, []).append(duration_ms)
        times = self._execution_times[task_type][-20:]  # last 20

        avg = sum(times) / len(times)
        if avg > self.bottleneck_time_ms and len(times) >= 5:
            opp = Opportunity(
                opportunity_type=OpportunityType.BOTTLENECK,
                severity=OpportunitySeverity.HIGH,
                title=f"Bottleneck in {task_type} (avg {avg:.0f}ms)",
                description=f"Average execution time for '{task_type}' is {avg:.0f}ms (threshold: {self.bottleneck_time_ms}ms)",
                evidence=[f"task_type:{task_type}", f"avg_ms:{avg:.0f}", f"samples:{len(times)}"],
                impact_estimate=min(1.0, avg / (self.bottleneck_time_ms * 3)),
            )
            self._opportunities[opp.opportunity_id] = opp
            return opp
        return None

    def detect_low_utilization(self, agents: list[dict]) -> list[Opportunity]:
        """Detect agents with low utilization."""
        opps: list[Opportunity] = []
        for agent in agents:
            utilization = agent.get("utilization", 0.0)
            name = agent.get("name", "unknown")
            if utilization < self.utilization_low:
                opp = Opportunity(
                    opportunity_type=OpportunityType.INEFFICIENCY,
                    severity=OpportunitySeverity.LOW,
                    title=f"Low utilization: {name} ({utilization:.0%})",
                    description=f"Agent '{name}' has {utilization:.0%} utilization",
                    evidence=[f"agent:{name}", f"utilization:{utilization:.2f}"],
                    impact_estimate=0.3,
                )
                self._opportunities[opp.opportunity_id] = opp
                opps.append(opp)
        return opps

    def detect_missing_capability(self, failed_tasks: list[dict]) -> list[Opportunity]:
        """Detect tasks that fail because no agent has the required capability."""
        opps: list[Opportunity] = []
        capability_gaps: dict[str, int] = {}
        for task in failed_tasks:
            required = task.get("required_capability", "")
            if required and task.get("failure_reason") == "no_capable_agent":
                capability_gaps[required] = capability_gaps.get(required, 0) + 1

        for cap, count in capability_gaps.items():
            opp = Opportunity(
                opportunity_type=OpportunityType.MISSING_CAPABILITY,
                severity=OpportunitySeverity.CRITICAL,
                title=f"Missing capability: {cap} ({count} failed tasks)",
                description=f"No agent can handle '{cap}'. {count} tasks failed.",
                evidence=[f"capability:{cap}", f"failed_tasks:{count}"],
                impact_estimate=min(1.0, count / 5),
            )
            self._opportunities[opp.opportunity_id] = opp
            opps.append(opp)
        return opps

    def resolve(self, opportunity_id: str) -> None:
        if opportunity_id in self._opportunities:
            self._opportunities[opportunity_id].resolved = True

    def get_unresolved(self) -> list[Opportunity]:
        return sorted(
            [o for o in self._opportunities.values() if not o.resolved],
            key=lambda o: o.impact_estimate,
            reverse=True,
        )

    def get_all(self) -> list[dict]:
        return [o.to_dict() for o in self._opportunities.values()]

    def get_stats(self) -> dict:
        unresolved = [o for o in self._opportunities.values() if not o.resolved]
        by_type: dict[str, int] = {}
        for o in unresolved:
            by_type[o.opportunity_type.value] = by_type.get(o.opportunity_type.value, 0) + 1
        return {
            "total": len(self._opportunities),
            "unresolved": len(unresolved),
            "by_type": by_type,
        }
