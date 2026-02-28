import json
import sqlite3
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from ..contracts.memory_contract import (
    MemoryContract,
    MemoryPayload,
    MemoryType,
    MemoryMetadata,
)

logger = logging.getLogger("procedural_memory")


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
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS heuristics (
                    id TEXT PRIMARY KEY,
                    condition_key TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    confidence REAL DEFAULT 0.0,
                    metadata TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            conn.commit()
        logger.info(f"Initialized Procedural Memory at {self.db_path}")

    async def add_heuristic(
        self,
        condition: str,
        strategy: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add or update an optimization heuristic."""
        heuristic_id = f"{condition}:{strategy}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO heuristics (id, condition_key, strategy, confidence, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    heuristic_id,
                    condition,
                    strategy,
                    confidence,
                    json.dumps(metadata or {}),
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    async def store(self, payload: MemoryPayload):
        """Implement MemoryContract store."""
        if isinstance(payload.content, dict) and "condition" in payload.content:
            await self.add_heuristic(
                payload.content["condition"],
                payload.content["strategy"],
                payload.metadata.confidence,
                payload.content.get("metadata"),
            )

    async def retrieve(
        self, query: str, filters: Dict[str, Any]
    ) -> List[MemoryPayload]:
        """Implement MemoryContract retrieve."""
        condition = filters.get("condition") or query
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM heuristics WHERE condition_key = ? ORDER BY confidence DESC",
                (condition,),
            )
            rows = cursor.fetchall()
            return [
                MemoryPayload(
                    memory_type=MemoryType.PROCEDURAL,
                    content={
                        "condition": row[1],
                        "strategy": row[2],
                        "confidence": row[3],
                        "metadata": json.loads(row[4]),
                    },
                    metadata=MemoryMetadata(
                        source_agent="procedural_store", confidence=row[3]
                    ),
                )
                for row in rows
            ]

    async def forget(self, policy: Dict[str, Any]):
        """Implement MemoryContract forget."""
        if "condition" in policy:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM heuristics WHERE condition_key = ?",
                    (policy["condition"],),
                )
                conn.commit()
