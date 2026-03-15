# Architecture Diagram Verification Report

This document compares the architecture diagrams (PNG/.mmd in `docs/diagrams/` and the images you provided) with `docs/architecture_diagrams.md` and the codebase, and lists placeholder/stub files that may need follow-up.

---

## 1. Inconsistencies Between Diagrams and architecture_diagrams.md

### 1.1 Cognitive pipeline (Section 4) vs layer .mmd files

| Aspect | architecture_diagrams.md (Section 4) | Layer .mmd / diagrams |
|--------|-------------------------------------|------------------------|
| **Layer 2 Perception** | Shows only `Normalize → OBSERVATION` | Full diagram: Environment → Input Normalizer → Vision (Moondream), Speech (Whisper), Text Understanding → Attention/Priority Filtering → System Event Bus. Model names (Moondream, Whisper) and “Attention / Priority Filtering” and “System Event Bus” are **not** in the in-doc Mermaid. |
| **Layer 3 Task Understanding** | Linear: TaskParser → DecompositionEngine → GoalManager → TASK_SPAWNED | Full diagram: Intent Detection → Task Parser → Context-Aware Parsing (with Memory Layer) → Task Decomposition → Priority Scoring → Conflict Resolution → Multi-Agent Assignment → Planner/Orchestrator. The doc **omits**: Context-Aware Parsing, Priority Scoring, Conflict Resolution, Multi-Agent Assignment, and Memory → Context-Aware. |
| **Layer 4 System Spine** | SafetyGate → PermissionsValidator → ResourceManager → EXECUTION_APPROVED | Diagram 4 and .mmd: Resource Manager, Safety & Governance, **Health & Telemetry**, **Identity & Permissions**. Doc does **not** name Health & Telemetry or Identity & Permissions in the pipeline. |
| **Layer 5 Core Cognitive** | Ctx → Plan → Val → Agg (ContextBuilder, ExecutionPlanner, ReasoningValidator, ResultAggregator) | .mmd: Planner, Context Builder, Reasoning Validator, Result Aggregator. “ExecutionPlanner” in doc vs “Planner” in .mmd is naming only; flow matches. |
| **Layer 6 Swarm Manager** | Orch → MR → ADR (linear) | .mmd: **Aggregated Plan → Orchestrator**; **Capability Registry → Model Router**; both Orchestrator and Model Router → **Task Scheduler** → Agent Swarm. The doc does **not** show “Task Scheduler” as a box; it collapses the flow to Orch → MR → ADR. |
| **Layer 7 Agent Swarm** | “Planner / Coder / Evaluator / ...” | Agent Swarm .mmd: **System Agents, Simulation Agents, Research Agents, Coding Agents, Reasoning Agents**. Different taxonomy (no “Evaluator” in the five; “Coder” vs “Coding Agents”). |
| **Layer 8 Execution** | “Tool Exec / Code Run” | .mmd: **Tool Executor** (receives L7) → **System Control** (→ Health & Telemetry L4), **Automation Engine**, **Code Runner** (→ Result Aggregator L5); Tool Executor also → Result Aggregator. Doc omits System Control and Automation Engine. |

**Recommendation:** Either extend Section 4’s in-doc Mermaid to include the missing components (e.g. Task Scheduler, agent types, Execution sub-components) or add a short note that Section 4 is a simplified view and that the authoritative detail is in `docs/diagrams/*.mmd`.

### 1.2 Full 13-layer overview (Section 11) vs layer diagrams

- **Layer 11:** Doc says “Curiosity”, “Hypothesis / Experiments”. .mmd has Curiosity Engine, Hypothesis Generator, Experiment Designer, Experiment Runner, Discovery Agents. Abbreviation only.
- **Layer 12:** Doc says “Strategy Engine”, “Self-Model”. .mmd has Long-Horizon Strategy, Technology Radar, Capability Forecasting, System Self-Model. Doc omits Technology Radar and Capability Forecasting in the simplified diagram.
- **Layer 13:** Doc says “Governance Council”, “Innovation”. .mmd adds Infrastructure Evolution, Knowledge Economy, Agent Society Manager. Abbreviation only.

### 1.3 Civilization Loop (Layer 13) – diagram vs .mmd

- **Image (13-civilization):** “Autonomous Research (Layer 11) sends output to **Governance Council**.”
- **.mmd (13-civilization_layer):** `Discovery["Autonomous Research (Layer 11)"] --> Innovation` (sends to **Innovation Engine**, not Governance Council).

