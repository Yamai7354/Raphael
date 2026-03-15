# Memory System Verification: Diagrams vs. Codebase

This document verifies whether the Raphael memory system is implemented as depicted in:

1. **`polyglot_memory_system-2026-02-22-205539.mmd`** — Layer–store connections (Working Memory, Episodic, Operational KG, Research KG, Vector Store).
2. **`polyglot_memory_system-2026-02-22-205537.png`** — Conceptual Polyglot Memory System (L0 Polyglot, Temporal Graph, Declarative, Procedural, Plan/Task Graph, Operational/Workflow, and L1 layer flows).

---

## 1. Verification against the .mmd diagram

The `.mmd` file shows **five memory stores** and **which layers (L3–L13) connect to them**.

### Store types: ✅ Implemented

| Diagram store | Implementation | Location |
|---------------|----------------|----------|
| **Working Memory (Redis)** | ✅ | `core/memory/knowledge_graph/working_memory.py` (Redis), `core/memory/working_memory/redis_buffer.py` (`RedisWorkingMemory`), `core/memory/working_memory/cache.py` (`RedisCache`). ai_router uses `ai_router/working_memory.py` (Redis). |
| **Episodic Memory (Timescale/PostgreSQL)** | ✅ | `core/memory/episodic_memory/postgres_store.py` (`PostgresEpisodicStore`), `episodic_memory.py` singleton. Also SQLite variant in `sqlite_store.py`. |
| **Operational KG (Neo4j, Agent & Task)** | ✅ | `core/memory/knowledge_graph/operational_kg.py` (“Separated from ResearchKG per Polyglot Architecture”). Director uses `graph/graph_api.py` (`Neo4jGraphStore`) for tasks/blueprints — same Neo4j, different schema/usage. |
| **Research KG (Neo4j/Arango/RDF)** | ✅ | `core/research/research_kg.py` (Neo4j, “Separated from the OperationalKG per the Polyglot Architecture”). No Arango/RDF implementation; diagram lists alternatives. |
| **Vector Store (Milvus/FAISS/Weaviate)** | ✅ | `core/memory/semantic_memory/vector_store.py` (LanceDB), `qdrant_store.py`, `milvus_store.py`. |

### Cross-store references in diagram

- **Neo4jOp → Neo4jRes, Milvus → Neo4jRes, RDFStore → Neo4jRes**: Not implemented as explicit “cross-store” pipelines. ResearchKG and OperationalKG are separate Neo4j databases (`operational` vs `research`). Vector stores and graph are not wired to push into Research KG in code; consolidation flows (see below) go Episodic → Procedural/Semantic.

### Layer–store connections: ⚠️ Partially implemented

The .mmd claims specific layer → store edges. Findings:

| Connection in diagram | In code |
|-----------------------|--------|
| **L3 → Redis, L3 → Milvus** | ❌ No direct imports. `core/understanding` (TaskParser, DecompositionEngine, GoalManager) does not use Working Memory or Vector Store. |
| **L4 → Neo4jOp** | ⚠️ Spine (`spine/`) does not import OperationalKG. Director and GraphReasoner use `graph/graph_api.py` (Neo4j) for tasks/blueprints; that is the “operational” graph in practice. |
| **L5 → Redis, L5 → Milvus** | ⚠️ `ContextBuilder` (L5) only *simulates* “Polyglot Memory” with mock tips; comment mentions LanceDB/Redis but no real calls. |
| **L6 → Neo4jOp** | ⚠️ Swarm router/orchestrator do not import OperationalKG. Director’s GraphReasoner uses `graph_api` for blueprints. |
| **L7 → Neo4jOp** | ⚠️ `agents/base_agent.py` has *commented-out* `operational_kg.record_task` and `episodic_memory.log_event`. Not active. |
| **L8 → Redis, L8 → Timescale** | ⚠️ Execution layer uses ToolRegistry; no direct Redis/Postgres episodic in `core/execution`. ai_router uses working_memory + episodic_memory. |
| **L9 → Timescale** | ⚠️ Evaluation (Critic, Sandbox) does not import episodic store. |
| **L10 → Neo4jRes, RDFStore** | ❌ `core/learning/router.py` uses PolicyManager only; no ResearchKG or RDF. |
| **L11 → Neo4jRes, RDFStore** | ⚠️ `ResearchKG` exists and is used in tests/conftest; `core/research/curiosity.py` uses mocked memory. No direct ResearchKG wiring in ResearchRouter. |
| **L12, L13 → Neo4jRes, RDFStore** | ❌ Strategy and civilization routers do not import ResearchKG. |

**Summary for .mmd**: Store types and separation (Operational vs Research KG, Episodic, Working, Vector) match the design. The **layer–store connection matrix** is only partly implemented; many layer routers do not actually use the depicted stores.

