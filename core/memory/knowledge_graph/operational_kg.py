"""
Operational Knowledge Graph - Neo4j backed memory.

Tracks live operational state, tasks, tool usage, and session links.
Separated from ResearchKG per Polyglot Architecture.

Schema:
    Session -[:CONTAINS]-> Task
    Task -[:USED_MODEL]-> ModelRef
    Task -[:USED_TOOL]-> ToolRef
    Session -[:NEXT]-> Session
    Task -[:DEPENDS_ON]-> Task
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase

logger = logging.getLogger("raphael.memory.operational_kg")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "postgres")
NEO4J_DATABASE = "operational"


class OperationalKG:
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None,
    ):
        self.driver = AsyncGraphDatabase.driver(
            uri or NEO4J_URI,
            auth=(user or NEO4J_USER, password or NEO4J_PASSWORD),
        )
        self.database = database or NEO4J_DATABASE

    async def close(self):
        await self.driver.close()

    def _session(self):
        return self.driver.session(database=self.database)

    async def ensure_schema(self):
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Task) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:ModelRef) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (tl:ToolRef) REQUIRE tl.name IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (t:Task) ON (t.status)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Task) ON (t.started_at)",
            "CREATE INDEX IF NOT EXISTS FOR (s:Session) ON (s.started_at)",
        ]

        async with self._session() as s:
            for c in constraints:
                await s.run(c)
            for idx in indexes:
                await s.run(idx)
        logger.info("OperationalKG schema ensured.")

    async def start_session(self, agent: str = "system", summary: str = "") -> str:
        session_id = str(uuid.uuid4())[:8]
        async with self._session() as s:
            await s.run(
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
            await s.run(
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

    async def record_task(
        self,
        session_id: str,
        task_id: str,
        title: str,
        status: str = "pending",
        model: str = None,
        tools: List[str] = None,
    ):
        tools = tools or []
        async with self._session() as s:
            await s.run(
                """
                MATCH (sess:Session {id: $session_id})
                CREATE (t:Task {
                    id: $id,
                    title: $title,
                    status: $status,
                    started_at: datetime()
                })
                MERGE (sess)-[:CONTAINS]->(t)
                """,
                session_id=session_id,
                id=str(task_id),
                title=title,
                status=status,
            )

            if model:
                await s.run(
                    """
                    MATCH (t:Task {id: $task_id})
                    MERGE (m:ModelRef {name: $model})
                    MERGE (t)-[:USED_MODEL]->(m)
                    """,
                    task_id=str(task_id),
                    model=model,
                )

            for tool_name in tools:
                await s.run(
                    """
                    MATCH (t:Task {id: $task_id})
                    MERGE (tl:ToolRef {name: $tool})
                    MERGE (t)-[:USED_TOOL]->(tl)
                    """,
                    task_id=str(task_id),
                    tool=tool_name,
                )
        logger.info("Recorded task node %s: %s", task_id, title)


# Singleton
operational_kg = OperationalKG()
