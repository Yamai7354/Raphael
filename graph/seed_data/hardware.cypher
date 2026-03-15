// Phase 6: Hardware Awareness — Real Machine & GPU Topology
// Seeded from desktop_hardware_capabilities.json and mac_hardware_capabilities.json
// Run: kubectl exec -n graph neo4j-0 -- cypher-shell -u neo4j -p raphael-neo4j -f /tmp/phase6_hardware.cypher
// ─── Clean up old placeholder data ─────────────────────────────
MATCH (m:Machine)
DETACH DELETE m;
MATCH (g:GPU)
DETACH DELETE g;

// ═══════════════════════════════════════════════════════════════
// MacBook — Apple M4 (primary dev machine)
// ═══════════════════════════════════════════════════════════════
CREATE
  (m:Machine
    {
      name: "macbook",
      hostname: "ai-macbook",
      tailscale_ip: "100.66.48.16",
      cpu_name: "Apple M4",
      cpu_arch: "ARM64",
      cpu_cores: 10,
      cpu_extensions: "AdvSIMD",
      ram_gb: 16,
      vram_gb: 12,
      total_memory_bytes: 17179869184,
      storage_gb: 500,
      cluster: "raphael-swarm",
      role: "development",
      model_formats: "gguf,safetensors",
      gpu_platform: "Metal",
      metal_gpu_family: 9,
      memory_type: "infrastructure",
      promotion_score: 1.0
    });

// ═══════════════════════════════════════════════════════════════
// Desktop — AMD Ryzen 5 PRO 2400G + R9 390 (remote compute)
// ═══════════════════════════════════════════════════════════════
CREATE
  (m:Machine
    {
      name: "desktop",
      hostname: "ai-desktop",
      tailscale_ip: "100.125.58.22",
      cpu_name: "AMD Ryzen 5 PRO 2400G with Radeon Vega Graphics",
      cpu_arch: "x86_64",
      cpu_cores: 4,
      cpu_extensions: "AVX,AVX2",
      ram_gb: 14,
      vram_gb: 8,
      total_memory_bytes: 23534895104,
      storage_gb: 500,
      cluster: "raphael-swarm",
      role: "gpu-compute",
      model_formats: "gguf",
      gpu_platform: "Vulkan",
      memory_type: "infrastructure",
      promotion_score: 1.0
    });

// ─── GPU Definitions ────────────────────────────────────────────

// Apple M4 — unified memory GPU (Metal)
CREATE
  (g:GPU
    {
      name: "apple-m4",
      manufacturer: "apple",
      vram_gb: 12,
      dedicated_vram_bytes: 12713115648,
      total_memory_bytes: 17179869184,
      integration: "Integrated",
      platform: "Metal",
      metal_gpu_family: 9,
      compute_capability: "metal-9",
      memory_type: "infrastructure",
      promotion_score: 1.0
    });

// AMD Radeon R9 390 — discrete GPU (Vulkan)
CREATE
  (g:GPU
    {
      name: "amd-r9-390",
      manufacturer: "amd",
      vram_gb: 8,
      dedicated_vram_bytes: 8589934592,
      total_memory_bytes: 15793651712,
      integration: "Discrete",
      platform: "Vulkan",
      platform_version: "1.3.283",
      compute_capability: "vulkan-1.3",
      memory_type: "infrastructure",
      promotion_score: 1.0
    });

// AMD Radeon Vega 11 — integrated GPU (Vulkan)
CREATE
  (g:GPU
    {
      name: "amd-vega-11",
      manufacturer: "amd",
      vram_gb: 2,
      dedicated_vram_bytes: 2147483648,
      total_memory_bytes: 9351200768,
      integration: "Integrated",
      platform: "Vulkan",
      platform_version: "1.3.283",
      compute_capability: "vulkan-1.3",
      memory_type: "infrastructure",
      promotion_score: 1.0
    });

// ─── Machine → GPU Relationships ────────────────────────────────
MATCH (m:Machine {name: "macbook"}), (g:GPU {name: "apple-m4"})
MERGE (m)-[:HAS_GPU {count: 1, status: "available", type: "unified"}]->(g);

MATCH (m:Machine {name: "desktop"}), (g:GPU {name: "amd-r9-390"})
MERGE (m)-[:HAS_GPU {count: 1, status: "available", type: "discrete"}]->(g);

MATCH (m:Machine {name: "desktop"}), (g:GPU {name: "amd-vega-11"})
MERGE (m)-[:HAS_GPU {count: 1, status: "available", type: "integrated"}]->(g);

// ─── Service → Machine (RUNS_ON) ────────────────────────────────
// Services run on the macbook (primary k3d cluster host)
MATCH (s:Service {name: "vector_memory"}), (m:Machine {name: "macbook"})
MERGE (s)-[:RUNS_ON]->(m);

MATCH (s:Service {name: "repo_service"}), (m:Machine {name: "macbook"})
MERGE (s)-[:RUNS_ON]->(m);

MATCH (s:Service {name: "model_cache"}), (m:Machine {name: "macbook"})
MERGE (s)-[:RUNS_ON]->(m);

// ─── GPU-Required Capabilities ──────────────────────────────────
// GPU inference can use either the R9 390 or the M4
MATCH (c:Capability {name: "gpu_inference"}), (g:GPU {name: "amd-r9-390"})
MERGE (c)-[:REQUIRES_GPU]->(g);

MATCH (c:Capability {name: "gpu_inference"}), (g:GPU {name: "apple-m4"})
MERGE (c)-[:REQUIRES_GPU]->(g);

MATCH (c:Capability {name: "video_generation"}), (g:GPU {name: "amd-r9-390"})
MERGE (c)-[:REQUIRES_GPU]->(g);

// ─── Habitat → Machine ─────────────────────────────────────────
// Research and coding run on macbook (primary dev machine)
MATCH
  (h:HabitatBlueprint {name: "research_habitat"}), (m:Machine {name: "macbook"})
MERGE (h)-[:RUNS_ON {preference: "primary"}]->(m);

MATCH
  (h:HabitatBlueprint {name: "coding_habitat"}), (m:Machine {name: "macbook"})
MERGE (h)-[:RUNS_ON {preference: "primary"}]->(m);

// GPU inference primary on desktop (discrete R9 390), fallback to macbook (M4 Metal)
MATCH
  (h:HabitatBlueprint {name: "gpu_inference_habitat"}),
  (m:Machine {name: "desktop"})
MERGE (h)-[:RUNS_ON {preference: "primary"}]->(m);

MATCH
  (h:HabitatBlueprint {name: "gpu_inference_habitat"}),
  (m:Machine {name: "macbook"})
MERGE (h)-[:RUNS_ON {preference: "fallback"}]->(m);