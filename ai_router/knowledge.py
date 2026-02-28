import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from .database import db_manager

logger = logging.getLogger("ai_router.knowledge")


class KnowledgeGraph:
    """
    Service for managing semantic relationships (triples) between entities.
    Backed by SQLite 'triples' table.
    """

    async def start(self):
        await db_manager.connect()
        logger.info("KnowledgeGraph started.")

    async def stop(self):
        # Database connection is managed by main.py / memory service usually,
        # but we can close it if this is standalone.
        # For shared usage, we might rely on the shared db_manager.
        pass

    async def add_triple(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
        source: str = "system",
    ):
        """Add a semantic relationship."""
        try:
            query = """
                INSERT OR REPLACE INTO triples (subject, predicate, object, confidence, source, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            await db_manager.execute_query(
                query,
                (
                    subject,
                    predicate,
                    object_,
                    confidence,
                    source,
                    datetime.utcnow().isoformat(),
                ),
            )
            logger.debug(f"Added triple: ({subject}) -[{predicate}]-> ({object_})")
        except Exception as e:
            logger.error(f"Failed to add triple: {e}")

    async def get_relations(self, subject: str) -> List[Dict[str, Any]]:
        """Get all outgoing relationships for a subject."""
        try:
            query = "SELECT * FROM triples WHERE subject = ?"
            rows = await db_manager.fetch_all(query, (subject,))
            return rows
        except Exception as e:
            # Fallback if fetch_all isn't implemented in db_manager yet (it likely isn't)
            # We should probably update db_manager to support fetching multiple rows
            logger.error(f"Failed to get relations using db_manager: {e}")
            return []

    async def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object_: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Flexible query for triples."""
        try:
            clauses = []
            params = []
            if subject:
                clauses.append("subject = ?")
                params.append(subject)
            if predicate:
                clauses.append("predicate = ?")
                params.append(predicate)
            if object_:
                clauses.append("object = ?")
                params.append(object_)

            where_clause = " AND ".join(clauses) if clauses else "1=1"
            query = f"SELECT * FROM triples WHERE {where_clause}"

            # NOTE: We need to implement fetch_all in DatabaseManager
            rows = await db_manager.fetch_all(query, tuple(params))
            return rows
        except Exception as e:
            logger.error(f"Failed to query triples: {e}")
            return []


# Singleton
knowledge_graph = KnowledgeGraph()
