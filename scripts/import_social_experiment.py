import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

CSV_PATH = Path('/Users/yamai/Downloads/social_experiment.csv')
REPORT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'social_experiment_import_report.json'

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7693')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')


def is_placeholder_query(query: str) -> bool:
    if '$' in query:
        return True
    if re.search(r'\bSET\s+\w+\s*=\s*\([^\)]*\)-\[', query):
        return True
    return False


def main() -> None:
    if not CSV_PATH.exists():
        print(json.dumps({'ok': False, 'error': f'CSV not found: {CSV_PATH}'}, indent=2))
        return

    with CSV_PATH.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    executed = []
    skipped = []
    errors = []

    try:
        with driver.session() as session:
            for row in rows:
                row_id = str(row.get('id', '')).strip()
                name = (row.get('name') or '').strip()
                query = (row.get('query') or '').strip()
                is_folder = str(row.get('isFolder', '')).lower() == 'true'

                if is_folder or not query:
                    skipped.append({'id': row_id, 'name': name, 'reason': 'folder_or_empty'})
                    continue

                if is_placeholder_query(query):
                    skipped.append({'id': row_id, 'name': name, 'reason': 'placeholder_or_template'})
                    continue

                try:
                    session.run(query).consume()
                    executed.append({'id': row_id, 'name': name})
                except Exception as exc:
                    errors.append({'id': row_id, 'name': name, 'error': str(exc)[:500]})

            # Ensure key relationships from the diagram are linked if nodes exist.
            bridge_queries = [
                "MATCH (c:Character)-[:HAS_MEMORY]->(m:Memory)-[:REFERS_TO]->(e:Event) MERGE (c)-[:PARTICIPATED_IN]->(e)",
                "MATCH (h:Hypothesis)-[:TESTED_BY]->(x:Experiment) MATCH (x)-[:CREATES]->(k:Knowledge) MERGE (h)-[:VALIDATED_AS]->(k)",
                "MATCH (s:Story)-[:REFERS_TO_HISTORY]->(h:HistoricalEvent) MATCH (ci:CulturalIdentity) MERGE (s)-[:SHAPES]->(ci)",
                "MATCH (b:Belief)-[:CONTRIBUTES_TO]->(ci:CulturalIdentity) MATCH (st:Strategy) MERGE (st)-[:SHAPES]->(ci)",
                "MATCH (i:Innovation) MATCH (b:Belief) MERGE (i)-[:GENERATED]->(b)",
            ]
            for q in bridge_queries:
                try:
                    session.run(q).consume()
                except Exception:
                    pass

            node_counts = session.run(
                "MATCH (n) RETURN labels(n) AS labels, count(*) AS count ORDER BY count DESC"
            ).data()
            rel_counts = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"
            ).data()

    finally:
        driver.close()

    report = {
        'ok': len(errors) == 0,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'csv_path': str(CSV_PATH),
        'executed_count': len(executed),
        'skipped_count': len(skipped),
        'error_count': len(errors),
        'executed': executed,
        'skipped': skipped,
        'errors': errors,
        'node_counts': node_counts,
        'relationship_counts': rel_counts,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
