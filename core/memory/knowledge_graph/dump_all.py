import os
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))


def dump_all():
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        # Get databases
        with driver.session(database="system") as session:
            result = session.run("SHOW DATABASES")
            dbs = [row["name"] for row in result if row["name"] not in ("system")]

        for db in dbs:
            print(f"--- Database: {db} ---")
            try:
                with driver.session(database=db) as session:
                    result = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count")
                    for row in result:
                        print(f"  {row['labels']}: {row['count']} nodes")

                    # Search for 192.168.1.198
                    res2 = session.run("""
                    MATCH (n)
                    WHERE any(k in keys(n) WHERE toString(n[k]) CONTAINS "192.168.1.198")
                    RETURN labels(n) as labels, properties(n) as props LIMIT 5
                    """)
                    matches = list(res2)
                    if matches:
                        print(f"  FOUND IP 192.168.1.198 in {len(matches)} nodes!")
                        for row in matches:
                            print(f"    {row['labels']}: {row['props']}")

                    # Search for mistral
                    res3 = session.run("""
                    MATCH (n)
                    WHERE any(k in keys(n) WHERE toString(n[k]) CONTAINS "mistral")
                    RETURN labels(n) as labels, properties(n) as props LIMIT 5
                    """)
                    matches3 = list(res3)
                    if matches3:
                        print(f"  FOUND MISTRAL in {len(matches3)} nodes!")
                        for row in matches3:
                            print(f"    {row['labels']}: {row['props']}")

            except Exception as e:
                print(f"  Error accessing database {db}: {e}")


if __name__ == "__main__":
    dump_all()
