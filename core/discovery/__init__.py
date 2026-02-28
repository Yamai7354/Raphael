"""
Autonomous Discovery Engine — core/discovery package.

Enables the swarm to discover opportunities, design new capabilities,
prototype improvements, and integrate validated upgrades.
"""

from .opportunities import OpportunityDetector, Opportunity
from .proposals import CapabilityProposal, ProposalGenerator
from .capability_registry import CapabilityRegistry, CapabilityRecord
from .prototype_designer import PrototypeDesigner, PrototypeSpec
from .sandbox import PrototypeSandbox, SandboxResult
from .evaluation import ExperimentEvaluator, EvaluationResult
from .integration import IntegrationEngine
from .approval import ApprovalGate
from .discovery_scheduler import DiscoveryScheduler
from .safety_controls import DiscoverySafetyControls
from .role_expansion import RoleExpansion
from .capability_tracking import CapabilityTracker
from .innovation_scoring import InnovationScorer

__all__ = [
    "OpportunityDetector",
    "Opportunity",
    "ProposalGenerator",
    "CapabilityProposal",
    "CapabilityRegistry",
    "CapabilityRecord",
    "PrototypeDesigner",
    "PrototypeSpec",
    "PrototypeSandbox",
    "SandboxResult",
    "ExperimentEvaluator",
    "EvaluationResult",
    "IntegrationEngine",
    "ApprovalGate",
    "DiscoveryScheduler",
    "DiscoverySafetyControls",
    "RoleExpansion",
    "CapabilityTracker",
    "InnovationScorer",
]
