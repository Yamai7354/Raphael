import os
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
)
with driver.session() as session:
    res = session.run("SHOW DATABASES")
    print("Databases:")
    for r in res:
        print(r["name"])
