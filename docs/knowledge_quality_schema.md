# Knowledge Quality System

The swarm must learn what deserves memory. Low-quality or junk content is not stored permanently.

## Quality score

```
score = relevance + reuse_frequency + success_rate
```

(Each component normalized; combined into a single `quality_score` in `[0, 1]`.)

## Neo4j node: KNOWLEDGE

| Property       | Type   | Description                    |
|----------------|--------|--------------------------------|
| `content`      | string | The knowledge snippet          |
| `source`       | string | Origin (e.g. `"agent"`, `"user"`) |
| `quality_score`| float  | Composite score in [0, 1]     |
| `reuse_count`  | int    | How often this was reused     |
| `first_seen`   | datetime | Optional                    |
| `last_seen`    | datetime | Optional                    |

Example:

```cypher
(:KNOWLEDGE {
  content: "...",
  source: "agent",
  quality_score: 0.82,
  reuse_count: 4
})
```

## Retention rules

| Score      | Action            |
|-----------|-------------------|
| **≥ 0.8** | Permanent memory  |
| **0.5–0.8** | Embedding store (vector index) |
| **< 0.5** | Delete after TTL  |

- **Permanent:** Stored in Neo4j long-term; used for reasoning and retrieval.
- **Embedding store:** Stored in Qdrant (or similar); used for semantic search; can be promoted to permanent if score later rises.
- **TTL:** Ephemeral; discarded after a short time window unless score improves.

This prevents the swarm from hoarding low-value content.
