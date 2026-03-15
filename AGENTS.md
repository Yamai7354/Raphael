# AGENTS.md — Guidance for AI Coding Assistants (Codex, Cursor, etc.)

This file helps AI assistants work effectively in the Raphael codebase. Follow these conventions and patterns when editing or adding code.

## Project identity

- **Raphael**: Self-improving multi-agent AI system with swarm intelligence, a shared knowledge graph (Neo4j), and event-driven coordination.
- **Stack**: Python 3.11+, uv for deps, Neo4j, Redis, Helm/Kubernetes for habitats. Dashboard: Next.js in `swarm-dashboard/`.
- **Docs**: `docs/architecture.md`, `docs/roadmap.md`, `docs/swarm_director.md`.

## Directory layout

| Path | Purpose |
|------|--------|
| `director/` | Swarm Director: TaskManager, GraphReasoner, HabitatSelector, HelmController, HabitatMetrics. |
| `graph/` | Neo4j schema, seed data, and `graph_api.py` (Neo4jGraphStore). |
| `agents/` | Agent implementations. Use `agents/base_agent.py`; `agents/base.py` re-exports for compatibility. |
| `agents/api.py` | **Formal agent contract**: `AgentContext`, `get_event_bus()`. Use these instead of instantiating `SystemEventBus()` in agents. |
| `event_bus/` | `SystemEventBus`, `EventType` and `SystemEvent` in `data/schemas.py`. |
| `habitats/` | Helm charts (coding-habitat, research-habitat, gpu-inference-habitat). |
| `core/` | Cognitive, memory, execution, research, civilization, strategy, learning, evaluation layers. |
| `ai_router/` | Node routing, perception, tool registry, LLM dispatch. |
| `observability/` | Prometheus/Grafana config. |
| `scripts/` | KG seed, import, rebuild, migration. |
| `docker/` | Dockerfiles for planner-agent and coding-agent; build from repo root. |

## Conventions

### Python

- **Runtime**: Python 3.11+.
- **Package manager**: Prefer `uv` (e.g. `uv run pytest`, `uv sync`). Lockfile: `uv.lock`.
- **Style**: Ruff (see `pyproject.toml`). Line length 100; fix E, F, I, N, W, UP.
- **Types**: Pydantic for payloads/schemas. Type hints encouraged; `disallow_untyped_defs = false` in mypy.

### Agents

- **Base**: New agents subclass `BaseAgent` from `agents/base_agent.py` and implement `async def execute(self, payload) -> dict` with `{success, logs, output}`.
- **Event bus**: Do not construct `SystemEventBus()` inside agents. Use `get_event_bus(self._event_bus)` from `agents/api.py`, and have the router (or caller) inject `event_bus` when building the agent.
- **Publishing**: Use `data.schemas.SystemEvent`, `EventType`, and `LayerContext` when publishing; add new event types to `EventType` in `data/schemas.py` if needed.
- **Graph**: When an agent needs Neo4j, accept an optional `graph_client` (or `AgentContext`) and use `context.execute_cypher()`; avoid creating a new Neo4j driver inside the agent.

### Event bus and layers

- Events flow between layers (1–13). See `data/schemas.py` for `EventType` and `LayerContext`.
- Subscribers: `bus.subscribe(EventType.X, callback)`. Callbacks are async and receive `SystemEvent`.
- Publish: `await bus.publish(event)`.

### Neo4j / graph

- Use `graph/graph_api.py` (`Neo4jGraphStore`). Labels and relationship types are restricted; see `ALLOWED_LABELS` and `ALLOWED_RELATIONSHIPS`.
- Director uses `GraphReasoner` in `director/graph_reasoner.py` for capability/blueprint queries.

### Testing

- **Runner**: `uv run pytest` from repo root.
- **Import mode**: `import-mode=importlib` in `pyproject.toml` so the project `agents` package resolves correctly.
- **Paths**: `pythonpath = ["."]`; tests live in `tests/`. Use `tests/conftest.py` fixtures (e.g. `mock_event_bus`).

### Dashboard (swarm-dashboard)

- Next.js app; run with `npm run dev` from `swarm-dashboard/`.
- API routes under `app/api/`; shared components in `components/`.

## Commands

- **Install deps**: `uv sync`
- **Tests**: `uv run pytest tests/ -v`
- **Dev bootstrap**: `make run-dev` (see `Makefile`)
- **Build agent images**: `make build-agents` or `docker build -f docker/planner-agent.Dockerfile -t <tag> .` from repo root

## Placeholders and known stubs

- `core/interfaces/adapters/task_manager_adapter.py` and `browser_adapter.py`: return placeholder data; replace when wiring real integrations.
- `core/interfaces/adapters/file_system_adapter.py`, `email_adapter.py`, `calendar_adapter.py`: same pattern (return placeholder data); replace when wiring real integrations.
- `ai_router/agent.py`: minimal placeholder module.
- `ai_router/tool_router.py`: tool routing module placeholder.
- Several agents have `# TODO: Subscribe to …` (e.g. performance_analyzer, exploration_engine, system_monitor_agent); event subscriptions are not yet wired.
- `observability/prometheus.yml`: `localhost:8080` is a placeholder scrape target for agent metrics.

When adding features near these areas, prefer implementing real behavior or documenting the stub rather than expanding placeholder logic.

## Do not

- Add a top-level `agents.py` module (would shadow the `agents/` package).
- Instantiate `SystemEventBus()` inside agent code; use `get_event_bus(injected_bus_or_context)`.
- Introduce new Neo4j labels or relationship types without adding them to `ALLOWED_LABELS` / `ALLOWED_RELATIONSHIPS` in `graph/graph_api.py`.
- Rely on `--import-mode=prepend` for pytest; keep `import-mode=importlib` so `agents` resolves to the project package.
