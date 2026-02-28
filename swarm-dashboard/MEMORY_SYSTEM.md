# Memory System (Long-term + Semantic/Episodic/Procedural)

This adds a SQLite-backed memory layer with three APIs:

- `POST /api/memory/router` -> write memory
- `GET /api/memory/router?q=...&type=...&k=...` -> query memory
- `GET /api/memory/health` -> health metrics
- `POST /api/memory/maintenance` -> consolidation/retention/conflict scans

Data lives in:

- `data/memory_system.db`

Graph pointers:

- Writes create compact `ResearchDoc` pointer nodes in Neo4j (`kind: "MemoryPointer"`) and `AUTHORED_DOC` / `ABOUT` relationships.

## Write

```bash
curl -s -X POST http://localhost:3000/api/memory/router \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Hina is researching model-routing for retrieval precision",
    "agent": "Hina",
    "intent": "research insight",
    "metadata": {
      "claim_key": "hina_research_focus",
      "stance": "positive",
      "concepts": ["model-routing", "retrieval"]
    }
  }' | jq
```

## Query

```bash
curl -s 'http://localhost:3000/api/memory/router?q=What%20is%20Hina%20researching%3F&type=semantic&k=5' | jq
```

## Health

```bash
curl -s http://localhost:3000/api/memory/health | jq
```

## Maintenance

Default (all three passes):

```bash
curl -s -X POST http://localhost:3000/api/memory/maintenance \
  -H 'Content-Type: application/json' \
  -d '{}' | jq
```

Custom:

```bash
curl -s -X POST http://localhost:3000/api/memory/maintenance \
  -H 'Content-Type: application/json' \
  -d '{
    "actions": ["consolidate", "retention", "conflicts"],
    "payload": {
      "window_days": 7,
      "min_items": 6,
      "keep_days": 90,
      "confidence_threshold": 0.35,
      "limit": 10000
    }
  }' | jq
```
