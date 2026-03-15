"""
Research & Learning Knowledge Graph - Neo4j/RDFStore backed memory.

Tracks insights, skill acquisition, and systemic learning loops.
Separated from the OperationalKG per the Polyglot Architecture.

Schema:
    Outcome -[:GENERATED]-> Insight
    Insight -[:IMPROVES]-> Skill
    Insight -[:RELATED_TO]-> Insight
"""

import os
import uuid
import logging
from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase

from core.knowledge_quality.intake_gate import (
    IntakeGate,
    NodeProposal,
    EdgeProposal,
    Provenance,
    ProposalVerdict,
)

logger = logging.getLogger("raphael.memory.research_kg")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "postgres")
NEO4J_DATABASE = "research"


class ResearchKG:
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None,
        gate: IntakeGate = None,
    ):
        self.driver = AsyncGraphDatabase.driver(
            uri or NEO4J_URI,
            auth=(user or NEO4J_USER, password or NEO4J_PASSWORD),
        )
        self.database = database or NEO4J_DATABASE
        self._gate = gate

    async def close(self):
        await self.driver.close()

    def _session(self):
        return self.driver.session(database=self.database)

    async def ensure_schema(self):
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Insight) REQUIRE i.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sk:Skill) REQUIRE sk.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Outcome) REQUIRE o.id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (i:Insight) ON (i.confidence)",
            "CREATE INDEX IF NOT EXISTS FOR (i:Insight) ON (i.discovered_at)",
        ]

        async with self._session() as s:
            for c in constraints:
                await s.run(c)
            for idx in indexes:
                await s.run(idx)
        logger.info("ResearchKG schema ensured.")

    async def record_insight(
        self,
        content: str,
        confidence: float = 0.8,
        source: str = "observation",
        outcome_id: str = None,
        related_skill: str = None,
        tags: List[str] = None,
    ) -> str:
        insight_id = str(uuid.uuid4())[:8]
        res_prov = Provenance(source=source, confidence=confidence)

        if self._gate:
            await self._gate.asubmit_node(NodeProposal(
                label="Insight",
                match_keys={"id": insight_id},
                properties={
                    "content": content,
                    "tags": tags or [],
                },
                provenance=res_prov,
                submitted_by="ResearchKG",
            ))
            if outcome_id:
                await self._gate.asubmit_edge(EdgeProposal(
                    from_label="Outcome",
                    from_keys={"id": outcome_id},
                    rel_type="GENERATED",
                    to_label="Insight",
                    to_keys={"id": insight_id},
                    provenance=res_prov,
                    submitted_by="ResearchKG",
                ))
            if related_skill:
                # Skill creation goes through the gate — dictionary check applies
                result = await self._gate.asubmit_node(NodeProposal(
                    label="Skill",
                    match_keys={"name": related_skill},
                    properties={"proficiency": 0.0, "practice_count": 0},
                    provenance=res_prov,
                    submitted_by="ResearchKG",
                ))
                if result.verdict != ProposalVerdict.REJECTED:
                    await self._gate.asubmit_edge(EdgeProposal(
                        from_label="Insight",
                        from_keys={"id": insight_id},
                        rel_type="IMPROVES",
                        to_label="Skill",
                        to_keys={"name": related_skill},
                        provenance=res_prov,
                        submitted_by="ResearchKG",
                    ))
                else:
                    logger.warning(
                        "Skill '%s' rejected by gate: %s", related_skill, result.reason
                    )
        else:
            async with self._session() as s:
                await s.run(
                    """
                    CREATE (i:Insight {
                        id: $id,
                        content: $content,
                        confidence: $confidence,
                        source: $source,
                        discovered_at: datetime(),
                        tags: $tags
                    })
                    """,
                    id=insight_id,
                    content=content,
                    confidence=confidence,
                    source=source,
                    tags=tags or [],
                )
                if outcome_id:
                    await s.run(
                        """
                        MERGE (o:Outcome {id: $oid})
                        WITH o
                        MATCH (i:Insight {id: $iid})
                        MERGE (o)-[:GENERATED]->(i)
                        """,
                        oid=outcome_id,
                        iid=insight_id,
                    )
                if related_skill:
                    await s.run(
                        """
                        MATCH (i:Insight {id: $iid})
                        MERGE (sk:Skill {name: $skill})
                        ON CREATE SET sk.proficiency = 0.0,
                                      sk.practice_count = 0
                        MERGE (i)-[:IMPROVES]->(sk)
                        """,
                        iid=insight_id,
                        skill=related_skill,
                    )

        logger.info("Recorded insight %s: %s", insight_id, content[:60])
        return insight_id

    async def update_skill(self, name: str, proficiency_delta: float = 0.1):
        if self._gate:
            result = await self._gate.asubmit_node(NodeProposal(
                label="Skill",
                match_keys={"name": name},
                properties={"proficiency_delta": proficiency_delta},
                provenance=Provenance(source="research_kg", confidence=0.85),
                submitted_by="ResearchKG",
            ))
            if result.verdict == ProposalVerdict.REJECTED:
                logger.warning("Skill '%s' rejected by gate: %s", name, result.reason)
                return
            # Still need to do the increment via raw Cypher (gate does MERGE, not increment)
            async with self._session() as s:
                await s.run(
                    """
                    MATCH (sk:Skill {name: $name})
                    SET sk.proficiency = coalesce(sk.proficiency, 0) + $delta,
                        sk.practice_count = coalesce(sk.practice_count, 0) + 1,
                        sk.last_practiced = datetime()
                    """,
                    name=name,
                    delta=proficiency_delta,
                )
        else:
            async with self._session() as s:
                await s.run(
                    """
                    MERGE (sk:Skill {name: $name})
                    ON CREATE SET sk.proficiency = $delta,
                                  sk.practice_count = 1,
                                  sk.last_practiced = datetime()
                    ON MATCH SET sk.proficiency = sk.proficiency + $delta,
                                 sk.practice_count = sk.practice_count + 1,
                                 sk.last_practiced = datetime()
                    """,
                    name=name,
                    delta=proficiency_delta,
                )
        logger.debug("Updated skill %s (+%.2f)", name, proficiency_delta)


# Singleton
research_kg = ResearchKG()
