# Knowledge Graph Schema

The Neo4j database acts as the central intelligence of Raphael. It records the current hardware state, agent capabilities, habitat definitions, and historical metrics to make deeply informed orchestration decisions.

## Node Types

- **`Machine`**: Physical or virtual machine (e.g., macbook, desktop).
- **`GPU`**: Hardware accelerator (e.g., Apple M4, AMD R9 390).
- **`Capability`**: Abstract system skills (e.g., `code_generation`, `gpu_inference`).
- **`AgentType`**: Types of agents (e.g., `coding_agent`, `planner`).
- **`HabitatBlueprint`**: A template mapping to a Helm chart.
- **`Task`**: A unit of work submitted to the Director.
- **`Metric`**: Historical performance tracking.

## Core Relationships

- `(Machine)-[:HAS_GPU]->(GPU)`
- `(Capability)-[:REQUIRES_GPU]->(GPU)`
- `(AgentType)-[:HAS_CAPABILITY]->(Capability)`
- `(HabitatBlueprint)-[:CONTAINS_AGENT]->(AgentType)`
- `(HabitatBlueprint)-[:HAS_CAPABILITY]->(Capability)`
- `(HabitatBlueprint)-[:RUNS_ON]->(Machine)`
- `(Task)-[:SOLVED_BY]->(HabitatBlueprint)`
- `(HabitatBlueprint)-[:PERFORMANCE]->(Metric)`

The `GraphReasoner` in the Swarm Director traverses these links to match a given Task to the optimal Blueprint and Machine.
