# AI Router (Current Module Overview)

`packages/ai_router` is the runtime kernel for this repository. It exposes the FastAPI control plane, task orchestration loop, policy gates, routing logic, and telemetry/transparency endpoints.

## Entry Point

- App module: `packages/ai_router/main.py`
- FastAPI lifespan initializes:
  - Event bus (`RedisEventBus`)
  - Perception/evaluation/resource services
  - Memory layers (episodic, knowledge, working memory)
  - Reflection/experiment/interaction services
  - Node health monitor loop

## Key Runtime Modules

- `main.py`: API routes and service lifecycle.
- `router.py`: Node selection, capability/load-aware routing.
- `supervisor.py`: Task planning/execution orchestration.
- `policy.py`: Risk scoring, approval threshold, ethical constraints.
- `orchestration.py`: Task/step models and task registry.
- `transparency_stream.py`: SSE event stream for dashboard visibility.

## Primary Endpoints

- `GET /health`
- `POST /v1/chat/completions`
- `POST /task/create`
- `POST /task/{task_id}/execute`
- `GET /task/{task_id}/status`
- `GET /task/{task_id}/audit`
- `GET /admin/transparency/summary`
- `GET /admin/stream/decisions`
- `POST /interaction/process_text`
- `POST /interaction/process_audio`
- `GET /interaction/settings`

## Dashboard Integration

The React dashboard in `packages/dashboard` consumes:

- `GET /admin/transparency/summary`
- `GET /admin/stream/decisions`
- `GET /task/{task_id}/audit`

Default frontend origin allowed by CORS: `http://localhost:5173`.

## Local Run Notes

- API default: `http://localhost:9000`
- Redis expected at `localhost:6379` unless overridden.
- Root verification runner: `python3 run_verifications.py`
