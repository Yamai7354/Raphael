// Phase 2: Habitat Blueprint System
// Run via: kubectl exec -n graph neo4j-0 -- cypher-shell -u neo4j -p raphael-neo4j -f /tmp/phase2_blueprints.cypher
// ─── Research Habitat ───────────────────────────────────────────
MERGE (h:HabitatBlueprint {name: "research_habitat"})
SET
  h.description = "Habitat for information gathering, synthesis, and analysis",
  h.helmChart = "charts/research-habitat",
  h.recommendedAgents = 4,
  h.memory_type = "infrastructure",
  h.promotion_score = 1.0;

// Research habitat requires research capability
MATCH
  (h:HabitatBlueprint {name: "research_habitat"}),
  (c:Capability {name: "research"})
MERGE (h)-[:REQUIRES_CAPABILITY]->(c);

// Research habitat spawns planner + search agents
MATCH
  (h:HabitatBlueprint {name: "research_habitat"}),
  (a:AgentType {name: "planner"})
MERGE (h)-[:SPAWNS_AGENT {count: 1, role: "coordinator"}]->(a);

MATCH
  (h:HabitatBlueprint {name: "research_habitat"}),
  (a:AgentType {name: "search_agent"})
MERGE (h)-[:SPAWNS_AGENT {count: 3, role: "worker"}]->(a);

// Research habitat uses vector_memory
MATCH
  (h:HabitatBlueprint {name: "research_habitat"}),
  (s:Service {name: "vector_memory"})
MERGE (h)-[:USES_SERVICE]->(s);

// ─── Coding Habitat ────────────────────────────────────────────
MERGE (h:HabitatBlueprint {name: "coding_habitat"})
SET
  h.description = "Habitat for code generation, review, and testing",
  h.helmChart = "charts/coding-habitat",
  h.recommendedAgents = 6,
  h.memory_type = "infrastructure",
  h.promotion_score = 1.0;

// Coding habitat requires code_generation capability
MATCH
  (h:HabitatBlueprint {name: "coding_habitat"}),
  (c:Capability {name: "code_generation"})
MERGE (h)-[:REQUIRES_CAPABILITY]->(c);

// Coding habitat spawns planner + coding agents + test runner
MATCH
  (h:HabitatBlueprint {name: "coding_habitat"}), (a:AgentType {name: "planner"})
MERGE (h)-[:SPAWNS_AGENT {count: 1, role: "coordinator"}]->(a);

MATCH
  (h:HabitatBlueprint {name: "coding_habitat"}),
  (a:AgentType {name: "coding_agent"})
MERGE (h)-[:SPAWNS_AGENT {count: 4, role: "worker"}]->(a);

MATCH
  (h:HabitatBlueprint {name: "coding_habitat"}),
  (a:AgentType {name: "test_runner"})
MERGE (h)-[:SPAWNS_AGENT {count: 1, role: "validator"}]->(a);

// Coding habitat uses repo_service + vector_memory
MATCH
  (h:HabitatBlueprint {name: "coding_habitat"}),
  (s:Service {name: "repo_service"})
MERGE (h)-[:USES_SERVICE]->(s);

MATCH
  (h:HabitatBlueprint {name: "coding_habitat"}),
  (s:Service {name: "vector_memory"})
MERGE (h)-[:USES_SERVICE]->(s);

// ─── GPU Inference Habitat ──────────────────────────────────────
MERGE (h:HabitatBlueprint {name: "gpu_inference_habitat"})
SET
  h.description =
    "Habitat for GPU-accelerated model inference and embedding generation",
  h.helmChart = "charts/gpu-inference-habitat",
  h.recommendedAgents = 3,
  h.memory_type = "infrastructure",
  h.promotion_score = 1.0;

// GPU inference habitat requires gpu_inference capability
MATCH
  (h:HabitatBlueprint {name: "gpu_inference_habitat"}),
  (c:Capability {name: "gpu_inference"})
MERGE (h)-[:REQUIRES_CAPABILITY]->(c);

// GPU inference habitat spawns embedding workers
MATCH
  (h:HabitatBlueprint {name: "gpu_inference_habitat"}),
  (a:AgentType {name: "embedding_worker"})
MERGE (h)-[:SPAWNS_AGENT {count: 3, role: "worker"}]->(a);

// GPU inference habitat uses model_cache
MATCH
  (h:HabitatBlueprint {name: "gpu_inference_habitat"}),
  (s:Service {name: "model_cache"})
MERGE (h)-[:USES_SERVICE]->(s);