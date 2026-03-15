# Swarm Director

The **Swarm Director** (`director/swarm_director.py`) is the central orchestrator and autonomous brain of the Raphael system. It is responsible for continuously polling the task queue, reasoning over available capabilities, and spawning/monitoring habitats.

## Core Modules

1. **`TaskManager`**: Manages an asynchronous queue categorized by priority. Handles task states (`pending`, `running`, `completed`, `failed`).
2. **`GraphReasoner`**: Interfaces with `graph/graph_api.py` (Neo4j) to understand available blueprints, machines, and GPUs.
3. **`HabitatSelector`**: Uses weighted logic (capabilities + resource constraints) to rank and select the optimal blueprint for a task.
4. **`HardwareScheduler`**: Determines the physical/virtual node where the habitat will execute, ensuring GPU availability if required.
5. **`ClusterRouter`**: Manages burst capacity for hybrid-cloud deployments.
6. **`HelmController`**: Executes isolated agent deployments using Kubernetes Helm.
7. **`HabitatMonitor` & `HabitatMetrics`**: Observes running pods, tracks TTL, and syncs performance data to the Graph.
8. **`HabitatEvolver`**: Mutates parameters (like agent counts) and promotes successful configurations to new blueprints.
9. **`PatternDiscovery`**: Mines logs and autonomously authors brand-new Helm charts based on discovered best practices.
10. **`ExperimentScheduler`**: Injects synthetic training workloads into the swarm whenever the active task queue falls below a defined idle threshold.
