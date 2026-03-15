// Phase 1: Knowledge Graph Core — Capabilities Seed
// ─── Base Capabilities ──────────────────────────────────────────
MERGE (c:Capability {name: "code_generation"})
SET
  c.description = "Ability to generate, refactor, and debug code",
  c.memory_type = "infrastructure",
  c.promotion_score = 1.0;

MERGE (c:Capability {name: "research"})
SET
  c.description = "Ability to search, summarize, and synthesize information",
  c.memory_type = "infrastructure",
  c.promotion_score = 1.0;

MERGE (c:Capability {name: "video_generation"})
SET
  c.description = "Ability to generate and edit video content",
  c.memory_type = "infrastructure",
  c.promotion_score = 1.0;

MERGE (c:Capability {name: "gpu_inference"})
SET
  c.description = "Ability to run GPU-accelerated model inference",
  c.memory_type = "infrastructure",
  c.promotion_score = 1.0;

// ─── Base Services ──────────────────────────────────────────────
MERGE (s:Service {name: "vector_memory"})
SET
  s.description = "Persistent vector database for semantic search",
  s.memory_type = "infrastructure",
  s.promotion_score = 1.0;

MERGE (s:Service {name: "repo_service"})
SET
  s.description = "Git repository management and code operations",
  s.memory_type = "infrastructure",
  s.promotion_score = 1.0;

MERGE (s:Service {name: "model_cache"})
SET
  s.description = "Caches downloaded model weights for fast loading",
  s.memory_type = "infrastructure",
  s.promotion_score = 1.0;