So either the PNG and the .mmd disagree (L11 → Governance Council vs L11 → Innovation), or one was updated. Worth aligning the .mmd with the intended design (and with the PNG if that is the source of truth).

### 1.4 System Spine diagram (4-system_spine_layer .mmd)

- The **same subgraph** “4. System Spine” (Resource Manager, Safety & Governance, Health & Telemetry, Identity & Permissions) is **defined twice** (lines 1–7 and 36–42). This is redundant and can confuse renderers; one definition is enough.
- The diagram mixes Layer 2, Layer 3, Registry, and Layer 4 in one file; the doc’s Section 4 only describes the L4 pipeline. No conflict, but the .mmd is the richer source.

### 1.5 Observability (Section 10)

- The doc explicitly calls out **“habitats: localhost:8080 placeholder”** in the Prometheus scrape config. This matches `observability/prometheus.yml` and is documented as a placeholder.

---

## 2. Missing or Under-specified Elements in the Doc

1. **Perception:** No mention of **System Event Bus** as the output of the Perception layer in the main pipeline (Section 4). The Perception .mmd shows Normalize → Vision/Speech/Text → Attention → **System Event Bus**.
2. **Task Understanding:** **Memory Layer** input into Context-Aware Parsing is not shown in Section 4.
3. **Execution & Integration:** **System Control** and its link to **Health & Telemetry (Layer 4)** are not in the in-doc pipeline; only “Tool Exec / Code Run” is mentioned.
4. **Agent types:** The five agent types (System, Simulation, Research, Coding, Reasoning) from the Agent Swarm diagram are not listed in the doc; the doc uses “Planner / Coder / Evaluator / ...”.
5. **Layer 12:** Technology Radar and Capability Forecasting are in the .mmd but not in the simplified Section 11 diagram.
6. **Polyglot Memory / Memory system:** The doc points to `MEMORY_SYSTEM_VERIFICATION.md` for diagram vs code. That file already notes missing layer–store wiring and Polyglot L0 / Temporal Graph as future work.

---

## 3. Placeholder and Stub Files (Workspace)

These are under `ai/Raphael` (excluding `.venv_raphael` and third-party packages).

### 3.1 Documented in AGENTS.md

- `core/interfaces/adapters/task_manager_adapter.py` – returns placeholder data.
- `core/interfaces/adapters/browser_adapter.py` – returns placeholder data.
- `ai_router/agent.py` – minimal placeholder module.
- `observability/prometheus.yml` – `localhost:8080` placeholder scrape target for agent metrics.

### 3.2 Other adapters (same pattern as task_manager / browser)

- `core/interfaces/adapters/file_system_adapter.py` – returns `"files": "placeholder"`, `"content": "placeholder"`.
- `core/interfaces/adapters/email_adapter.py` – returns `"emails": "placeholder"`, `"message_id": "placeholder"`.
- `core/interfaces/adapters/calendar_adapter.py` – returns `"events": "placeholder"`, `"event_id": "placeholder"`.

**Suggestion:** Add these three to AGENTS.md “Placeholders and known stubs” so they are not forgotten.

### 3.3 AI Router

- `ai_router/agent.py` – “Agent logic placeholder.” (already in AGENTS.md)
- `ai_router/tool_router.py` – “Tool routing module placeholder.”
- `ai_router/config.yaml` – “# Configuration placeholder” (may be intentional minimal config).

**Suggestion:** Add `ai_router/tool_router.py` to AGENTS.md.

### 3.4 Core / perception and cognition

- `core/perception/models.py` – **MockVisionModel** “Placeholder for Moondream/vision integration”; **MockSpeechModel** “Placeholder for Whisper/audio integration.” Aligns with Perception diagram (Vision Models Moondream, Speech Models Whisper).
- `core/understanding/decomposition.py` – “(This is a placeholder for an LLM/Cognitive evaluation layer).”
- `core/interfaces/api/api_interface.py` – “For now, this is a placeholder for the API layer.”
- `core/cognitive/validator.py` – “Allowed system capabilities (Placeholder until Layer 6 Swarm defines them).”
- `core/planner/resource_manager.py` – “Placeholder static cost.”
- `core/memory/consolidation/governance_layer.py` – “avg_latency=1.0  # Placeholder until we track latency in episodic.”
- `core/memory/semantic_memory/vector_store.py` – “# Schema placeholder: vector, text, id, metadata.”
- `core/evaluation/sandbox.py` – “Native Docker binding requested but SDK is not implemented in logic yet.”

