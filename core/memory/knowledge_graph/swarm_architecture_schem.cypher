// Swarm Routing Knowledge Graph Schema
// Designed for distributed LLM routing and agent orchestration
// Compatible with Neo4j
// ======================================================
// CONSTRAINTS
// ======================================================

CREATE CONSTRAINT machine_id IF NOT EXISTS
FOR (m:Machine) REQUIRE m.id IS UNIQUE;

CREATE CONSTRAINT model_name IF NOT EXISTS
FOR (m:Model) REQUIRE m.name IS UNIQUE;

CREATE CONSTRAINT agent_name IF NOT EXISTS
FOR (a:Agent) REQUIRE a.name IS UNIQUE;

CREATE CONSTRAINT capability_name IF NOT EXISTS
FOR (c:Capability) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT tool_name IF NOT EXISTS
FOR (t:Tool) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT skill_name IF NOT EXISTS
FOR (s:Skill) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT task_id IF NOT EXISTS
FOR (t:Task) REQUIRE t.id IS UNIQUE;


// ======================================================
// INDEXES
// ======================================================

CREATE INDEX machine_status IF NOT EXISTS
FOR (m:Machine) ON (m.status);

CREATE INDEX model_family IF NOT EXISTS
FOR (m:Model) ON (m.family);

CREATE INDEX performance_tokens IF NOT EXISTS
FOR (p:PerformanceProfile) ON (p.tokens_per_sec);

CREATE INDEX hardware_type IF NOT EXISTS
FOR (h:Hardware) ON (h.type);


// ======================================================
// INFRASTRUCTURE LAYER
// ======================================================
// Machines
CREATE (:Machine {
  id: "example-node",
  hostname: "placeholder",
  tailscale_ip: "0.0.0.0",
  status: "online"
});

// Hardware
CREATE (:Hardware {
  type: "GPU",
  name: "example_gpu",
  vram_gb: 0
});

// Relationships
(Machine)-[
    :HAS_HARDWARE
]->(Hardware)
(Machine)-[
    :CONNECTED_TO
]->(Machine)
(Machine)-[
    :RUNS_RUNTIME
]->(Runtime)
(Machine)-[
    :HAS_LOAD
]->(Load)
// ======================================================
// MODEL INTELLIGENCE LAYER
// ======================================================
// Models
CREATE (:Model {
  name: "example-model",
  family: "llm",
  parameters_b: 7,
  quantization: "q4"
});

// Capabilities
CREATE (:Capability {name: "reasoning"
});
CREATE (:Capability {name: "coding"
});
CREATE (:Capability {name: "analysis"
});
CREATE (:Capability {name: "planning"
});

// Model Relationships
(Model)-[
    :HAS_CAPABILITY
]->(Capability)
(Model)-[
    :RUNS_ON
]->(Machine)
(Model)-[
    :REQUIRES_HARDWARE
]->(Hardware)
(Model)-[
    :HAS_PERFORMANCE
]->(PerformanceProfile)
// ======================================================
// SWARM BEHAVIOR LAYER
// ======================================================
// Agents
CREATE (:Agent {
  name: "router_agent",
  role: "task_router"
});

// Skills
CREATE (:Skill {name: "code_generation"
});
CREATE (:Skill {name: "system_design"
});
CREATE (:Skill {name: "research_analysis"
});

// Relationships
(Agent)-[
    :HAS_SKILL
]->(Skill)
(Agent)-[
    :USES_MODEL
]->(Model)
(Agent)-[
    :CAN_USE_TOOL
]->(Tool)
(Skill)-[
    :SUPPORTED_BY_MODEL
]->(Model)
// ======================================================
// TOOL EXECUTION LAYER
// ======================================================
// Tools
CREATE (:Tool {
  name: "code_executor",
  latency_ms: 0
});

// Relationships
(Tool)-[
    :RUNS_ON
]->(Machine)
(Tool)-[
    :REQUIRES_HARDWARE
]->(Hardware)
(Agent)-[
    :CAN_USE
]->(Tool)
// ======================================================
// TASK & ROUTING LAYER
// ======================================================
// Task example
CREATE (:Task {
  id: "example-task",
  type: "code_generation",
  priority: 1
});

// Relationships
(Task)-[
    :REQUIRES_CAPABILITY
]->(Capability)
(Task)-[
    :ASSIGNED_TO
]->(Agent)
(Task)-[
    :EXECUTED_ON
]->(Machine)
(Task)-[
    :USED_MODEL
]->(Model)
// ======================================================
// PERFORMANCE & LEARNING LAYER
// ======================================================

CREATE (:PerformanceProfile {
  tokens_per_sec: 0,
  latency_ms: 0,
  success_rate: 1.0
});

// Relationships
(Model)-[
    :HAS_PERFORMANCE
]->(PerformanceProfile)
(PerformanceProfile)-[
    :MEASURED_ON
]->(Machine)
// ======================================================
// CORE SWARM ROUTING QUERY
// ======================================================
// Find best model + machine for a task
// Example query template:
MATCH (task:Task)-[
    :REQUIRES_CAPABILITY
]->(cap:Capability)
MATCH (model:Model)-[hc:HAS_CAPABILITY
]->(cap)
MATCH (model)-[
    :RUNS_ON
]->(machine:Machine)
MATCH (model)-[
    :HAS_PERFORMANCE
]->(perf:PerformanceProfile)

WHERE machine.status = "online"

RETURN model.name AS model,
       machine.id AS machine,
       perf.tokens_per_sec AS speed,
       hc.score AS capability_score

ORDER BY speed DESC, capability_score DESC
LIMIT 1;
*/
// ======================================================
// ADVANCED SWARM QUERY
// Agent + Model + Machine Selection
// ======================================================
MATCH (task:Task)-[
    :REQUIRES_CAPABILITY
]->(cap:Capability)
MATCH (agent:Agent)-[
    :HAS_SKILL
]->(:Skill)-[
    :SUPPORTED_BY_MODEL
]->(model:Model)
MATCH (model)-[
    :HAS_CAPABILITY
]->(cap)
MATCH (model)-[
    :RUNS_ON
]->(machine:Machine)
MATCH (model)-[
    :HAS_PERFORMANCE
]->(perf:PerformanceProfile)

WHERE machine.status = "online"

RETURN agent.name,
       model.name,
       machine.id,
       perf.tokens_per_sec
ORDER BY perf.tokens_per_sec DESC
LIMIT 1;
*/