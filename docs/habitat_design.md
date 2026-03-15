# Habitat Design

A **Habitat** is the ephemeral, isolated environment deployed by Raphael in response to a Task. It provides the specific tools, networking, and agent combinations required to solve a problem.

## Structure

Habitats are packaged as Helm charts stored in `habitats/`. Each habitat contains:
- `Chart.yaml`: Helm metadata and versioning.
- `values.yaml`: Configurable defaults (e.g., agent counts, resource requests).
- `templates/`: Kubernetes manifests (Deployments, Services, ConfigMaps).

## Existing Habitats

1.  **`coding-habitat`**: Spawns coder agents with syntax linters and safe execution sandboxes.
2.  **`research-habitat`**: Spawns search and planner agents with robust internet and VectorDB access.
3.  **`gpu-inference-habitat`**: Deployed primarily on hardware with discrete GPUs (`desktop` with R9 390) for heavy memory workloads.

## Adaptive Evolution

The `HabitatEvolver` module monitors metrics. If a habitat configuration performs exceptionally well, it creates a new optimized `HabitatBlueprint` in the Graph, allowing the swarm to adapt to workloads over time.
