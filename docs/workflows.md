# Automation Workflows

Three automated workflows the swarm can run. Each follows the task flow: Planner → Router → Worker(s) → Evaluator → Memory.

---

## Workflow 1 — Coding Task

**Task:** Build feature

| Step | Agent / Component | Action |
|------|-------------------|--------|
| 1 | Planner | Creates subtasks (design, implement, test) |
| 2 | Router | Assigns coder (and optionally auditor) |
| 3 | Coder | Writes code |
| 4 | Evaluator | Tests it (run tests, lint) |
| 5 | Graph agent | Records solution in knowledge graph |

---

## Workflow 2 — Research Pipeline

**Task:** Learn new concept

| Step | Agent / Component | Action |
|------|-------------------|--------|
| 1 | Research agent | Gathers info (search, docs) |
| 2 | Summarizer | Compresses knowledge |
| 3 | Graph agent | Stores concepts (Neo4j + embeddings) |
| 4 | Evaluator | Checks usefulness (quality score) |

---

## Workflow 3 — System Optimization

**Task:** Improve swarm performance

| Step | Agent / Component | Action |
|------|-------------------|--------|
| 1 | Metrics agent | Checks logs and metrics |
| 2 | Planner | Suggests improvements (e.g. routing, TTL) |
| 3 | Coder | Updates system (config, code) |
| 4 | Evaluator | Validates change (regression, health) |

---

These workflows are implemented as orchestration scripts or event-driven flows that emit the right sequence of tasks through the task flow engine.
