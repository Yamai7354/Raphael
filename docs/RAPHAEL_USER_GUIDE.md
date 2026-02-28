# Raphael OS: User Guide

Raphael is a 13-layer, event-driven agentic operating system designed to manage complex AI ecosystems. It coordinates perception, task understanding, cognitive planning, and multi-agent execution through a centralized asynchronous event bus.

## 🏛 Architecture Overview

Raphael is structured into 13 foundational layers, each serving a specific purpose in the "cognitive pipeline":

1.  **Environment Layer**: Bridges the system with the external world (Filesystem, Network, User).
2.  **Perception Layer**: Normalizes inputs (Text, Vision, Speech).
3.  **Goals & Task Understanding**: Detects intent and decomposes high-level goals into sub-tasks.
4.  **System Spine**: The regulatory backbone (Safety, Resource Management, Health, Identity).
5.  **Core Cognitive System**: The "thinking" layer (Planning, Context Building, Validation).
6.  **Swarm Manager**: Orchestrates task assignment and model routing.
7.  **Agent Swarm**: Specialized agents (Coding, Research, Reasoning) that execute work.
8.  **Execution & Integration**: Low-level tool execution and system control.
9.  **Evaluation & Testing**: Critics and QA agents that validate results.
10. **Learning Engine**: Updates policies and learns new skills based on feedback.
11. **Autonomous Research**: Generates hypotheses and designs experiments.
12. **Strategic Intelligence**: Long-horizon planning and self-modeling.
13. **Civilization Loop**: High-level governance and infrastructure evolution.

## 🛰 Core Concepts

### The System Event Bus
All communication in Raphael happens via the `SystemEventBus`. Layers do not call each other directly; they publish and subscribe to `SystemEvent` objects.

### System Events
An event consists of:
- **EventType**: (e.g., `OBSERVATION`, `TASK_SPAWNED`, `EXECUTION_APPROVED`).
- **Priority**: 1 (Lowest) to 10 (Highest).
- **Payload**: The JSON body containing data.
- **SourceLayer**: Information about the emitting module.

## 🚀 Getting Started

### System Requirements
- Python 3.10+
- Dependencies: `pydantic`, `asyncio`, `pytest` (for testing)

### Initializing the System (Developer Example)
To start a minimal Raphael instance, you need to initialize the bus and the desired layer routers:

```python
import asyncio
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.perception.router import PerceptionRouter
from src.raphael.understanding.router import UnderstandingRouter
from src.raphael.spine.router import SpineRouter

async def main():
    bus = SystemEventBus()
    
    # Initialize Core Layers
    perception = PerceptionRouter(bus)
    understanding = UnderstandingRouter(bus)
    spine = SpineRouter(bus)
    
    # Start the Bus
    await bus.start()
    
    # System is now listening for OBSERVATION events...
    pass

asyncio.run(main())
```

## 🛠 Usage & Interfaces

Currently, Raphael is in an "Assembly Required" state. You can interact with it via:
1.  **Integration Tests**: Run `pytest tests/integration` to see full-flow examples.
2.  **CLI (Planned)**: A high-level command-line tool.
3.  **API (Planned)**: A FastAPI-based interface for remote agents.
4.  **Dashboard (Planned)**: A visual UI for monitoring the Cognitive Spine.

## 🛡 Database Stewardship & Maintenance

Raphael includes a suite of specialized agents for maintaining the health and integrity of its data layers:

### Database Stewardship
Raphael includes autonomous stewards for Neo4j, Qdrant, and Relational databases. They perform periodic health checks and self-healing.

- **Stewardship Ritual**: Runs every 5 minutes (300s) to validate graph integrity, vector collection health, and database consistency.

### Portfolio & Documentation
The system integrates with the AI Portfolio Suite to maintain up-to-date project records automatically.

- **Portfolio Agent**: An L7 swarm agent that manages documentation, diagrams, and reports.
- **Reporting Ritual**: Runs every hour (3600s) to update system architecture diagrams and generate daily project reports.
- **Automated Tracking**: Every agent action is logged as a session entry in the `portfolio/data/sessions.json` for full auditability.
- **Relational Stewardship (`L7.db_steward`)**: Manages SQLite integrity and indexing.
