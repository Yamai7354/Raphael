import logging
import asyncio
from typing import Dict, Any, List
from neo4j import GraphDatabase
from agents.stewardship_base import DatabaseStewardAgent

logger = logging.getLogger(__name__)


class Neo4jStewardAgent(DatabaseStewardAgent):
    """
    Agent responsible for Neo4j Graph Health.
    Implements validation and repair logic from steward.py.
    """

    def __init__(self, agent_id: str, uri: str, user: str, password: str):
        super().__init__(agent_id, ["graph_validation", "graph_repair", "neo4j_maintenance"])
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

        self.validation_queries = {
            "orphan_observations": "MATCH (o:Observation) WHERE NOT (o)--() RETURN count(o) AS count",
            "episodes_missing_triggers": "MATCH (e:Episode) WHERE NOT (e)-[:TRIGGERED_BY]->() RETURN count(e) AS count",
            "duplicate_uids": "MATCH (n) WITH n.uid AS uid, count(n) AS c WHERE uid IS NOT NULL AND c > 1 RETURN count(uid) AS count",
        }

        self.repair_queries = [
            """
            MATCH (n)
            WITH n.uid AS uid, collect(n) AS nodes
            WHERE uid IS NOT NULL AND size(nodes) > 1
            CALL {
                WITH nodes
                WITH nodes[0] AS keep, nodes[1..] AS dupes
                UNWIND dupes AS d
                CALL {
                    WITH keep, d
                    MATCH (d)-[r]->(x)
                    MERGE (keep)-[nr:TYPE(r)]->(x)
                    SET nr += r
                }
                CALL {
                    WITH keep, d
                    MATCH (x)-[r]->(d)
                    MERGE (x)-[nr:TYPE(r)]->(keep)
                    SET nr += r
                }
                DETACH DELETE d
            }
            RETURN count(*) as processed
            """
        ]

    async def validate(self) -> Dict[str, Any]:
        issues = {}
        with self.driver.session() as session:
            for name, query in self.validation_queries.items():
                result = session.run(query)
                record = result.single()
                issues[name] = record["count"] if record else 0
        return issues

    async def repair(self, issues: Dict[str, Any]) -> Dict[str, Any]:
        results = {"queries_run": 0, "status": "Incomplete"}
        with self.driver.session() as session:
            for query in self.repair_queries:
                session.run(query)
                results["queries_run"] += 1
        results["status"] = "Complete"
        return results

    def close(self):
        self.driver.close()
