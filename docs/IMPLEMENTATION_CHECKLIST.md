# Raphael Swarm — Implementation Checklist

One-page checklist for the stabilized core brain and automation system.

## Core System

- [x] Create `config/agents.yaml` registry
- [x] Add capability nodes to Neo4j (`ingest_agents_from_registry` in `populate_swarm_graph.py`)
- [x] Implement task router to use `data/capabilities.json` or registry (ModelRouter fallback in `swarm/model_router.py`)

## Task Pipeline

- [ ] Planner agent decomposition
- [ ] Router capability matching (from `agents.yaml` / `capabilities.json`)
- [ ] Worker execution system
- [ ] Evaluator scoring

## Memory System

- [x] Knowledge scoring schema (see `docs/knowledge_quality_schema.md`)
- [ ] Embedding store integration with quality thresholds
- [ ] TTL cleanup for low-quality nodes

## Automation

- [x] Workflow definitions (see `docs/workflows.md`)
- [ ] Coding workflow (orchestration)
- [ ] Research workflow (orchestration)
- [ ] System optimization workflow (orchestration)

## Observability

- [x] Metrics endpoint (`observability/metrics_endpoint.py` + FastAPI `/metrics`)
- [x] Prometheus scrape config (`observability/prometheus.yml`)
- [x] Grafana dashboards dir (`observability/grafana/`)

---

**Phase 1 (Done):** Agent registry (`config/agents.yaml`), capability map (`data/capabilities.json`), Neo4j sync (`ingest_agents_from_registry`), capability map script (`scripts/build_capabilities_map.py`).

**Phase 2:** Task flow documented in `docs/architecture_diagrams.md` (Task flow engine). Rule: only Planner talks to user.

**Phase 3:** Knowledge quality rules in `docs/knowledge_quality_schema.md`.

**Phase 4:** Workflow steps in `docs/workflows.md`; orchestration to be wired to event bus.

**Phase 5:** Prometheus metrics (task success rate, agent response time, memory growth, model usage) via `observability/metrics_endpoint.py`.
