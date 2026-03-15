# Raphael

A self-improving multi-agent AI system with swarm intelligence, memory, and exploration capabilities.

## Overview

Raphael is a modular AI platform built around the concept of cooperating AI agents that share a knowledge graph, coordinate via an event bus, and continuously learn from their environment. It combines:

- **Multi-Agent Architecture** — Specialized agents for exploration, research, optimization, and system monitoring
- **Knowledge Graph** — Neo4j-backed graph for persistent knowledge, agent relationships, and system topology
- **Swarm Intelligence** — Agents collaborate, delegate, and self-organize through a swarm coordination layer
- **AI Router** — Intelligent routing of tasks to the best-suited LLM model based on capability and performance
- **Event-Driven Communication** — Redis-backed event bus for inter-agent messaging
- **Self-Healing** — Automatic detection and recovery from failures, dead nodes, and resource bottlenecks

## Project Structure

```text
raphael/
├── director/       # Central nervous system (SwarmDirector, TaskManager, GraphReasoner)
├── graph/          # Knowledge Graph (schema, seed_data, reasoning queries)
├── habitats/       # Helm charts for environments (coding, research, gpu)
├── agents/         # Specialised agent implementations (planner, coder, etc.)
├── infrastructure/ # Kubernetes and physical setup (k3d, hardware specs)
├── services/       # Persistent organs (Neo4j, vector stores, etc.)
├── experiments/    # Sandbox tests for habitat evolution
├── observability/  # Prometheus/Grafana metrics
├── scripts/        # Utility deployment and bootstrap scripts
└── docs/           # Documentation and architecture diagrams
```

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Neo4j 5.x
- Redis 7.x
- Node.js 18+ (for dashboard)

### Installation

```bash
# Clone the repository
git clone https://github.com/Yamai7354/Raphael.git
cd Raphael

# Create and activate virtual environment (optional but recommended)
uv venv
source .venv/bin/activate

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your Neo4j, LLM, and NATS credentials

# Bootstrap the local environment (installs deps and starts the Director)
make run-dev
```

### Building Agents

To build the localized Docker images for the Planner and Coder agents (used by the Habitats):

```bash
make build-agents
```

### Dashboard Setup

```bash
cd swarm-dashboard
npm install
npm run dev
```

## Configuration

All secrets and connection strings are configured via environment variables. Copy `.env.example` to `.env` and fill in your values:

| Variable                      | Description                         |
| ----------------------------- | ----------------------------------- |
| `NEO4J_URI`                   | Neo4j Bolt connection URI           |
| `NEO4J_PASSWORD`              | Neo4j password                      |
| `NATS_URL`                    | NATS server connection URL          |
| `OPENROUTER_API_KEY`          | OpenRouter API key (for cloud LLMs) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry Collector URL         |

## Continuous Integration

- GitHub Actions (`.github/workflows/helm-lint.yml`) automatically validates all Helm charts in `habitats/` on pushes to `main`.
- For local testing, use `./scripts/test.sh`.

## License

MIT
