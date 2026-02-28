import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SQLITE_PATH = DATA_DIR / "research_hybrid.db"
REPORT_PATH = DATA_DIR / "research_hybrid_report.json"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
OLLAMA_BASE = os.getenv("OLLAMA_LOCAL_URL", "http://100.125.58.22:5000").rstrip("/")


def ensure_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS research_docs (
            doc_id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            title TEXT,
            summary TEXT,
            content TEXT,
            concepts_json TEXT,
            source_memory_eid TEXT,
            source_timestamp TEXT,
            embedding_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_research_docs_agent ON research_docs(agent)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_research_docs_ts ON research_docs(source_timestamp)"
    )
    conn.commit()


def make_doc_id(memory_eid: str, agent: str, note: str) -> str:
    raw = f"{memory_eid}|{agent}|{note}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:20]


def embed_text(text: str, model: str) -> list[float] | None:
    try:
        response = httpx.post(
            f"{OLLAMA_BASE}/api/embeddings",
            json={"model": model, "prompt": text[:4000]},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        vector = payload.get("embedding")
        if isinstance(vector, list) and vector:
            return [float(x) for x in vector[:1024]]
    except Exception:
        return None
    return None


def count_snapshot(session):
    out = {}
    out["memory_nodes"] = session.run("MATCH (m:Memory) RETURN count(m) AS c").single()["c"]
    out["concept_nodes"] = session.run("MATCH (c:Concept) RETURN count(c) AS c").single()["c"]
    out["research_docs"] = session.run("MATCH (d:ResearchDoc) RETURN count(d) AS c").single()["c"]
    out["research_rollups"] = session.run("MATCH (r:ResearchRollup) RETURN count(r) AS c").single()[
        "c"
    ]
    out["linked_to_edges"] = session.run("MATCH ()-[r:LinkedTo]->() RETURN count(r) AS c").single()[
        "c"
    ]
    out["authored_doc_edges"] = session.run(
        "MATCH ()-[r:AUTHORED_DOC]->() RETURN count(r) AS c"
    ).single()["c"]
    out["about_edges"] = session.run("MATCH ()-[r:ABOUT]->() RETURN count(r) AS c").single()["c"]
    out["rollup_edges"] = session.run(
        "MATCH ()-[r:HAS_RESEARCH_ROLLUP]->() RETURN count(r) AS c"
    ).single()["c"]
    return out


def fetch_memory_batches(session, limit: int):
    rows = session.run(
        """
        MATCH (m:Memory)-[:LinkedTo]->(c:Concept)
        WHERE m.agent IS NOT NULL AND m.note IS NOT NULL
        WITH m, collect(DISTINCT c.name)[0..8] AS concepts
        RETURN elementId(m) AS memory_eid,
               m.agent AS agent,
               m.note AS note,
               toString(m.timestamp) AS ts,
               concepts
        LIMIT $limit
        """,
        limit=limit,
    ).data()
    return rows


def migrate(limit: int, embed: bool, embed_model: str):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    ensure_sqlite(conn)

    inserted = 0
    skipped = 0
    linked = 0

    try:
        with driver.session() as session:
            before = count_snapshot(session)
            rows = fetch_memory_batches(session, limit)

            for row in rows:
                agent = str(row.get("agent") or "").strip()
                note = str(row.get("note") or "").strip()
                memory_eid = str(row.get("memory_eid") or "")
                ts = str(row.get("ts") or "")
                concepts = [str(c) for c in (row.get("concepts") or []) if c]

                # Guard: skip empty or trivially short notes
                if not agent or not note or len(note) < 20:
                    skipped += 1
                    continue

                doc_id = make_doc_id(memory_eid, agent, note)
                exists = conn.execute(
                    "SELECT 1 FROM research_docs WHERE doc_id = ?", (doc_id,)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

                title = concepts[0] if concepts else f"{agent} research finding"
                summary = note[:180]
                embedding = embed_text(note, embed_model) if embed else None

                conn.execute(
                    """
                    INSERT INTO research_docs(
                        doc_id, agent, title, summary, content, concepts_json, source_memory_eid,
                        source_timestamp, embedding_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        agent,
                        title,
                        summary,
                        note,
                        json.dumps(concepts),
                        memory_eid,
                        ts,
                        json.dumps(embedding) if embedding is not None else None,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

                session.run(
                    """
                    MERGE (d:ResearchDoc {id: $doc_id})
                    SET d.title = $title,
                        d.summary = $summary,
                        d.content = $content,
                        d.source_ref = $source_ref,
                        d.agent = $agent,
                        d.created_at = datetime()
                    WITH d
                    MATCH (a:Agent {name: $agent})
                    MERGE (a)-[:AUTHORED_DOC]->(d)
                    """,
                    doc_id=doc_id,
                    title=title,
                    summary=summary,
                    content=note[:5000],
                    source_ref=f"sqlite://research_docs/{doc_id}",
                    agent=agent,
                )

                for concept in concepts:
                    session.run(
                        """
                        MERGE (c:Concept {name: $concept})
                        WITH c
                        MATCH (d:ResearchDoc {id: $doc_id})
                        MERGE (d)-[:ABOUT]->(c)
                        """,
                        concept=concept,
                        doc_id=doc_id,
                    )
                    linked += 1

                # Mark source memory archived to enable pruning later.
                session.run(
                    """
                    MATCH (m:Memory)
                    WHERE elementId(m) = $memory_eid
                    SET m.archived = true, m.archived_at = datetime()
                    """,
                    memory_eid=memory_eid,
                )
                inserted += 1

            conn.commit()
            after = count_snapshot(session)

    finally:
        conn.close()
        driver.close()

    return {
        "inserted_docs": inserted,
        "skipped_docs": skipped,
        "about_links_created": linked,
        "sqlite_path": str(SQLITE_PATH),
        "before": before,
        "after": after,
    }


def prune_archived(prune_days: int, batch_size: int, aggressive: bool = False):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    deleted = 0
    try:
        with driver.session() as session:
            while True:
                row = session.run(
                    """
                    MATCH (m:Memory)
                    WHERE m.archived = true
                      AND (
                        $aggressive = true OR
                        (
                          m.timestamp IS NOT NULL
                          AND datetime(m.timestamp) < datetime() - duration({days: $days})
                        )
                      )
                    WITH m LIMIT $batch
                    DETACH DELETE m
                    RETURN count(*) AS c
                    """,
                    days=prune_days,
                    batch=batch_size,
                    aggressive=aggressive,
                ).single()
                c = int(row["c"]) if row and row["c"] is not None else 0
                deleted += c
                if c == 0:
                    break
    finally:
        driver.close()
    return {
        "deleted_archived_memory_nodes": deleted,
        "prune_days": prune_days,
        "batch_size": batch_size,
        "aggressive": aggressive,
    }


def compact_rollups():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    created = 0
    try:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (m:Memory {archived: true})-[:LinkedTo]->(c:Concept)
                WHERE m.agent IS NOT NULL
                WITH m.agent AS agent,
                     date(datetime(coalesce(m.timestamp, m.archived_at, datetime()))) AS day,
                     count(DISTINCT m) AS memory_count,
                     collect(DISTINCT c.name)[0..12] AS concepts
                MERGE (r:ResearchRollup {agent: agent, day: toString(day)})
                SET r.memory_count = memory_count,
                    r.concepts = concepts,
                    r.updated_at = datetime()
                WITH r, agent
                MATCH (a:Agent {name: agent})
                MERGE (a)-[:HAS_RESEARCH_ROLLUP]->(r)
                RETURN count(r) AS c
                """
            ).single()
            created = int(rows["c"]) if rows and rows["c"] is not None else 0
    finally:
        driver.close()
    return {"rollups_touched": created}


def main():
    parser = argparse.ArgumentParser(description="Hybridize graph research storage")
    parser.add_argument(
        "--limit", type=int, default=4000, help="Max memory rows to migrate per run"
    )
    parser.add_argument("--embed", action="store_true", help="Generate embeddings via Ollama")
    parser.add_argument(
        "--embed-model", default="text-embedding-bge-large-en-v1.5", help="Embedding model name"
    )
    parser.add_argument("--prune", action="store_true", help="Prune archived old memory nodes")
    parser.add_argument("--prune-days", type=int, default=14)
    parser.add_argument("--prune-batch", type=int, default=5000)
    parser.add_argument(
        "--aggressive-prune", action="store_true", help="Delete archived memory immediately"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Create ResearchRollup summary nodes from archived memory",
    )
    args = parser.parse_args()

    migration = migrate(limit=max(10, args.limit), embed=args.embed, embed_model=args.embed_model)
    compaction = compact_rollups() if args.compact else None
    pruning = (
        prune_archived(args.prune_days, args.prune_batch, aggressive=args.aggressive_prune)
        if args.prune
        else None
    )

    report = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "limit": args.limit,
            "embed": args.embed,
            "embed_model": args.embed_model,
            "prune": args.prune,
            "prune_days": args.prune_days,
            "prune_batch": args.prune_batch,
            "aggressive_prune": args.aggressive_prune,
            "compact": args.compact,
        },
        "migration": migration,
        "compaction": compaction,
        "pruning": pruning,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