---

## 2. Verification against the PNG (conceptual Polyglot diagram)

The PNG describes a more detailed architecture:

- **Polyglot Memory (L0)** as foundation, fed by **ML/Cognitive Graph Data Processing**; L1 components (Learning Engine, Adaptive Decision Engine, Strategy Intelligence) with “internal caching” to Polyglot.
- **Episodic Memory** ← Observation/Perception; Episodic → **Temporal Graph (Events & Relationships)**; Polyglot → Temporal Graph.
- **Declarative Memory** ← Action/Execution, Skill/Tool; Temporal Graph → Declarative; feedback to those layers.
- **Procedural Memory** ← Planner Agent, Cognitive Control; Procedural → **Plan/Task Graph (Actions & Goals)**; Episodic + Declarative → Plan/Task Graph.
- **Operational/Workflow Memory** ← Event Manager; **Sensor/Effectors and Task Goals** ← Agent Server, Operational/Workflow; Plan/Task Graph → Operational/Workflow.

### Mapping to current code

| Conceptual element | In code |
|--------------------|--------|
| **Polyglot Memory (L0)** | ❌ No single “Polyglot” store. `ContextBuilder` (L5) docstring says it “Simulates retrieval of historical data from the Polyglot Memory System” but implementation is mock only (no unified L0 backend). |
| **ML/Cognitive Graph Data Processing** | ⚠️ Consolidation (GovernanceLayer, Distiller) moves Episodic → Procedural/Semantic. No named “ML/Cognitive Graph” module. |
| **Episodic Memory** | ✅ Implemented (PostgresEpisodicStore, SQLiteEpisodicStore). |
| **Temporal Graph (Events & Relationships)** | ❌ No dedicated “Temporal Graph” store. Episodic stores events/tasks with timestamps; there is no separate graph of events/relationships. |
| **Declarative Memory** | ⚠️ Conceptually aligned with **Semantic Memory** (facts, concepts). Implemented as VectorStore (LanceDB) and Neo4jGraphStore for Concept nodes (`graph_api.py`). No type named “Declarative.” |
| **Procedural Memory** | ✅ `core/memory/procedural/procedural_store.py` (ProceduralMemoryStore). GovernanceLayer promotes episodic → procedural. |
| **Plan/Task Graph (Actions & Goals)** | ⚠️ Partially: Director and `graph/graph_api.py` store Task nodes and Task–Blueprint relationships. SwarmOrchestrator holds in-memory plan state. No separate “Plan/Task Graph” store; operational Neo4j and in-memory plans cover this. |
| **Operational/Workflow Memory** | ✅ OperationalKG (Neo4j, agent/task/session state). ai_router `workflow_manager` has “Shared workflow memory” in context. |
| **Sensor/Effectors and Task Goals** | ⚠️ Conceptually: agents and event bus. No module literally named “Sensor/Effectors”; AgentRouter and tool execution fulfill the role. |

### L1 layer names in PNG vs code

- **Learning Engine (L1)** → core Layer 10 (LearningRouter, PolicyManager); not named “Adaptive Decision Engine.”
- **Strategy Intelligence (L1)** → core Layer 12 (strategy engine, forecaster, self_model).
- **Observation/Perception (L1)** → core Layer 2 (PerceptionRouter, normalizer).
- **Action/Execution, Skill/Tool (L1)** → core Layer 8 (execution, tool registry).
- **Planner Agent, Cognitive Control (L1)** → core Layer 5 (CognitiveRouter, Planner, Validator, Aggregator).
- **Event Manager, Agent Server (L1)** → Event bus (SystemEventBus), AgentRouter (Layer 7).

The **data flows** in the PNG (e.g. Episodic → Temporal Graph, Polyglot → Temporal, Procedural → Plan/Task Graph, Plan/Task → Operational/Workflow) are **not fully implemented** as drawn. Consolidation implements Episodic → Procedural and (via GovernanceLayer) episodic → semantic; there is no Temporal Graph or single Polyglot L0.

---

## 3. Broken or missing wiring in code

1. **~~Broken import~~ (fixed)**  
   `core/memory/consolidation/governance_layer.py` and `consolidator.py` previously imported `from ..semantic.neo4j_store import Neo4jGraphStore`, but `core/memory/semantic_memory/neo4j_store.py` did not exist. The import has been updated to `from graph.graph_api import Neo4jGraphStore` so consolidation uses the shared Neo4j graph store (Concept/semantic nodes).
