"""
Swarm Director — Phase 4: Orchestration Brain

The Director is the central control loop that:
  1. Observes incoming tasks (TaskManager)
  2. Queries the knowledge graph for solutions (GraphReasoner)
  3. Selects the best habitat blueprint (HabitatSelector)
  4. Deploys/destroys Helm charts (HelmController)
  5. Monitors running habitats (HabitatMonitor)
"""


def __getattr__(name):
    """Lazy imports to avoid loading neo4j driver unless needed."""
    _imports = {
        "TaskManager": ("director.task_manager", "TaskManager"),
        "GraphReasoner": ("director.graph_reasoner", "GraphReasoner"),
        "HabitatSelector": ("director.habitat_selector", "HabitatSelector"),
        "HelmController": ("director.helm_controller", "HelmController"),
        "HabitatMonitor": ("director.habitat_monitor", "HabitatMonitor"),
        "HardwareScheduler": ("director.hardware_scheduler", "HardwareScheduler"),
        "HabitatMetrics": ("director.habitat_metrics", "HabitatMetrics"),
        "SwarmDirector": ("director.director", "SwarmDirector"),
    }
    if name in _imports:
        module_path, attr = _imports[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, attr)
    raise AttributeError(f"module 'director' has no attribute {name}")


__all__ = [
    "TaskManager",
    "GraphReasoner",
    "HabitatSelector",
    "HelmController",
    "HabitatMonitor",
    "HardwareScheduler",
    "HabitatMetrics",
    "SwarmDirector",
]
