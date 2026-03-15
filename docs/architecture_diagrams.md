# Architecture & Dataflow Diagrams

This document collects **architecture** and **workflow/dataflow** diagrams for each major piece of the Raphael project. All diagrams use [Mermaid](https://mermaid.js.org/) and render in GitHub, VS Code, and most Markdown viewers.

---

## Index

| Diagram | Description |
|--------|-------------|
| [System overview](#1-system-overview) | High-level Swarm Director + Habitats + Graph |
| [Director workflow](#2-director-workflow) | Task lifecycle: observe → reason → select → deploy → monitor |
| [Event bus dataflow](#3-event-bus-dataflow) | Event types and which layers publish/subscribe |
| [Cognitive pipeline (L3→L7)](#4-cognitive-pipeline-l3l7) | Task understanding → Spine → Cognition → Swarm → Agents |
| [Agent dispatch workflow](#5-agent-dispatch-workflow) | PLAN_FINALIZED → dispatch → execute → SUBTASK_COMPLETED |
| [Knowledge graph dataflow](#6-knowledge-graph-dataflow) | Who reads/writes Neo4j and which nodes/edges |
| [Memory system dataflow](#7-memory-system-dataflow) | Working memory, episodic, semantic, operational KG |
| [Habitats lifecycle](#8-habitats-lifecycle) | Deploy → run → metrics → evolver → destroy |
| [Experiments workflow](#9-experiments-workflow) | Idle-time injection → task → evaluate → metrics |
| [Observability dataflow](#10-observability-dataflow) | HabitatMetrics → Neo4j; Prometheus scrape targets |
| [Full 13-layer architecture](#11-full-13-layer-architecture) | Complete system (reference to existing diagram) |
| [AI Router workflow](#12-ai-router-workflow) | Request → perception → node selection → LLM dispatch |
| [Task flow engine](#task-flow-engine-circulatory-system) | User task → Planner → Router → Worker → Evaluator → Memory |

---

## Task flow engine (circulatory system)

The task flow is the circulatory system: every user task flows through the same pipeline. **No agent talks to the user directly except the Planner** — this keeps the swarm organized.

```mermaid
flowchart TB
    User[User Task]
    Planner[Planner Agent]
    Router[Router Agent]
    Worker[Worker Agent]
    Evaluator[Evaluation Agent]
    Memory[Memory Update]

    User -->|"1. task"| Planner
    Planner -->|"2. subtasks + capabilities"| Router
    Router -->|"3. assigned task"| Worker
    Worker -->|"4. result"| Evaluator
    Evaluator -->|"5. score + store"| Memory
    Memory -.->|"feedback"| Planner
```

**Rule:** Only the Planner has a user-facing interface. All other agents receive and return structured payloads via the event bus / orchestrator.

---

## 1. System overview

High-level architecture: Director as central orchestrator, Graph as long-term memory, Habitats as execution environments.

```mermaid
flowchart LR
    subgraph Input
        T[Task Queue]
    end

    subgraph Director["Swarm Director"]
        TM[TaskManager]
        GR[GraphReasoner]
        HS[HabitatSelector]
        HC[HelmController]
        HM[HabitatMonitor]
        TM --> GR --> HS --> HC
        HC --> HM
    end

    subgraph Store["Knowledge Graph"]
        Neo4j[(Neo4j)]
    end

    subgraph Runtime["Kubernetes"]
        H1[Habitat 1]
        H2[Habitat 2]
    end

    T --> TM
    GR <--> Neo4j
    HC --> Runtime
    HM --> Neo4j
    HM -.-> Runtime
```

---

## 2. Director workflow

Dataflow through the Swarm Director main loop. Each task moves through these stages.

```mermaid
flowchart TB
    subgraph Loop["Director loop (director/director.py)"]
        A[1. Observe: next_task from TaskManager]
        B[2. Reason: GraphReasoner.find_blueprints_for_capabilities]
        C[3. Select: HabitatSelector.select]
        D[4. Deploy: HelmController.install]
        E[5. Monitor: HabitatMonitor.register + transition RUNNING]
        F[6. Persist: store_node Task + record_task_solution]
        A --> B --> C --> D --> E --> F
    end

    subgraph Data["Data flow"]
        T[(TaskManager queue)]
        G[(Neo4j Graph)]
        K8s[Helm → K8s]
        T --> A
        B --> G
        G --> B
        C --> D
        D --> K8s
        E --> G
        F --> G
    end
```

---

## 3. Event bus dataflow

Which layers publish and subscribe to which event types. Arrows: **publish → subscribe**.

```mermaid
flowchart LR
    subgraph L2["L2 Perception"]
        P2[Observation]
    end

    subgraph L3["L3 Understanding"]
        U3[UnderstandingRouter]
    end

    subgraph L4["L4 Spine"]
        S4[SpineRouter]
    end

    subgraph L5["L5 Cognitive"]
        C5[CognitiveRouter]
    end

    subgraph L6["L6 Swarm"]
        R6[SwarmRouter]
    end

    subgraph L7["L7 Agents"]
        A7[AgentRouter]
    end

    P2 -->|OBSERVATION| U3
    U3 -->|TASK_SPAWNED| S4
    S4 -->|EXECUTION_APPROVED| C5
    C5 -->|PLAN_FINALIZED| R6
    R6 -->|AGENT_DISPATCH_REQUESTED| A7
    A7 -->|SUBTASK_COMPLETED| R6
    A7 -.->|CRASH_REPORT| Bus
    C5 -.->|CRASH_REPORT| Bus
    S4 -.->|CRASH_REPORT| Bus
```

---

## 4. Cognitive pipeline (L3→L7)

End-to-end workflow from observation to agent execution. Data flows top-to-bottom; event bus carries payloads between layers.

```mermaid
flowchart TB
    subgraph L2["Layer 2: Perception"]
        N[Normalize]
        O[OBSERVATION]
        N --> O
    end

    subgraph L3["Layer 3: Task Understanding"]
        Parse[TaskParser]
        Decomp[DecompositionEngine]
        GM[GoalManager]
        TS[TASK_SPAWNED]
        Parse --> Decomp --> GM --> TS
    end

    subgraph L4["Layer 4: System Spine"]
        Safe[SafetyGate]
        Perm[PermissionsValidator]
        Res[ResourceManager]
        EA[EXECUTION_APPROVED]
        Safe --> Perm --> Res --> EA
    end

    subgraph L5["Layer 5: Core Cognitive"]
        Ctx[ContextBuilder]
        Plan[ExecutionPlanner]
        Val[ReasoningValidator]
        Agg[ResultAggregator]
        PF[PLAN_FINALIZED]
        Ctx --> Plan --> Val --> Agg --> PF
    end

    subgraph L6["Layer 6: Swarm Manager"]
        Orch[SwarmOrchestrator]
        MR[ModelRouter]
        ADR[AGENT_DISPATCH_REQUESTED]
        Orch --> MR --> ADR
    end

    subgraph L7["Layer 7: Agent Swarm"]
        AR[AgentRouter]
        Agents[Planner / Coder / Evaluator / ...]
        SC[SUBTASK_COMPLETED]
        AR --> Agents --> SC
    end

    O --> Parse
    TS --> Safe
    EA --> Ctx
    PF --> Orch
    ADR --> AR
    SC --> Orch
```

---

## 5. Agent dispatch workflow

How a finalized plan becomes agent executions and how completions feed back.

```mermaid
sequenceDiagram
    participant Bus as Event Bus
    participant R6 as SwarmRouter (L6)
    participant Orch as SwarmOrchestrator
    participant R7 as AgentRouter (L7)
    participant Agent as Agent (e.g. CodingAgent)

    Bus->>R6: PLAN_FINALIZED
    R6->>Orch: ingest_plan(payload)
    R6->>Orch: process_queue(plan_id)
    Orch-->>R6: dispatch_list
    loop For each assignment
        R6->>Bus: AGENT_DISPATCH_REQUESTED
        Bus->>R7: AGENT_DISPATCH_REQUESTED
        R7->>R7: agent_registry[assigned_agent]
        R7->>Agent: execute(payload)
        Agent-->>R7: { success, logs, output }
        R7->>Bus: SUBTASK_COMPLETED
    end
    Bus->>R6: SUBTASK_COMPLETED
    R6->>Orch: handle_completion(plan_id, sub_task_id)
    R6->>Orch: process_queue(plan_id)
```

---

## 6. Knowledge graph dataflow

Who reads from and writes to the Neo4j graph. Schema is in `docs/graph_schema.md` and `graph/graph_api.py` (ALLOWED_LABELS, ALLOWED_RELATIONSHIPS).

```mermaid
flowchart TB
    subgraph Writers["Writers"]
        Director[SwarmDirector: store_node Task, record_task_solution]
        Metrics[HabitatMetrics: PERFORMANCE, Metric nodes]
        Evolver[HabitatEvolver: promote blueprints]
        Pattern[PatternDiscovery: new charts]
    end

    subgraph Readers["Readers"]
        GR[GraphReasoner: find_blueprints_for_capabilities]
        Selector[HabitatSelector: rank candidates]
    end

    subgraph Neo4j["Neo4j Graph"]
        Task[Task]
        Blueprint[HabitatBlueprint]
        Cap[Capability]
        AgentType[AgentType]
        Machine[Machine]
        GPU[GPU]
        Metric[Metric]
        Task --> Blueprint
        Blueprint --> Cap
        Blueprint --> AgentType
        Blueprint --> Machine
        Blueprint --> Metric
    end

    Director --> Task
    Metrics --> Metric
    Evolver --> Blueprint
    GR --> Blueprint
    GR --> Cap
    GR --> AgentType
    GR --> Machine
```

---

## 7. Memory system dataflow

How different memory stores are used by layers. Aligns with `docs/diagrams/polyglot_memory_system-*.mmd`.

**Memory verification and target:** The diagram in `docs/diagrams/polyglot_memory_system-2026-02-22-205539.mmd` has been aligned with current implementation (Director, Consolidation, AI Router → stores). The PNG (`polyglot_memory_system-2026-02-22-205537.png`) is the **target** architecture; see **`docs/diagrams/MEMORY_SYSTEM_VERIFICATION.md`** for current vs. future (Polyglot L0, Temporal Graph, layer–store wiring) and recommendations.

```mermaid
flowchart TB
    subgraph Layers["Layers"]
        L3[L3 Task Understanding]
        L4[L4 Spine]
        L5[L5 Cognitive]
        L6[L6 Swarm]
        L7[L7 Agents]
        L8[L8 Execution]
        L9[L9 Evaluation]
        L10[L10 Learning]
        L11[L11 Research]
    end

    subgraph Working["Working Memory"]
        Redis[(Redis)]
    end

    subgraph Episodic["Episodic Memory"]
        PG[(PostgreSQL / TimescaleDB)]
    end

    subgraph Operational["Operational KG"]
        Neo4jOp[(Neo4j: Agent & Task graph)]
    end

    subgraph Semantic["Vector / Semantic"]
        Vector[(Milvus / LanceDB / Qdrant)]
    end

    L3 --> Redis
    L3 --> Vector
    L4 --> Neo4jOp
    L5 --> Redis
    L5 --> Vector
    L6 --> Neo4jOp
    L7 --> Neo4jOp
    L8 --> Redis
    L8 --> PG
    L9 --> PG
    L10 --> Neo4jOp
    L11 --> Vector
    L11 --> Neo4jOp
```

---

## 8. Habitats lifecycle

From Director decision to deploy through monitoring and teardown. Includes evolution feedback.

```mermaid
stateDiagram-v2
    [*] --> Pending: task submitted
    Pending --> Deploying: Director selects blueprint
    Deploying --> Running: Helm install OK
    Deploying --> Failed: Helm install fail
    Running --> Completing: TTL or manual destroy
    Completing --> Syncing: HabitatMetrics.record_completion
    Syncing --> [*]: sync_to_graph (PERFORMANCE)
    Failed --> [*]: task FAILED

    note right of Running: HabitatMonitor tracks TTL\nHabitatEvolver may mutate params
    note right of Syncing: (Blueprint)-[PERFORMANCE]->(Metric)\nHabitatSelector.update_performance
```

---

## 9. Experiments workflow

How experiments are injected when the queue is idle and how results feed metrics.

```mermaid
flowchart LR
    subgraph Director["Director"]
        Idle[Queue idle?]
        ExpSched[ExperimentScheduler]
        TM[TaskManager]
        Idle --> ExpSched
        ExpSched -->|submit_task| TM
    end

    subgraph Experiment["BaseExperiment"]
        Gen[generate_workload_payload]
        Eval[evaluate_result]
        Gen --> TM
    end

    TM --> Loop[Director loop]
    Loop --> Deploy[Deploy habitat]
    Deploy --> Run[Run experiment]
    Run --> Result[Result]
    Result --> Eval
    Eval --> Metrics[HabitatMetrics]
    Metrics --> Graph[(Neo4j)]
```

---

## 10. Observability dataflow

Where metrics are produced and where they are consumed. Prometheus/Grafana config lives in `observability/`.

```mermaid
flowchart TB
    subgraph Sources["Metric sources"]
        HM[HabitatMetrics: completion_time, success_rate, agent_efficiency]
        Director[Director: pending_tasks, running_tasks, active_habitats]
        Agents[Agent containers: /health, port 8080]
    end

    subgraph Storage["Storage"]
        Neo4j[(Neo4j: Metric nodes, PERFORMANCE edges)]
    end

    subgraph Scrape["Prometheus scrape (observability/prometheus.yml)"]
        P1[swarm_director: host.docker.internal:8000]
        P2[habitats: localhost:8080 placeholder]
    end

    HM --> Neo4j
    Director --> P1
    Agents --> P2
```

---

## 11. Full 13-layer architecture

The complete system view with all 13 layers and supporting systems (Memory, World Model, Registry, Event Bus) is in:

- **`docs/diagrams/complete_system_architecture.mmd`** — Mermaid flowchart with `layout: elk`; open in Mermaid Live Editor or a tool that supports `.mmd` for full layout.

Below is a simplified version that fits in-doc rendering.

```mermaid
flowchart TB
    subgraph L1["1. Environment"]
        User[User / External Systems]
    end

    subgraph L2["2. Perception"]
        Norm[Normalizer]
        Vision[Vision / Speech / Text]
    end

    subgraph L3["3. Task Understanding"]
        Intent[Intent / Parser / Decomposer]
    end

    subgraph L4["4. System Spine"]
        Res[Resource Manager]
        Gov[Safety & Governance]
    end

    subgraph L5["5. Core Cognitive"]
        Plan[Planner]
        Agg[Aggregator]
    end

    subgraph L6["6. Swarm Manager"]
        Orch[Orchestrator]
        Router[Model Router]
    end

    subgraph L7["7. Agent Swarm"]
        Agents[Agents]
    end

    subgraph L8["8. Execution"]
        Exec[Tool Exec / Code Run]
    end

    subgraph L9["9. Evaluation"]
        Critic[Critic / QA / Sandbox]
    end

    subgraph L10["10. Learning"]
        Reward[Reward Signals]
        Skill[Skill Learning]
    end

    subgraph L11["11. Research"]
        Curiosity[Curiosity]
        Hypothesis[Hypothesis / Experiments]
    end

    subgraph L12["12. Strategic"]
        Strategy[Strategy Engine]
        Self[Self-Model]
    end

    subgraph L13["13. Civilization"]
        GovC[Governance Council]
        Innov[Innovation]
    end

    User --> Norm --> Vision --> Intent
    Intent --> Gov --> Plan --> Orch --> Agents --> Exec --> Critic
    Critic --> Reward --> Skill
    Reward --> Curiosity --> Hypothesis
    Strategy --> Intent
    GovC --> Innov
```

---

## Layer-specific diagrams (existing)

Detailed per-layer Mermaid source files in `docs/diagrams/`:

| Layer | File |
|-------|------|
| 1 Environment | `1-environment_layer-*.mmd` |
| 2 Perception | `2-perception_layer-*.mmd` |
| 3 Task Understanding | `3-task_understanding_layer-*.mmd` |
| 4 System Spine | `4-system_spine_layer-*.mmd` |
| 5 Core Cognitive | `5-core_cognitive_layer-*.mmd` |
| 6 Swarm Manager | `6-swarm_manager_layer-*.mmd` |
| 7 Agent Swarm | `7-agent_swarm-*.mmd` |
| 8 Execution & Integration | `8-execution-integration_layer-*.mmd` |
| 9 Evaluation | `9-evaluation_layer-*.mmd` |
| 10 Learning | `10-learning_layer-*.mmd` |
| 11 Autonomous Research | `11-autonomous_research_layer-*.mmd` |
| 12 Strategic Intelligence | `12-strategic_intelligence-*.mmd` |
| 13 Civilization Loop | `13-civilization_layer-*.mmd` |
| Memory (polyglot) | `polyglot_memory_system-*.mmd` |

These can be opened in [Mermaid Live](https://mermaid.live/) or rendered by tools that support Mermaid (e.g. `mmdc` from `@mermaid-js/mermaid-cli`).

**Diagram verification:** For a comparison of these diagrams with this document and the codebase (inconsistencies, missing elements, placeholder files), see **[docs/ARCHITECTURE_DIAGRAM_VERIFICATION.md](ARCHITECTURE_DIAGRAM_VERIFICATION.md)**.

---

## 12. AI Router workflow

The **AI Router** (`ai_router/`) is a FastAPI service that manages node registration, perception, working memory, and routing of requests to LLM-capable nodes. It can run alongside or in place of the core event-bus pipeline for node-centric workflows.

```mermaid
flowchart TB
    subgraph Client["Clients"]
        API[HTTP / API]
        SSE[Transparency SSE]
    end

    subgraph Router["AI Router (ai_router/main.py)"]
        NodeMgr[NodeManager: registration, heartbeat]
        Config[config.json: nodes, roles, policy]
        Perception[Perception: normalize, understand]
        WM[Working Memory]
        KG[knowledge_graph]
        Episodic[episodic_memory]
        Resource[resource_manager]
        Placement[placement / routing]
        Eval[evaluation_service]
    end

    subgraph Nodes["LLM nodes"]
        N1[Node 1 e.g. Ollama]
        N2[Node 2 e.g. LM Studio]
    end

    API --> NodeMgr
    API --> Perception
    Config --> NodeMgr
    Config --> Placement
    Perception --> WM
    Perception --> KG
    WM --> Placement
    Resource --> Placement
    Placement --> N1
    Placement --> N2
    N1 & N2 --> Eval
    Eval --> Episodic
    NodeMgr --> SSE
```

