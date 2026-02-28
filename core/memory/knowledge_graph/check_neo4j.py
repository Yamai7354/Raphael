import os
from neo4j import GraphDatabase
import json

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
)
with driver.session() as session:
    res = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as c")
    print("Labels in graph:")
    for r in res:
        print(r["labels"], r["c"])

    print("\nSample Models:")
    res = session.run("MATCH (n:Model) RETURN properties(n) as props LIMIT 10")
    models = []
    for r in res:
        models.append(r["props"])
        print(json.dumps(r["props"], indent=2))

    print("\nSample LLM Models:")
    res = session.run("MATCH (n:LLMModel) RETURN properties(n) as props LIMIT 10")
    for r in res:
        print(json.dumps(r["props"], indent=2))

    print("\nSample Embedding Models:")
    res = session.run("MATCH (n:EmbeddingModel) RETURN properties(n) as props LIMIT 10")
    for r in res:
        print(json.dumps(r["props"], indent=2))