2. **Layer–store connections**: Most layer routers (L3, L4, L5, L6, L7, L8, L9, L10, L12, L13) do not import or use the memory stores shown in the .mmd. Only consolidation, ai_router (working_memory, episodic_memory), and director (graph_api) actively use the stores.
3. **Polyglot L0 and Temporal Graph**: Not implemented. To align with the PNG, you’d need either a unified Polyglot facade over existing stores or a dedicated Temporal Graph store and explicit flows from Episodic into it.

---

## 4. Current vs. future (PNG target architecture)

The PNG diagram (`polyglot_memory_system-2026-02-22-205537.png`) is the **target** architecture. Below is what is **current** vs **future** so diagrams and code stay consistent.

| Element | Status | Notes |
|--------|--------|-------|
| **Polyglot Memory (L0)** | 🔜 Future | Single facade over Working, Episodic, Semantic, Procedural, and graph stores. Not implemented; ContextBuilder currently mocks it. |
| **ML/Cognitive Graph Data Processing** | ⚠️ Partial | Consolidation (GovernanceLayer, Distiller) does Episodic → Procedural/Semantic. No separate “ML/Cognitive Graph” module. |
| **Episodic Memory** | ✅ Current | PostgresEpisodicStore, SQLiteEpisodicStore. |
| **Temporal Graph (Events & Relationships)** | 🔜 Future | No dedicated store. Option: model Episodic as temporal graph or add a Temporal Graph store and flow Episodic → Temporal. |
| **Declarative Memory** | ✅ Current (as Semantic) | VectorStore (LanceDB, etc.) + Neo4jGraphStore Concept nodes. Naming: “Declarative” in PNG = “Semantic” in code. |
| **Procedural Memory** | ✅ Current | ProceduralMemoryStore. GovernanceLayer promotes episodic → procedural. |
| **Plan/Task Graph (Actions & Goals)** | ⚠️ Partial | Director + graph_api store Task nodes; SwarmOrchestrator holds in-memory plans. No separate Plan/Task Graph store. |
| **Operational/Workflow Memory** | ✅ Current | OperationalKG (Neo4j), workflow context in ai_router. |
| **Sensor/Effectors and Task Goals** | ✅ Current | AgentRouter, tool execution, event bus. |
| **Layer–store wiring (L3–L13)** | 🔜 Future | .mmd updated to show only current component→store edges; layer→store matrix is commented as target in the .mmd. |

When implementing the PNG target: add a **Polyglot (L0) facade**, a **Temporal Graph** store or view, and **wire each layer router** to the intended stores per the layer–store matrix in the .mmd (see commented section).

---

## 5. Recommendations

1. **Consolidation imports**: ✅ Done. `GovernanceLayer` and `ConsolidationWorker` now import `Neo4jGraphStore` from `graph.graph_api` for Concept/semantic storage.
2. **Align .mmd with code**: ✅ Done (option a). The .mmd now shows only **current** component→store connections (Director → Neo4jOp; Consolidation → Episodic, Procedural, Neo4jOp; AI Router → Redis, Timescale). Procedural Memory was added. The layer–store matrix (L3–L13) remains in the file as commented-out **target** wiring for future work. 3. **PNG conceptual design**: ✅ Documented. Section 4 above labels each PNG element as Current, Partial, or Future. The PNG remains the target architecture. To implement it you would need: a Polyglot (L0) abstraction or facade, a Temporal Graph store (or model Episodic as temporal graph), and explicit dataflows (Episodic → Temporal, Polyglot → Temporal, etc.). Document which parts are “future” vs “current” so diagrams and code stay consistent.

---

## 6. Summary table

| Item | .mmd diagram | PNG diagram | Code |
|------|--------------|-------------|------|
| Working Memory (Redis) | ✅ | (in Operational/Workflow context) | ✅ |
| Episodic Memory (Postgres) | ✅ | ✅ | ✅ |
| Operational KG (Neo4j) | ✅ | Operational/Workflow | ✅ |
| Research KG | ✅ | (Semantic/learning) | ✅ |
| Vector / Semantic store | ✅ | Declarative | ✅ |
| Procedural Memory | — | ✅ | ✅ |
| Polyglot Memory (L0) | — | ✅ | ❌ (concept only) |
| Temporal Graph | — | ✅ | ❌ |
| Plan/Task Graph (dedicated) | — | ✅ | ⚠️ (Neo4j Task + in-memory plans) |
| Layer–store edges as drawn | — | — | ⚠️ Many missing |
| Consolidation semantic import | — | — | ✅ Fixed (uses graph.graph_api.Neo4jGraphStore) |

**Conclusion**: The memory system **implements the store types** (and their separation) shown in the .mmd and partially the PNG; **layer–store connections** are under-wired and the **conceptual Polyglot/Temporal/Plan-Task flows** from the PNG are not fully implemented. Recommendation status: see Section 5.
