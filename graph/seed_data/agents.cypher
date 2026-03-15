// Phase 1: Knowledge Graph Core — Agents Seed
// ─── Base Agent Types ───────────────────────────────────────────
MERGE (a:AgentType {name: "planner"})
SET
  a.description = "Orchestrates task decomposition and agent coordination",
  a.memory_type = "infrastructure",
  a.promotion_score = 1.0;

MERGE (a:AgentType {name: "coding_agent"})
SET
  a.description = "Writes, reviews, and tests code",
  a.memory_type = "infrastructure",
  a.promotion_score = 1.0;

MERGE (a:AgentType {name: "search_agent"})
SET
  a.description = "Performs web and knowledge base searches",
  a.memory_type = "infrastructure",
  a.promotion_score = 1.0;

MERGE (a:AgentType {name: "test_runner"})
SET
  a.description = "Executes test suites and reports results",
  a.memory_type = "infrastructure",
  a.promotion_score = 1.0;

MERGE (a:AgentType {name: "embedding_worker"})
SET
  a.description = "Generates vector embeddings for documents and queries",
  a.memory_type = "infrastructure",
  a.promotion_score = 1.0;

// ─── AgentType → Capability Relationships ───────────────────────
MATCH (a:AgentType {name: "planner"}), (c:Capability {name: "research"})
MERGE (a)-[:HAS_CAPABILITY]->(c);

MATCH
  (a:AgentType {name: "coding_agent"}), (c:Capability {name: "code_generation"})
MERGE (a)-[:HAS_CAPABILITY]->(c);

MATCH (a:AgentType {name: "search_agent"}), (c:Capability {name: "research"})
MERGE (a)-[:HAS_CAPABILITY]->(c);

MATCH
  (a:AgentType {name: "test_runner"}), (c:Capability {name: "code_generation"})
MERGE (a)-[:HAS_CAPABILITY]->(c);

MATCH
  (a:AgentType {name: "embedding_worker"}),
  (c:Capability {name: "gpu_inference"})
MERGE (a)-[:HAS_CAPABILITY]->(c);