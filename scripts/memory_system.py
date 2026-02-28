#!/usr/bin/env python3
import argparse
import base64
import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "memory_system.db"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

MEMORY_TYPES = {"semantic", "episodic", "procedural", "long_term"}
VALIDATION_STATES = {"unverified", "verified", "conflicted", "retracted"}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_items (
            id TEXT PRIMARY KEY,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            embedding_json TEXT,
            metadata_json TEXT,
            source_agent TEXT,
            confidence REAL DEFAULT 0.5,
            validation_status TEXT DEFAULT 'unverified',
            created_at TEXT NOT NULL,
            supersedes_id TEXT,
            conflict_group TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS retrieval_events (
            id TEXT PRIMARY KEY,
            query TEXT,
            memory_type TEXT,
            top_k INTEGER,
            hit_count INTEGER,
            latency_ms INTEGER,
            selected_ids_json TEXT,
            outcome TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_health_snapshots (
            id TEXT PRIMARY KEY,
            total_items INTEGER,
            by_type_json TEXT,
            by_validation_json TEXT,
            conflict_items INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def infer_memory_type(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("memory_type") or "").strip().lower()
    if explicit in MEMORY_TYPES:
        return explicit

    intent = str(payload.get("intent") or "").strip().lower()
    if any(x in intent for x in ["procedure", "runbook", "how-to", "policy", "playbook"]):
        return "procedural"
    if any(x in intent for x in ["episode", "event", "timeline", "job", "execution", "task"]):
        return "episodic"
    if any(x in intent for x in ["fact", "knowledge", "summary", "research", "insight"]):
        return "semantic"
    return "long_term"


def normalize_validation(value: Any) -> str:
    s = str(value or "unverified").strip().lower()
    return s if s in VALIDATION_STATES else "unverified"


def text_embedding(text: str, dims: int = 64) -> list[float]:
    vec = [0.0] * dims
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        idx = int.from_bytes(digest[:2], "big") % dims
        weight = 1.0 + (digest[2] / 255.0)
        vec[idx] += weight
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _load_json(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def write_graph_pointer(
    item_id: str,
    memory_type: str,
    summary: str,
    source_agent: str,
    metadata: dict[str, Any],
    content: str = "",
) -> bool:
    """Write a research doc pointer to Neo4j.

    Guards against creating empty shell nodes:
    - Requires summary of at least 20 chars
    - Stores actual content on the node (not just title)
    - Only creates Concept nodes for non-empty, meaningful concept names
    """
    if GraphDatabase is None:
        return False

    # Guard: don't create empty shell nodes
    if not summary or len(summary.strip()) < 20:
        return False

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception:
        return False

    concepts = metadata.get("concepts")
    if not isinstance(concepts, list):
        concepts = []
    # Only keep concepts that look meaningful (not auto-numbered junk)
    clean_concepts = [
        str(c).strip()
        for c in concepts
        if str(c).strip()
        and len(str(c).strip()) > 3
        and not str(c).strip()[-1].isdigit()  # Skip "Exploration Findings 760" style names
    ][:20]

    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (p:ResearchDoc {id: $id})
                SET p.title = $title,
                    p.summary = $summary,
                    p.content = $content,
                    p.kind = $kind,
                    p.source_ref = $source_ref,
                    p.created_at = datetime()
                WITH p
                MERGE (a:Agent {name: $agent})
                MERGE (a)-[:AUTHORED_DOC]->(p)
                """,
                id=item_id,
                title=f"{memory_type} memory {item_id[:8]}",
                summary=summary[:500],
                content=(content or summary)[:5000],
                kind="MemoryPointer",
                source_ref=f"sqlite://memory_items/{item_id}",
                agent=(source_agent or "Unknown"),
            )
            if clean_concepts:
                session.run(
                    """
                    MATCH (p:ResearchDoc {id: $id})
                    UNWIND $concepts AS cname
                    MERGE (c:Concept {name: cname})
                    MERGE (p)-[:ABOUT]->(c)
                    """,
                    id=item_id,
                    concepts=clean_concepts,
                )
        return True
    except Exception:
        return False
    finally:
        try:
            driver.close()
        except Exception:
            pass


def write_memory(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    content = str(payload.get("content") or payload.get("text") or "").strip()
    if not content:
        return {"ok": False, "error": "content is required"}

    memory_type = infer_memory_type(payload)
    source_agent = str(payload.get("source_agent") or payload.get("agent") or "Unknown").strip()[
        :120
    ]
    summary = str(payload.get("summary") or content[:220]).strip()
    confidence = clamp(float(payload.get("confidence") or 0.5), 0.0, 1.0)
    validation_status = normalize_validation(payload.get("validation_status"))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

    item_id = str(uuid.uuid4())
    should_embed = bool(payload.get("create_embedding", True))
    embedding = text_embedding(content) if should_embed else None

    conn.execute(
        """
        INSERT INTO memory_items (
            id, memory_type, content, summary, embedding_json, metadata_json, source_agent,
            confidence, validation_status, created_at, supersedes_id, conflict_group
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            memory_type,
            content,
            summary,
            json.dumps(embedding) if embedding is not None else None,
            json.dumps(metadata),
            source_agent,
            confidence,
            validation_status,
            now_iso(),
            str(payload.get("supersedes_id") or "") or None,
            None,
        ),
    )
    conn.commit()

    pointer_written = write_graph_pointer(
        item_id, memory_type, summary, source_agent, metadata, content=content
    )

    return {
        "ok": True,
        "item": {
            "id": item_id,
            "memory_type": memory_type,
            "source_agent": source_agent,
            "summary": summary,
            "confidence": confidence,
            "validation_status": validation_status,
            "created_at": now_iso(),
        },
        "graph_pointer_written": pointer_written,
    }


def query_memory(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    q = str(payload.get("query") or payload.get("q") or "").strip()
    if not q:
        return {"ok": False, "error": "query is required"}

    top_k = max(1, min(100, int(payload.get("top_k") or payload.get("k") or 10)))
    memory_type = str(payload.get("memory_type") or "").strip().lower()

    start = dt.datetime.now(dt.timezone.utc)
    params: list[Any] = []
    sql = """
      SELECT id, memory_type, content, summary, embedding_json, metadata_json, source_agent,
             confidence, validation_status, created_at, supersedes_id, conflict_group
      FROM memory_items
    """
    if memory_type in MEMORY_TYPES:
        sql += " WHERE memory_type = ?"
        params.append(memory_type)

    rows = conn.execute(sql, params).fetchall()
    qv = text_embedding(q)

    scored = []
    q_tokens = set(q.lower().split())
    for row in rows:
        emb = _load_json(row[4], [])
        sim = cosine(qv, emb if isinstance(emb, list) else [])
        text_blob = f"{row[2]} {row[3] or ''}".lower()
        overlap = 0.0
        if q_tokens:
            overlap = len([t for t in q_tokens if t in text_blob]) / len(q_tokens)
        score = (0.75 * sim) + (0.25 * overlap)
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = scored[:top_k]

    items = []
    selected_ids = []
    for score, row in chosen:
        selected_ids.append(row[0])
        items.append(
            {
                "id": row[0],
                "memory_type": row[1],
                "content": row[2],
                "summary": row[3],
                "metadata": _load_json(row[5], {}),
                "source_agent": row[6],
                "confidence": row[7],
                "validation_status": row[8],
                "created_at": row[9],
                "supersedes_id": row[10],
                "conflict_group": row[11],
                "score": round(float(score), 4),
            }
        )

    elapsed_ms = int((dt.datetime.now(dt.timezone.utc) - start).total_seconds() * 1000)
    conn.execute(
        """
        INSERT INTO retrieval_events (
            id, query, memory_type, top_k, hit_count, latency_ms, selected_ids_json, outcome, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            q,
            memory_type if memory_type in MEMORY_TYPES else None,
            top_k,
            len(items),
            elapsed_ms,
            json.dumps(selected_ids),
            "ok",
            now_iso(),
        ),
    )
    conn.commit()

    return {
        "ok": True,
        "query": q,
        "memory_type": memory_type if memory_type in MEMORY_TYPES else "any",
        "top_k": top_k,
        "hit_count": len(items),
        "latency_ms": elapsed_ms,
        "items": items,
    }


def memory_health(conn: sqlite3.Connection) -> dict[str, Any]:
    total = int(conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0])
    by_type_rows = conn.execute(
        "SELECT memory_type, COUNT(*) FROM memory_items GROUP BY memory_type"
    ).fetchall()
    by_val_rows = conn.execute(
        "SELECT validation_status, COUNT(*) FROM memory_items GROUP BY validation_status"
    ).fetchall()
    conflict_items = int(
        conn.execute(
            "SELECT COUNT(*) FROM memory_items WHERE conflict_group IS NOT NULL"
        ).fetchone()[0]
    )
    avg_conf = conn.execute("SELECT AVG(confidence) FROM memory_items").fetchone()[0]
    retrievals_24h = int(
        conn.execute(
            "SELECT COUNT(*) FROM retrieval_events WHERE created_at > datetime('now', '-1 day')"
        ).fetchone()[0]
    )

    by_type = {k: int(v) for k, v in by_type_rows}
    by_validation = {k: int(v) for k, v in by_val_rows}

    snapshot = {
        "id": str(uuid.uuid4()),
        "total_items": total,
        "by_type": by_type,
        "by_validation": by_validation,
        "conflict_items": conflict_items,
        "avg_confidence": round(float(avg_conf or 0.0), 4),
        "retrieval_events_24h": retrievals_24h,
        "captured_at": now_iso(),
    }

    conn.execute(
        """
        INSERT INTO memory_health_snapshots (
            id, total_items, by_type_json, by_validation_json, conflict_items, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot["id"],
            total,
            json.dumps(by_type),
            json.dumps(by_validation),
            conflict_items,
            snapshot["captured_at"],
        ),
    )
    conn.commit()
    return {"ok": True, "health": snapshot}


def consolidate_memories(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    min_items = max(3, min(100, int(payload.get("min_items") or 6)))
    window_days = max(1, min(365, int(payload.get("window_days") or 7)))

    rows = conn.execute(
        """
        SELECT source_agent, GROUP_CONCAT(id), GROUP_CONCAT(summary), COUNT(*)
        FROM memory_items
        WHERE memory_type = 'episodic' AND created_at >= datetime('now', ?)
        GROUP BY source_agent
        HAVING COUNT(*) >= ?
        """,
        (f"-{window_days} day", min_items),
    ).fetchall()

    created = 0
    for source_agent, ids_csv, summaries_csv, _count in rows:
        ids = [x for x in str(ids_csv or "").split(",") if x]
        summaries = [x for x in str(summaries_csv or "").split(",") if x]
        if not ids:
            continue
        summary = "Procedural pattern inferred: " + " | ".join(summaries[:10])
        metadata = {"derived_from": ids, "strategy": "episodic_to_procedural"}

        result = write_memory(
            conn,
            {
                "memory_type": "procedural",
                "content": summary,
                "summary": summary[:220],
                "source_agent": source_agent or "System",
                "confidence": 0.6,
                "validation_status": "unverified",
                "metadata": metadata,
            },
        )
        if result.get("ok"):
            created += 1

    return {"ok": True, "created": created, "window_days": window_days, "min_items": min_items}


def retention_pass(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    keep_days = max(7, min(3650, int(payload.get("keep_days") or 90)))
    conf_threshold = clamp(float(payload.get("confidence_threshold") or 0.35), 0.0, 1.0)

    cur = conn.execute(
        """
        DELETE FROM memory_items
        WHERE memory_type = 'episodic'
          AND confidence < ?
          AND validation_status != 'verified'
          AND created_at < datetime('now', ?)
        """,
        (conf_threshold, f"-{keep_days} day"),
    )
    conn.commit()
    return {
        "ok": True,
        "deleted": int(cur.rowcount or 0),
        "keep_days": keep_days,
        "confidence_threshold": conf_threshold,
    }


def conflict_scan(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    limit = max(100, min(50000, int(payload.get("limit") or 10000)))
    rows = conn.execute(
        """
        SELECT id, metadata_json
        FROM memory_items
        WHERE metadata_json IS NOT NULL AND metadata_json != ''
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    groups: dict[str, dict[str, list[str]]] = {}
    for item_id, metadata_json in rows:
        md = _load_json(metadata_json, {})
        if not isinstance(md, dict):
            continue
        key = str(md.get("claim_key") or "").strip()
        stance = str(md.get("stance") or "").strip().lower()
        if not key or stance not in {"positive", "negative"}:
            continue
        groups.setdefault(key, {"positive": [], "negative": []})[stance].append(item_id)

    conflicts = 0
    for key, bucket in groups.items():
        if bucket["positive"] and bucket["negative"]:
            conflict_id = f"cg::{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"
            ids = bucket["positive"] + bucket["negative"]
            conn.executemany(
                "UPDATE memory_items SET conflict_group = ?, validation_status = 'conflicted' WHERE id = ?",
                [(conflict_id, item_id) for item_id in ids],
            )
            conflicts += len(ids)

    conn.commit()
    return {"ok": True, "conflicted_items": conflicts, "scanned": len(rows)}


def decode_payload(payload_b64: str | None) -> dict[str, Any]:
    if not payload_b64:
        return {}
    try:
        raw = base64.b64decode(payload_b64.encode("utf-8"))
        value = json.loads(raw.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        required=True,
        choices=["write", "query", "health", "consolidate", "retention", "conflicts", "trace"],
    )
    parser.add_argument("--payload-b64", default="")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_db(conn)

    payload = decode_payload(args.payload_b64)

    if args.action == "write":
        out = write_memory(conn, payload)
    elif args.action == "query":
        out = query_memory(conn, payload)
    elif args.action == "health":
        out = memory_health(conn)
    elif args.action == "consolidate":
        out = consolidate_memories(conn, payload)
    elif args.action == "retention":
        out = retention_pass(conn, payload)
    elif args.action == "conflicts":
        out = conflict_scan(conn, payload)
    elif args.action == "trace":
        window_days = max(1, min(30, int(payload.get("window_days") or 1)))
        since = f"-{window_days} day"
        totals = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   AVG(latency_ms) AS avg_latency,
                   AVG(CASE WHEN hit_count > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate
            FROM retrieval_events
            WHERE created_at > datetime('now', ?)
            """,
            (since,),
        ).fetchone()
        total_queries = int(totals[0] or 0)
        avg_latency_ms = float(totals[1] or 0.0)
        hit_rate = float(totals[2] or 0.0)

        top_missed_rows = conn.execute(
            """
            SELECT query, COUNT(*) AS misses
            FROM retrieval_events
            WHERE created_at > datetime('now', ?)
              AND hit_count = 0
              AND query IS NOT NULL
              AND TRIM(query) != ''
            GROUP BY query
            ORDER BY misses DESC, query ASC
            LIMIT 8
            """,
            (since,),
        ).fetchall()
        top_slow_rows = conn.execute(
            """
            SELECT query, latency_ms
            FROM retrieval_events
            WHERE created_at > datetime('now', ?)
            ORDER BY latency_ms DESC, created_at DESC
            LIMIT 8
            """,
            (since,),
        ).fetchall()

        out = {
            "ok": True,
            "trace": {
                "window_days": window_days,
                "total_queries": total_queries,
                "avg_latency_ms": round(avg_latency_ms, 2),
                "hit_rate_pct": round(hit_rate * 100.0, 2),
                "top_missed_queries": [
                    {"query": str(q), "misses": int(m)} for q, m in top_missed_rows
                ],
                "slow_queries": [
                    {"query": str(q or ""), "latency_ms": int(l or 0)} for q, l in top_slow_rows
                ],
            },
        }
    else:
        out = {"ok": False, "error": "unsupported action"}

    out["db_path"] = str(DB_PATH)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
