# Hybrid Research Graph

## Why
The graph is too large for raw research exhaust. Use Neo4j for structure and move verbose research content to SQLite + optional embeddings.

## What this adds
- `app/hybridize_research_graph.py`
  - Migrates `Memory -> Concept` research traces into `data/research_hybrid.db` (`research_docs` table)
  - Creates compact graph links:
    - `(Agent)-[:AUTHORED_DOC]->(ResearchDoc)`
    - `(ResearchDoc)-[:ABOUT]->(Concept)`
  - Marks source memory nodes as `archived=true`
  - Optional pruning of archived old memory nodes
  - Optional embeddings via Ollama (`/api/embeddings`)
- `app/api/research-hybrid/route.ts`
  - `GET`: latest migration report
  - `POST`: run migration/prune with options

## CLI usage

```bash
cd /Users/yamai/ai/Raphael/swarm-dashboard
./.venv/bin/python app/hybridize_research_graph.py --limit 4000
```

With embeddings:

```bash
./.venv/bin/python app/hybridize_research_graph.py --limit 2000 --embed --embed-model text-embedding-bge-large-en-v1.5
```

With pruning:

```bash
./.venv/bin/python app/hybridize_research_graph.py --limit 3000 --prune --prune-days 14 --prune-batch 5000
```

One-time compaction + immediate shrink:

```bash
./.venv/bin/python app/hybridize_research_graph.py --limit 5000 --compact --prune --aggressive-prune --prune-batch 10000
```

## API usage

```bash
curl -s http://localhost:3000/api/research-hybrid | jq
```

```bash
curl -s -X POST http://localhost:3000/api/research-hybrid \
  -H 'Content-Type: application/json' \
  -d '{"limit":4000,"embed":false,"compact":true,"prune":true,"aggressivePrune":true,"pruneDays":14,"pruneBatch":5000}' | jq
```

## Storage
- Structured graph: Neo4j (`ResearchDoc` summary nodes and structural edges)
- Research content store: `data/research_hybrid.db`
- Latest run report: `data/research_hybrid_report.json`

## Next recommended step
Add a retrieval endpoint that ranks docs from SQLite by embeddings (or text fallback), then enriches with graph context from Neo4j.
