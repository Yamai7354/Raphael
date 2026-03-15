"""
Memory Graph — Neo4j-backed long-term memory for agent work tracking.

Targets the 'memory' database in Neo4j. Tracks sessions, tasks, outcomes,
insights, and skills to enable a research/self-improvement loop.

Schema:
    Session -[:CONTAINS]-> Task
    Task -[:USED_MODEL]-> ModelRef
    Task -[:USED_TOOL]-> ToolRef
    Task -[:PRODUCED]-> Outcome
    Task -[:CATEGORIZED_AS]-> TaskType
    Outcome -[:GENERATED]-> Insight
    Insight -[:IMPROVES]-> Skill
    Session -[:NEXT]-> Session
    Task -[:DEPENDS_ON]-> Task
    Insight -[:RELATED_TO]-> Insight
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

from core.knowledge_quality.intake_gate import (
    IntakeGate,
    NodeProposal,
    EdgeProposal,
    Provenance,
    ProposalVerdict,
)

logger = logging.getLogger("ai_router.memory_graph")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = "memory"


class MemoryGraph:
    """
    Graph-based long-term memory for tracking agent work,
    learning outcomes, and self-improvement patterns.

    Complements:
      - WorkingMemory (Redis) — ephemeral scratchpads
      - EpisodicMemory (SQLite) — flat task/event logs
    """

    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None,
        gate: IntakeGate = None,
    ):
        self.driver = GraphDatabase.driver(
            uri or NEO4J_URI,
            auth=(user or NEO4J_USER, password or NEO4J_PASSWORD),
        )
        self.database = database or NEO4J_DATABASE
        self._gate = gate

    def close(self):
        self.driver.close()

    def _session(self):
        return self.driver.session(database=self.database)

    # ──────────────────────────────────────────────
    # Schema Bootstrap
    # ──────────────────────────────────────────────

    def ensure_schema(self):
        """Create constraints and indexes for the memory graph."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Task) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Outcome) REQUIRE o.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Insight) REQUIRE i.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sk:Skill) REQUIRE sk.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:ModelRef) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (tl:ToolRef) REQUIRE tl.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (tt:TaskType) REQUIRE tt.name IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (t:Task) ON (t.status)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Task) ON (t.started_at)",
            "CREATE INDEX IF NOT EXISTS FOR (i:Insight) ON (i.confidence)",
            "CREATE INDEX IF NOT EXISTS FOR (i:Insight) ON (i.discovered_at)",
            "CREATE INDEX IF NOT EXISTS FOR (s:Session) ON (s.started_at)",
        ]
        with self._session() as s:
            for c in constraints:
                s.run(c)
            for idx in indexes:
                s.run(idx)
        logger.info("Memory graph schema ensured (8 constraints, 5 indexes).")

    # ──────────────────────────────────────────────
    # Session Management
    # ──────────────────────────────────────────────

    def start_session(
        self,
        agent: str = "system",
        summary: str = "",
    ) -> str:
        """Start a new work session. Returns session ID."""
        session_id = str(uuid.uuid4())[:8]
        with self._session() as s:
            # Create session node
            s.run(
                """
                CREATE (s:Session {
                    id: $id,
                    agent: $agent,
                    summary: $summary,
                    started_at: datetime(),
                    status: 'active'
                })
                """,
                id=session_id,
                agent=agent,
                summary=summary,
            )
            # Link to previous session
            s.run(
                """
                MATCH (prev:Session)
                WHERE prev.id <> $id
                WITH prev ORDER BY prev.started_at DESC LIMIT 1
                MATCH (curr:Session {id: $id})
                MERGE (prev)-[:NEXT]->(curr)
                """,
                id=session_id,
            )
        logger.info("Started session %s (agent=%s)", session_id, agent)
        return session_id

    def end_session(
        self,
        session_id: str,
        summary: str = None,
    ) -> Dict[str, Any]:
        """End a session and return its stats."""
        with self._session() as s:
            # Update session
            s.run(
                """
                MATCH (s:Session {id: $id})
                SET s.ended_at = datetime(),
                    s.status = 'completed',
                    s.summary = CASE WHEN $summary IS NOT NULL
                                     THEN $summary ELSE s.summary END
                """,
                id=session_id,
                summary=summary,
            )
            # Get stats
            result = s.run(
                """
                MATCH (s:Session {id: $id})
                OPTIONAL MATCH (s)-[:CONTAINS]->(t:Task)
                OPTIONAL MATCH (t)-[:PRODUCED]->(o:Outcome)
                OPTIONAL MATCH (o)-[:GENERATED]->(i:Insight)
                RETURN s.started_at AS started,
                       s.ended_at AS ended,
                       count(DISTINCT t) AS tasks,
                       count(DISTINCT o) AS outcomes,
                       count(DISTINCT i) AS insights
                """,
                id=session_id,
            )
            rec = result.single()
            stats = {
                "session_id": session_id,
                "tasks": rec["tasks"],
                "outcomes": rec["outcomes"],
                "insights": rec["insights"],
            }
        logger.info("Ended session %s: %s", session_id, stats)
        return stats

    # ──────────────────────────────────────────────
    # Task Recording
    # ──────────────────────────────────────────────

    def record_task(
        self,
        session_id: str,
        title: str,
        status: str = "completed",
        priority: str = "medium",
        model: str = None,
        tools: List[str] = None,
        task_type: str = None,
        duration_ms: int = None,
        success: bool = True,
        error: str = None,
        metadata: Dict = None,
    ) -> str:
        """Record a task within a session. Returns task ID."""
        task_id = str(uuid.uuid4())[:8]
        tools = tools or []
        mem_prov = Provenance(source="memory_graph", confidence=0.9)

        if self._gate:
            self._gate.submit_node(NodeProposal(
                label="Task",
                match_keys={"id": task_id},
                properties={
                    "title": title, "status": status, "priority": priority,
                    "duration_ms": duration_ms, "success": success,
                    "error": error,
                    "metadata": json.dumps(metadata) if metadata else None,
                },
                provenance=mem_prov,
                submitted_by="MemoryGraph",
            ))
            self._gate.submit_edge(EdgeProposal(
                from_label="Session", from_keys={"id": session_id},
                rel_type="CONTAINS",
                to_label="Task", to_keys={"id": task_id},
                provenance=mem_prov, submitted_by="MemoryGraph",
            ))
            if model:
                self._gate.submit_node(NodeProposal(
                    label="ModelRef", match_keys={"name": model},
                    provenance=mem_prov, submitted_by="MemoryGraph",
                ))
                self._gate.submit_edge(EdgeProposal(
                    from_label="Task", from_keys={"id": task_id},
                    rel_type="USED_MODEL",
                    to_label="ModelRef", to_keys={"name": model},
                    provenance=mem_prov, submitted_by="MemoryGraph",
                ))
            for tool_name in tools:
                self._gate.submit_node(NodeProposal(
                    label="ToolRef", match_keys={"name": tool_name},
                    provenance=mem_prov, submitted_by="MemoryGraph",
                ))
                self._gate.submit_edge(EdgeProposal(
                    from_label="Task", from_keys={"id": task_id},
                    rel_type="USED_TOOL",
                    to_label="ToolRef", to_keys={"name": tool_name},
                    provenance=mem_prov, submitted_by="MemoryGraph",
                ))
            if task_type:
                self._gate.submit_node(NodeProposal(
                    label="TaskType", match_keys={"name": task_type},
                    provenance=mem_prov, submitted_by="MemoryGraph",
                ))
                self._gate.submit_edge(EdgeProposal(
                    from_label="Task", from_keys={"id": task_id},
                    rel_type="CATEGORIZED_AS",
                    to_label="TaskType", to_keys={"name": task_type},
                    provenance=mem_prov, submitted_by="MemoryGraph",
                ))
        else:
            with self._session() as s:
                s.run(
                    """
                    MATCH (sess:Session {id: $session_id})
                    CREATE (t:Task {
                        id: $id,
                        title: $title,
                        status: $status,
                        priority: $priority,
                        started_at: datetime(),
                        completed_at: CASE WHEN $status = 'completed'
                                           THEN datetime() ELSE null END,
                        duration_ms: $duration_ms,
                        success: $success,
                        error: $error,
                        metadata: $metadata
                    })
                    MERGE (sess)-[:CONTAINS]->(t)
                    """,
                    session_id=session_id, id=task_id, title=title,
                    status=status, priority=priority, duration_ms=duration_ms,
                    success=success, error=error,
                    metadata=json.dumps(metadata) if metadata else None,
                )
                if model:
                    s.run("""
                    MATCH (t:Task {id: $task_id})
                    MERGE (m:ModelRef {name: $model})
                    MERGE (t)-[:USED_MODEL]->(m)
                    """, task_id=task_id, model=model)
                for tool_name in tools:
                    s.run("""
                    MATCH (t:Task {id: $task_id})
                    MERGE (tl:ToolRef {name: $tool})
                    MERGE (t)-[:USED_TOOL]->(tl)
                    """, task_id=task_id, tool=tool_name)
                if task_type:
                    s.run("""
                    MATCH (t:Task {id: $task_id})
                    MERGE (tt:TaskType {name: $type})
                    MERGE (t)-[:CATEGORIZED_AS]->(tt)
                    """, task_id=task_id, type=task_type)

        logger.info("Recorded task %s: %s (model=%s)", task_id, title, model)
        return task_id

    def record_outcome(
        self,
        task_id: str,
        result_type: str = "success",
        quality_score: float = None,
        tokens_used: int = None,
        latency_ms: int = None,
        summary: str = None,
    ) -> str:
        """Record the outcome of a task. Returns outcome ID."""
        outcome_id = str(uuid.uuid4())[:8]
        mem_prov = Provenance(source="memory_graph", confidence=0.9)

        if self._gate:
            self._gate.submit_node(NodeProposal(
                label="Outcome",
                match_keys={"id": outcome_id},
                properties={
                    "result_type": result_type,
                    "quality_score": quality_score,
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "summary": summary,
                },
                provenance=mem_prov,
                submitted_by="MemoryGraph",
            ))
            self._gate.submit_edge(EdgeProposal(
                from_label="Task", from_keys={"id": task_id},
                rel_type="PRODUCED",
                to_label="Outcome", to_keys={"id": outcome_id},
                provenance=mem_prov, submitted_by="MemoryGraph",
            ))
        else:
            with self._session() as s:
                s.run(
                    """
                    MATCH (t:Task {id: $task_id})
                    CREATE (o:Outcome {
                        id: $id,
                        result_type: $result_type,
                        quality_score: $quality_score,
                        tokens_used: $tokens_used,
                        latency_ms: $latency_ms,
                        summary: $summary,
                        recorded_at: datetime()
                    })
                    MERGE (t)-[:PRODUCED]->(o)
                    """,
                    task_id=task_id, id=outcome_id,
                    result_type=result_type, quality_score=quality_score,
                    tokens_used=tokens_used, latency_ms=latency_ms,
                    summary=summary,
                )
        return outcome_id

    # ──────────────────────────────────────────────
    # Insights & Learning
    # ──────────────────────────────────────────────

    def record_insight(
        self,
        content: str,
        confidence: float = 0.8,
        source: str = "observation",
        outcome_id: str = None,
        related_skill: str = None,
        tags: List[str] = None,
    ) -> str:
        """Record a learned insight. Optionally link to an outcome and skill."""
        insight_id = str(uuid.uuid4())[:8]
        ins_prov = Provenance(source=source, confidence=confidence)

        if self._gate:
            self._gate.submit_node(NodeProposal(
                label="Insight",
                match_keys={"id": insight_id},
                properties={"content": content, "tags": tags or []},
                provenance=ins_prov,
                submitted_by="MemoryGraph",
            ))
            if outcome_id:
                self._gate.submit_edge(EdgeProposal(
                    from_label="Outcome", from_keys={"id": outcome_id},
                    rel_type="GENERATED",
                    to_label="Insight", to_keys={"id": insight_id},
                    provenance=ins_prov, submitted_by="MemoryGraph",
                ))
            if related_skill:
                result = self._gate.submit_node(NodeProposal(
                    label="Skill",
                    match_keys={"name": related_skill},
                    properties={"proficiency": 0.0, "practice_count": 0},
                    provenance=ins_prov,
                    submitted_by="MemoryGraph",
                ))
                if result.verdict != ProposalVerdict.REJECTED:
                    self._gate.submit_edge(EdgeProposal(
                        from_label="Insight", from_keys={"id": insight_id},
                        rel_type="IMPROVES",
                        to_label="Skill", to_keys={"name": related_skill},
                        provenance=ins_prov, submitted_by="MemoryGraph",
                    ))
                else:
                    logger.warning("Skill '%s' rejected by gate: %s", related_skill, result.reason)
        else:
            with self._session() as s:
                s.run("""
                CREATE (i:Insight {
                    id: $id, content: $content, confidence: $confidence,
                    source: $source, discovered_at: datetime(), tags: $tags
                })
                """, id=insight_id, content=content, confidence=confidence,
                    source=source, tags=tags or [])
                if outcome_id:
                    s.run("""
                    MATCH (o:Outcome {id: $oid})
                    MATCH (i:Insight {id: $iid})
                    MERGE (o)-[:GENERATED]->(i)
                    """, oid=outcome_id, iid=insight_id)
                if related_skill:
                    s.run("""
                    MATCH (i:Insight {id: $iid})
                    MERGE (sk:Skill {name: $skill})
                    ON CREATE SET sk.proficiency = 0.0, sk.practice_count = 0
                    MERGE (i)-[:IMPROVES]->(sk)
                    """, iid=insight_id, skill=related_skill)

        logger.info("Recorded insight %s: %s", insight_id, content[:60])
        return insight_id

    def update_skill(self, name: str, proficiency_delta: float = 0.1):
        """Increment a skill's proficiency and practice count."""
        if self._gate:
            result = self._gate.submit_node(NodeProposal(
                label="Skill",
                match_keys={"name": name},
                provenance=Provenance(source="memory_graph", confidence=0.85),
                submitted_by="MemoryGraph",
            ))
            if result.verdict == ProposalVerdict.REJECTED:
                logger.warning("Skill '%s' rejected by gate: %s", name, result.reason)
                return
            # Gate ensures the node exists with provenance; do the increment via raw Cypher
            with self._session() as s:
                s.run("""
                MATCH (sk:Skill {name: $name})
                SET sk.proficiency = coalesce(sk.proficiency, 0) + $delta,
                    sk.practice_count = coalesce(sk.practice_count, 0) + 1,
                    sk.last_practiced = datetime()
                """, name=name, delta=proficiency_delta)
        else:
            with self._session() as s:
                s.run("""
                MERGE (sk:Skill {name: $name})
                ON CREATE SET sk.proficiency = $delta,
                              sk.practice_count = 1,
                              sk.last_practiced = datetime()
                ON MATCH SET sk.proficiency = sk.proficiency + $delta,
                             sk.practice_count = sk.practice_count + 1,
                             sk.last_practiced = datetime()
                """, name=name, delta=proficiency_delta)
        logger.debug("Updated skill %s (+%.2f)", name, proficiency_delta)

    # ──────────────────────────────────────────────
    # Query & Analysis
    # ──────────────────────────────────────────────

    def get_session_history(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions with task counts."""
        with self._session() as s:
            result = s.run(
                """
                MATCH (s:Session)
                OPTIONAL MATCH (s)-[:CONTAINS]->(t:Task)
                WITH s, count(t) AS task_count,
                     sum(CASE WHEN t.success THEN 1 ELSE 0 END) AS successes
                RETURN s.id AS id,
                       s.agent AS agent,
                       s.summary AS summary,
                       s.started_at AS started,
                       s.ended_at AS ended,
                       s.status AS status,
                       task_count,
                       successes
                ORDER BY s.started_at DESC
                LIMIT $limit
                """,
                limit=limit,
            )
            return [dict(r) for r in result]

    def get_skill_report(self) -> List[Dict]:
        """Get proficiency report for all skills."""
        with self._session() as s:
            result = s.run(
                """
                MATCH (sk:Skill)
                OPTIONAL MATCH (i:Insight)-[:IMPROVES]->(sk)
                RETURN sk.name AS skill,
                       sk.proficiency AS proficiency,
                       sk.practice_count AS practices,
                       sk.last_practiced AS last_practiced,
                       count(i) AS insight_count
                ORDER BY sk.proficiency DESC
                """
            )
            return [dict(r) for r in result]

    def get_insights(
        self,
        min_confidence: float = 0.0,
        limit: int = 20,
        tag: str = None,
    ) -> List[Dict]:
        """Query insights, optionally filtered by confidence and tag."""
        with self._session() as s:
            if tag:
                result = s.run(
                    """
                    MATCH (i:Insight)
                    WHERE i.confidence >= $min_conf AND $tag IN i.tags
                    RETURN i.id AS id, i.content AS content,
                           i.confidence AS confidence, i.source AS source,
                           i.discovered_at AS discovered_at, i.tags AS tags
                    ORDER BY i.confidence DESC
                    LIMIT $limit
                    """,
                    min_conf=min_confidence,
                    tag=tag,
                    limit=limit,
                )
            else:
                result = s.run(
                    """
                    MATCH (i:Insight)
                    WHERE i.confidence >= $min_conf
                    RETURN i.id AS id, i.content AS content,
                           i.confidence AS confidence, i.source AS source,
                           i.discovered_at AS discovered_at, i.tags AS tags
                    ORDER BY i.confidence DESC
                    LIMIT $limit
                    """,
                    min_conf=min_confidence,
                    limit=limit,
                )
            return [dict(r) for r in result]

    def get_model_usage_stats(self) -> List[Dict]:
        """Get usage statistics for each model."""
        with self._session() as s:
            result = s.run(
                """
                MATCH (t:Task)-[:USED_MODEL]->(m:ModelRef)
                OPTIONAL MATCH (t)-[:PRODUCED]->(o:Outcome)
                RETURN m.name AS model,
                       count(DISTINCT t) AS task_count,
                       sum(CASE WHEN t.success THEN 1 ELSE 0 END) AS successes,
                       avg(o.quality_score) AS avg_quality,
                       avg(o.latency_ms) AS avg_latency,
                       sum(o.tokens_used) AS total_tokens
                ORDER BY task_count DESC
                """
            )
            return [dict(r) for r in result]

    def get_improvement_suggestions(self) -> List[Dict]:
        """Analyze task patterns and suggest improvements."""
        suggestions = []
        with self._session() as s:
            # 1. Models with low success rates
            result = s.run(
                """
                MATCH (t:Task)-[:USED_MODEL]->(m:ModelRef)
                WITH m.name AS model,
                     count(t) AS total,
                     sum(CASE WHEN t.success THEN 1 ELSE 0 END) AS ok
                WHERE total >= 3
                WITH model, total, ok,
                     toFloat(ok) / total AS rate
                WHERE rate < 0.7
                RETURN model, total, ok, rate
                ORDER BY rate ASC
                """
            )
            for r in result:
                suggestions.append(
                    {
                        "type": "low_success_model",
                        "priority": "high",
                        "message": (
                            f"Model '{r['model']}' has {r['rate']:.0%} success rate "
                            f"({r['ok']}/{r['total']}). Consider routing these "
                            f"tasks to a different model."
                        ),
                    }
                )

            # 2. Skills with low proficiency
            result = s.run(
                """
                MATCH (sk:Skill)
                WHERE sk.proficiency < 0.3 AND sk.practice_count >= 2
                RETURN sk.name AS skill, sk.proficiency AS prof,
                       sk.practice_count AS practices
                ORDER BY sk.proficiency ASC
                """
            )
            for r in result:
                suggestions.append(
                    {
                        "type": "weak_skill",
                        "priority": "medium",
                        "message": (
                            f"Skill '{r['skill']}' has low proficiency "
                            f"({r['prof']:.2f}) after {r['practices']} practices. "
                            f"Focus more training on this area."
                        ),
                    }
                )

            # 3. Task types with no recent activity
            result = s.run(
                """
                MATCH (tt:TaskType)
                OPTIONAL MATCH (t:Task)-[:CATEGORIZED_AS]->(tt)
                WITH tt.name AS task_type, count(t) AS total,
                     max(t.started_at) AS last_seen
                WHERE total = 0
                   OR (last_seen IS NOT NULL
                       AND duration.between(last_seen, datetime()).days > 7)
                RETURN task_type, total, last_seen
                """
            )
            for r in result:
                suggestions.append(
                    {
                        "type": "neglected_area",
                        "priority": "low",
                        "message": (
                            f"Task type '{r['task_type']}' has had no activity "
                            f"recently. Consider scheduling practice tasks."
                        ),
                    }
                )

            # 4. High-confidence insights not yet applied
            result = s.run(
                """
                MATCH (i:Insight)
                WHERE i.confidence >= 0.9
                  AND NOT (i)-[:IMPROVES]->(:Skill)
                RETURN i.content AS content, i.confidence AS confidence
                LIMIT 5
                """
            )
            for r in result:
                suggestions.append(
                    {
                        "type": "unapplied_insight",
                        "priority": "medium",
                        "message": (
                            f"High-confidence insight not linked to any skill: "
                            f"'{r['content'][:80]}'"
                        ),
                    }
                )

        return suggestions

    # ──────────────────────────────────────────────
    # Graph Stats
    # ──────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get overall memory graph statistics."""
        with self._session() as s:
            result = s.run(
                """
                MATCH (n)
                WITH labels(n)[0] AS label, count(n) AS cnt
                RETURN label, cnt ORDER BY cnt DESC
                """
            )
            nodes = {r["label"]: r["cnt"] for r in result}

            result = s.run(
                """
                MATCH ()-[r]->()
                WITH type(r) AS rtype, count(r) AS cnt
                RETURN rtype, cnt ORDER BY cnt DESC
                """
            )
            rels = {r["rtype"]: r["cnt"] for r in result}

        return {
            "database": self.database,
            "node_counts": nodes,
            "relationship_counts": rels,
            "total_nodes": sum(nodes.values()) if nodes else 0,
            "total_relationships": sum(rels.values()) if rels else 0,
        }


# Singleton
memory_graph = MemoryGraph()
