"""
Swarm Operating System — core/swarm_os package.

Central orchestration layer unifying evolution, cognition,
discovery, world model, and memory into a single adaptive system.
"""

from .orchestrator import SwarmOrchestrator
from .task_manager import SwarmTaskManager, SwarmTask
from .resource_coordinator import ResourceCoordinator
from .telemetry import TelemetryHub, MetricSnapshot
from .policy_controller import PolicyController
from .comm_bus import SwarmCommBus, SwarmMessage
from .knowledge_controller import KnowledgeController
from .experiment_orchestrator import ExperimentOrchestrator
from .self_regulation import SelfRegulation
from .version_manager import VersionManager, VersionRecord
from .failsafe import FailSafe
from .analytics import SwarmAnalytics
from .integration_api import IntegrationAPI
from .emergent_behavior import EmergentBehaviorMonitor

__all__ = [
    "SwarmOrchestrator",
    "SwarmTaskManager",
    "SwarmTask",
    "ResourceCoordinator",
    "TelemetryHub",
    "MetricSnapshot",
    "PolicyController",
    "SwarmCommBus",
    "SwarmMessage",
    "KnowledgeController",
    "ExperimentOrchestrator",
    "SelfRegulation",
    "VersionManager",
    "VersionRecord",
    "FailSafe",
    "SwarmAnalytics",
    "IntegrationAPI",
    "EmergentBehaviorMonitor",
]
