import os
from neo4j import GraphDatabase
import json

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
)
with driver.session() as session:
    res = session.run("""
    MATCH (n)
    UNWIND keys(n) AS key
    WITH n, key, n[key] AS value
    WHERE value CONTAINS "192.168.1.198"
    RETURN labels(n) as labels, key, value, properties(n) as props
    LIMIT 20
    """)
    matches = [r for r in res]
    print(f"Nodes with '192.168.1.198': {len(matches)}")
    for r in matches:
        print(f"Labels: {r['labels']}")
        print(f"Key: {r['key']}")
        print(f"Value: {r['value']}")
        # print(f"Props: {json.dumps(r['props'], indent=2)}")
        print("-------------")
