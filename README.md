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

```
raphael/
├── agents/          # Agent implementations (explorer, factory, caretaker, validator)
├── ai_router/       # LLM routing, model selection, and request orchestration
├── core/            # Core brain: reasoning, memory, knowledge graph, world model
├── event_bus/       # Redis-backed event bus for inter-agent communication
├── scripts/         # Utility scripts
├── skills/          # Agent skill definitions
├── spine/           # System spine: config, health, identity, permissions, telemetry
├── swarm/           # Swarm coordination and intelligence layer
├── swarm-dashboard/ # Next.js dashboard for monitoring the swarm
├── tests/           # Test suite
├── tool_router/     # Tool routing and execution
└── docs/            # Documentation and architecture diagrams
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

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies (dev mode with all optional groups)
uv pip install -e ".[dev]"

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Dashboard Setup

```bash
cd swarm-dashboard
npm install
npm run dev
```

## Configuration

All secrets and connection strings are configured via environment variables. Copy `.env.example` to `.env` and fill in your values:

| Variable             | Description                         |
| -------------------- | ----------------------------------- |
| `NEO4J_URI`          | Neo4j Bolt connection URI           |
| `NEO4J_PASSWORD`     | Neo4j password                      |
| `OLLAMA_BASE_URL`    | Ollama API endpoint                 |
| `OPENROUTER_API_KEY` | OpenRouter API key (for cloud LLMs) |
| `REDIS_URL`          | Redis connection URL                |

## Testing

```bash
pytest
```

## License

MIT
