"""
DISC-308 — Discovery Loop Scheduler.

Automates periodic execution of the full discovery pipeline:
opportunity detection → capability generation → prototype creation
→ sandbox experiments → evaluation → integration.
"""

import logging
import time
from dataclasses import dataclass, field

from .opportunities import OpportunityDetector
from .proposals import ProposalGenerator
from .prototype_designer import PrototypeDesigner
from .sandbox import PrototypeSandbox
from .evaluation import ExperimentEvaluator
from .integration import IntegrationEngine
from .approval import ApprovalGate
from .safety_controls import DiscoverySafetyControls

logger = logging.getLogger("core.discovery.discovery_scheduler")


@dataclass
class DiscoveryCycleResult:
    """Summary of one discovery loop cycle."""

    cycle_id: int
    opportunities_detected: int = 0
    proposals_generated: int = 0
    prototypes_created: int = 0
    sandbox_runs: int = 0
    evaluations_passed: int = 0
    integrations: int = 0
    rejected: int = 0
    duration_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "opportunities": self.opportunities_detected,
            "proposals": self.proposals_generated,
            "prototypes": self.prototypes_created,
            "sandbox_runs": self.sandbox_runs,
            "passed": self.evaluations_passed,
            "integrated": self.integrations,
            "rejected": self.rejected,
            "duration_s": round(self.duration_seconds, 2),
        }


class DiscoveryScheduler:
    """Orchestrates the full discovery cycle."""

    def __init__(
        self,
        detector: OpportunityDetector | None = None,
        proposal_gen: ProposalGenerator | None = None,
        designer: PrototypeDesigner | None = None,
        sandbox: PrototypeSandbox | None = None,
        evaluator: ExperimentEvaluator | None = None,
        integrator: IntegrationEngine | None = None,
        approval: ApprovalGate | None = None,
        safety: DiscoverySafetyControls | None = None,
        interval_seconds: float = 300,
    ):
        self.detector = detector or OpportunityDetector()
        self.proposals = proposal_gen or ProposalGenerator()
        self.designer = designer or PrototypeDesigner()
        self.sandbox = sandbox or PrototypeSandbox()
        self.evaluator = evaluator or ExperimentEvaluator()
        self.integrator = integrator or IntegrationEngine()
        self.approval = approval or ApprovalGate()
        self.safety = safety or DiscoverySafetyControls()
        self.interval_seconds = interval_seconds
        self._cycle_count = 0
        self._history: list[DiscoveryCycleResult] = []
        self._last_run: float = 0

    def should_run(self) -> bool:
        return time.time() - self._last_run >= self.interval_seconds

    def run_cycle(self, system_signals: dict | None = None) -> DiscoveryCycleResult:
        """Execute one full discovery cycle."""
        self._cycle_count += 1
        self._last_run = time.time()
        start = time.time()
        result = DiscoveryCycleResult(cycle_id=self._cycle_count)

        logger.info("=== Discovery Cycle %d START ===", self._cycle_count)

        # Safety check
        if not self.safety.can_start_cycle():
            logger.warning("Discovery cycle blocked by safety controls")
            result.duration_seconds = time.time() - start
            self._history.append(result)
            return result

        # 1. Opportunity detection
        opportunities = self.detector.get_unresolved()
        result.opportunities_detected = len(opportunities)

        # 2. Generate proposals (top 5 opportunities)
        for opp in opportunities[:5]:
            if not self.safety.can_create_prototype():
                break
            proposal = self.proposals.generate(opp)
            result.proposals_generated += 1

            # 3. Design prototype
            proto = self.designer.design(proposal)
            result.prototypes_created += 1

            # 4. Run in sandbox
            self.safety.record_prototype_start()
            sbx = self.sandbox.start(proto)
            # Simulate a few tasks (in production, these would be real tasks)
            import random

            for _ in range(10):
                success = random.random() > 0.3
                exec_ms = random.uniform(500, 8000)
                self.sandbox.record_task(
                    sbx.result_id, success, exec_ms, error=None if success else "simulated_error"
                )
            self.sandbox.stop(sbx.result_id)
            result.sandbox_runs += 1

            # 5. Evaluate
            sbx_result = self.sandbox.get_result(sbx.result_id)
            if sbx_result:
                eval_result = self.evaluator.evaluate(sbx_result)

                # 6. Approval gate
                decision = self.approval.check(eval_result)
                if decision.approved:
                    # 7. Integrate
                    self.integrator.integrate(proto, eval_result)
                    self.proposals.accept(proposal.proposal_id)
                    self.detector.resolve(opp.opportunity_id)
                    result.integrations += 1
                    result.evaluations_passed += 1
                else:
                    self.proposals.reject(proposal.proposal_id)
                    proto.status = "failed"
                    result.rejected += 1
                    self.safety.record_prototype_end()

        result.duration_seconds = time.time() - start
        self._history.append(result)
        logger.info(
            "=== Discovery Cycle %d END (%.2fs) integrated=%d rejected=%d ===",
            self._cycle_count,
            result.duration_seconds,
            result.integrations,
            result.rejected,
        )
        return result

    def get_history(self) -> list[dict]:
        return [r.to_dict() for r in self._history]

    def get_status(self) -> dict:
        return {
            "total_cycles": self._cycle_count,
            "last_run": self._last_run,
            "interval_seconds": self.interval_seconds,
            "opportunities": self.detector.get_stats(),
            "proposals": self.proposals.get_stats(),
            "prototypes": self.designer.get_stats(),
            "sandbox": self.sandbox.get_stats(),
            "evaluations": self.evaluator.get_stats(),
            "integrations": self.integrator.get_stats(),
            "approval": self.approval.get_stats(),
            "safety": self.safety.get_status(),
        }
