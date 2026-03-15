# Swarm Roadmap

The overarching goal is a fully autonomous, self-improving superintelligence network.

## Current State (Phase 11)

- Knowledge & Blueprint Layer (Neo4j + Helm integration) Complete.
- Core Director Components (Swarm Task Management & Scheduling) Complete.
- Evolution & Scale (Evolution, Metrics, Auto-generation) Complete.
- Repository Restructure (Unified Control Center) Complete.

## Next Steps

### 1. Robust Agent Interfaces ✅ (in progress)
- **Done:** Formalized APIs in `agents/api.py`: `AgentContext` (event_bus + optional graph_client), `get_event_bus()` for injected or fallback bus. Planner, Evaluator, and Auditor accept optional `event_bus` and use it when provided by `AgentRouter`.
- **Done:** Fixed agent module imports in `agents/router.py` (planner, coder, evaluator, researcher from new paths). Added `agents/base.py` shim and `TASK_CREATED` / `TASK_EVALUATED` to `EventType` in `data/schemas.py`.
- **Done:** Docker images: `docker/planner-agent.Dockerfile`, `docker/coding-agent.Dockerfile`; minimal `agents/agent_server.py` for health on port 8080. Build from repo root (see `docker/README.md`).
- **Optional:** Wire agents to optional `graph_client` (Neo4j) for read/write when running in Director; add `services/neo4j` client wrapper if desired.

### 2. Observability Dashboards
- Construct default Grafana templates in `observability/grafana` mapping directly to the `HabitatMetrics` module outputs.

### 3. Experiment Implementation
- Flesh out `experiments/` to create sandboxed simulated workloads that the Director can autonomously schedule during idle time to improve its own blueprints.

### 4. Continuous Integration ✅
- **Done:** Created `Makefile` at the repository root to bootstrap the local dev environment (`make run-dev`) and build Docker images (`make build-agents`).
- **Done:** Created `.github/workflows/helm-lint.yml` to automatically validate Helm charts on PRs to `main`.