### 3.5 Experiments and federation

- `experiments/scheduler.py` – “qsize = 0  # Placeholder for actual queue size lookup.”
- `ai_router/federation_manager.py` – “# Auth token for inter-cluster communication (placeholder).”

### 3.6 Event subscriptions (TODO in agents)

- `agents/exploration_engine.py` – “# TODO: Subscribe to exploration requested events”
- `agents/system_monitor_agent.py` – “# TODO: Subscribe to health and status events”
- `agents/performance_analyzer.py` – “# TODO: Subscribe to performance/metrics events”
- `agents/optimization_agent.py` – “# TODO: Subscribe to optimization events”
- `agents/experiment_agent.py` – “# TODO: Subscribe to experiment events”
- `agents/deployment_agent.py` – “# TODO: Subscribe to deployment-related events”
- `swarm/swarm_manager.py` – “# TODO: Subscribe to cluster and swarm events”

(Already called out in AGENTS.md.)

### 3.7 Other (not placeholders, but for context)

- `core/memory/episodic_memory/postgres_store.py` – “# TODO: Implement complex filtering based on JSONB payload”
- `core/memory/episodic_memory/database.py` – “Convert PostgreSQL-style placeholders ($1, $2, …)” (implementation detail, not a stub)
- `graph/seed_data/hardware.cypher` – “Clean up old placeholder data” (data cleanup)
- `core/memory/knowledge_graph/swarm_architecture_schem.cypher` – hostname: "placeholder" (seed data)
- `core/environment/network.py` – “Placeholder for web search capability.”

---

## 4. Diagram File Inventory

All expected layer .mmd files are present in `docs/diagrams/`:

| Layer | File pattern | Status |
|-------|----------------|--------|
| 1 Environment | `1-environment_layer-*.mmd` | Present |
| 2 Perception | `2-perception_layer-*.mmd` | Present |
| 3 Task Understanding | `3-task_understanding_layer-*.mmd` | Present |
| 4 System Spine | `4-system_spine_layer-*.mmd` | Present (has duplicate L4 subgraph) |
| 5 Core Cognitive | `5-core_cognitive_layer-*.mmd` | Present |
| 6 Swarm Manager | `6-swarm_manager_layer-*.mmd` | Present |
| 7 Agent Swarm | `7-agent_swarm-*.mmd` | Present |
| 8 Execution & Integration | `8-execution-integration_layer-*.mmd` | Present |
| 9 Evaluation | `9-evaluation_layer-*.mmd` | Present |
| 10 Learning | `10-learning_layer-*.mmd` | Present |
| 11 Autonomous Research | `11-autonomous_research_layer-*.mmd` | Present |
| 12 Strategic Intelligence | `12-strategic_intelligence-*.mmd` | Present |
| 13 Civilization Loop | `13-civilization_layer-*.mmd` | Present |
| Memory | `polyglot_memory_system-*.mmd` | Present |
| Full system | `complete_system_architecture.mmd` | Present |

The doc’s “Layer-specific diagrams” table matches the files. The PNGs you provided align with these .mmd descriptions except for the Civilization L11→Governance vs L11→Innovation difference noted above.

---

## 5. Recommended Next Steps

1. **architecture_diagrams.md:** Add a one-paragraph “Diagram consistency” note at the top or after the index stating that the in-doc Mermaid (e.g. Section 4, Section 11) is simplified and that the authoritative per-layer detail is in `docs/diagrams/*.mmd`; optionally add a link to this verification report.
2. **Civilization Loop:** Decide whether L11 (Autonomous Research) output goes to Governance Council or Innovation Engine and align the .mmd (and PNG, if regenerated) with that decision.
3. **4-system_spine_layer .mmd:** Remove the duplicate “4. System Spine” subgraph (keep a single definition).
4. **AGENTS.md:** Extend “Placeholders and known stubs” to include:
   - `core/interfaces/adapters/file_system_adapter.py`, `email_adapter.py`, `calendar_adapter.py`
   - `ai_router/tool_router.py`
5. **Optional:** Add a short “Placeholders” subsection in `docs/IMPLEMENTATION_CHECKLIST.md` or link to this report for the full placeholder list.
