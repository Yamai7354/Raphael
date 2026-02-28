"""
Swarm World Model & Environment Understanding — core/world_model package.

Structured representation of the system environment so the swarm
can reason about hardware, tools, infrastructure, and external resources.
"""

from .schema import WorldModelSchema, WorldNode, WorldRelationship
from .hardware_registry import HardwareRegistry, MachineRecord
from .model_capabilities import ModelCapabilityMap, ModelRecord
from .tool_registry import ToolRegistry, ToolRecord
from .resource_awareness import ResourceAwareness, ResourceSnapshot
from .state_monitor import EnvironmentMonitor
from .hw_scheduler import HardwareAwareScheduler
from .infra_optimizer import InfraOptimizer
from .external_sources import ExternalSourceRegistry, ExternalSource
from .topology import TopologyMap
from .forecasting import ResourceForecaster
from .reasoning_api import EnvironmentReasoningAPI
from .infra_improvement import InfraImprovementEngine

__all__ = [
    "WorldModelSchema",
    "WorldNode",
    "WorldRelationship",
    "HardwareRegistry",
    "MachineRecord",
    "ModelCapabilityMap",
    "ModelRecord",
    "ToolRegistry",
    "ToolRecord",
    "ResourceAwareness",
    "ResourceSnapshot",
    "EnvironmentMonitor",
    "HardwareAwareScheduler",
    "InfraOptimizer",
    "ExternalSourceRegistry",
    "ExternalSource",
    "TopologyMap",
    "ResourceForecaster",
    "EnvironmentReasoningAPI",
    "InfraImprovementEngine",
]
