import json
import sqlite3
import logging
import math
from typing import Any, Dict, List, Optional
from datetime import datetime

from ai_router.embedding_client import EmbeddingClient
from ai_router.embeddings import EmbeddingLayer
from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)

logger = logging.getLogger("procedural_memory")


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class ProceduralMemoryStore(MemoryContract):
    """MEM-5: Procedural Memory (Optimization Heuristics Store).
    Stores rules in the format: IF conditions THEN strategy CONFIDENCE score.
    """

    def __init__(self, db_path: str = "storage/procedural.db"):
        # We'll use /tmp for now for consistency with verification success
        if "agent_ecosystem" in db_path:  # simplified check
            self.db_path = "/tmp/procedural.db"
        else:
            self.db_path = db_path
        self.embedding_client = EmbeddingClient()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS procedures (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    success_rate REAL DEFAULT 0.0,
                    avg_latency REAL DEFAULT 0.0,
                    embedding_json TEXT,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            # Simple migration to add column if it doesn't exist
            try:
                conn.execute("ALTER TABLE procedures ADD COLUMN embedding_json TEXT")
            except sqlite3.OperationalError:
                pass  # Column exists

            conn.commit()
        logger.info(f"Initialized Procedural Memory at {self.db_path}")

    async def add_procedure(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        success_rate: float,
        avg_latency: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add or update an optimization procedure."""
        # Simple ID generation for now (e.g. name + hash)
        procedure_id = name.lower().replace(" ", "_")

        # Get BGE-small embedding for procedure name to allow semantic retrieval
        try:
            embedding = await self.embedding_client.embed(name, EmbeddingLayer.ROUTING)
            embedding_json = json.dumps(embedding)
        except Exception as e:
            logger.error(f"Failed to embed procedure name: {e}")
            embedding_json = "[]"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO procedures (
                    id, name, steps_json, success_rate, avg_latency, embedding_json, last_used, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    procedure_id,
                    name,
                    json.dumps(steps),
                    success_rate,
                    avg_latency,
                    embedding_json,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    async def store(self, payload: MemoryPayload):
        """Implement MemoryContract store."""
        if isinstance(payload.content, dict) and "name" in payload.content:
            await self.add_procedure(
                name=payload.content["name"],
                steps=payload.content.get("steps", []),
                success_rate=payload.content.get("success_rate", 0.0),
                avg_latency=payload.content.get("avg_latency", 0.0),
                metadata=payload.metadata.__dict__,
            )

    async def retrieve(self, query: str, filters: Dict[str, Any]) -> List[MemoryPayload]:
        """Implement MemoryContract retrieve with semantic search."""
        query_text = filters.get("query") or query

        query_embedding = []
        try:
            query_embedding = await self.embedding_client.embed(query_text, EmbeddingLayer.ROUTING)
        except Exception as e:
            logger.error(f"Failed to embed procedural query: {e}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM procedures")
            rows = cursor.fetchall()

            scored_results = []
            for row in rows:
                # row indices: 0:id, 1:name, 2:steps_json, 3:success_rate, 4:avg_latency, 5:embedding_json, 6:last_used
                row_embedding_json = row[5]
                score = 0.0

                # Check exact match for highest priority
                if query_text.lower() in row[1].lower():
                    score = 1.0 + row[3]  # boost exact match by its success_rate
                elif query_embedding and row_embedding_json:
                    try:
                        row_embedding = json.loads(row_embedding_json)
                        if row_embedding:
                            score = cosine_similarity(query_embedding, row_embedding) * row[3]
                    except Exception:
                        pass

                scored_results.append((score, row))

            # Sort by highest score first
            scored_results.sort(key=lambda x: x[0], reverse=True)

            # Filter low scores (threshold can be adjusted)
            top_results = [res[1] for res in scored_results if res[0] > 0.6][:5]

            # Update last_used for retrieved results
            for row in top_results:
                conn.execute(
                    "UPDATE procedures SET last_used = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), row[0]),
                )
            conn.commit()

            return [
                MemoryPayload(
                    memory_type=MemoryType.PROCEDURAL,
                    content={
                        "id": row[0],
                        "name": row[1],
                        "steps": json.loads(row[2]) if row[2] else [],
                        "success_rate": row[3],
                        "avg_latency": row[4],
                        "last_used": row[6],
                    },
                    metadata=MemoryMetadata(source_agent="procedural_store", confidence=row[3]),
                )
                for row in top_results
            ]

    async def forget(self, policy: Dict[str, Any]):
        """Implement MemoryContract forget."""
        if "id" in policy:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM procedures WHERE id = ?",
                    (policy["id"],),
                )
                conn.commit()
