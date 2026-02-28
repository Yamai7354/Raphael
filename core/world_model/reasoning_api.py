"""
WORLD-413 — Environment Reasoning API.

Exposes world model data through a structured query interface.
Agents can query state, request optimal resources, evaluate
infrastructure options, and plan experiments.

Also serves as the data source for WORLD-412 (Dashboard).
"""

import logging
from dataclasses import dataclass

from .schema import WorldModelSchema, NodeType
from .hardware_registry import HardwareRegistry
from .model_capabilities import ModelCapabilityMap, ModelSpecialization
from .tool_registry import ToolRegistry
from .resource_awareness import ResourceAwareness
from .state_monitor import EnvironmentMonitor
from .hw_scheduler import HardwareAwareScheduler, TaskRequirements
from .infra_optimizer import InfraOptimizer
from .external_sources import ExternalSourceRegistry
from .topology import TopologyMap
from .forecasting import ResourceForecaster

logger = logging.getLogger("core.world_model.reasoning_api")


class EnvironmentReasoningAPI:
    """Unified query interface for the world model.

    Agents use this to reason about the environment, request
    resources, and plan tasks.
    """

    def __init__(
        self,
        schema: WorldModelSchema | None = None,
        hardware: HardwareRegistry | None = None,
        models: ModelCapabilityMap | None = None,
        tools: ToolRegistry | None = None,
        resources: ResourceAwareness | None = None,
        monitor: EnvironmentMonitor | None = None,
        scheduler: HardwareAwareScheduler | None = None,
        optimizer: InfraOptimizer | None = None,
        sources: ExternalSourceRegistry | None = None,
        topology: TopologyMap | None = None,
        forecaster: ResourceForecaster | None = None,
    ):
        self.schema = schema or WorldModelSchema()
        self.hardware = hardware or HardwareRegistry()
        self.models = models or ModelCapabilityMap()
        self.tools = tools or ToolRegistry()
        self.resources = resources or ResourceAwareness()
        self.monitor = monitor or EnvironmentMonitor(self.hardware, self.models, self.resources)
        self.scheduler = scheduler or HardwareAwareScheduler(
            self.hardware, self.models, self.resources
        )
        self.optimizer = optimizer or InfraOptimizer(self.resources, self.hardware)
        self.sources = sources or ExternalSourceRegistry()
        self.topology = topology or TopologyMap()
        self.forecaster = forecaster or ResourceForecaster(self.resources)

    # --- Agent-facing queries ---

    def query_system_state(self) -> dict:
        """Full system state snapshot for agent reasoning."""
        return {
            "hardware": self.hardware.get_stats(),
            "models": self.models.get_stats(),
            "tools": self.tools.get_stats(),
            "resources": self.resources.get_stats(),
            "topology": self.topology.get_stats(),
            "sources": self.sources.get_stats(),
        }

    def request_optimal_resource(
        self, task_type: str, requires_gpu: bool = False, min_ram_gb: float = 0
    ) -> dict:
        """Agent asks: what's the best machine + model for my task?"""
        hostname = self.resources.get_optimal_for_task(
            required_memory_gb=min_ram_gb,
            require_gpu=requires_gpu,
        )
        model = self.models.find_best_for_task(task_type, max_vram_gb=None)
        available_tools = self.tools.discover_by_capability(task_type)

        return {
            "recommended_host": hostname or "local",
            "recommended_model": model.name if model else None,
            "available_tools": [t.name for t in available_tools[:5]],
            "system_load": self.resources.get_stats(),
        }

    def evaluate_infrastructure(self) -> dict:
        """Run infra optimization analysis."""
        recs = self.optimizer.analyze()
        forecasts = self.forecaster.forecast_all(hours_ahead=1.0)
        alerts = [f.to_dict() for f in forecasts if f.alert]

        return {
            "recommendations": [r.to_dict() for r in recs],
            "forecast_alerts": alerts,
            "overloaded_machines": self.resources.get_overloaded(),
        }

    def plan_experiment(
        self, task_type: str, estimated_duration_hours: float, requires_gpu: bool = True
    ) -> dict:
        """Plan resource allocation for an experiment."""
        host = self.resources.get_optimal_for_task(
            required_memory_gb=8,
            require_gpu=requires_gpu,
        )
        model = self.models.find_best_for_task(task_type)
        forecasts = (
            self.forecaster.forecast_host(host, hours_ahead=estimated_duration_hours)
            if host
            else []
        )

        return {
            "recommended_host": host or "local",
            "recommended_model": model.name if model else None,
            "forecast": [f.to_dict() for f in forecasts],
            "risk": "high" if any(f.alert for f in forecasts) else "low",
        }

    # --- Dashboard data (WORLD-412) ---

    def get_dashboard_data(self) -> dict:
        """Complete data for the World Model Dashboard."""
        return {
            "machines": self.hardware.get_all(),
            "models": self.models.get_all(),
            "tools": self.tools.get_all(),
            "resources": self.resources.get_all_current(),
            "topology": {
                "nodes": self.topology.get_all_nodes(),
                "links": self.topology.get_all_links(),
            },
            "sources": self.sources.get_all(),
            "health": self.monitor.get_stats(),
            "optimizations": self.optimizer.get_recommendations(),
            "forecasts": self.forecaster.get_alerts(),
        }

    def get_status(self) -> dict:
        """Compact status for monitoring."""
        return {
            "schema": self.schema.get_stats(),
            "hardware": self.hardware.get_stats(),
            "models": self.models.get_stats(),
            "tools": self.tools.get_stats(),
            "resources": self.resources.get_stats(),
            "monitor": self.monitor.get_stats(),
            "topology": self.topology.get_stats(),
            "optimizer": self.optimizer.get_stats(),
            "sources": self.sources.get_stats(),
            "forecaster": self.forecaster.get_stats(),
        }
