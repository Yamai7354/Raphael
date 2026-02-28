import logging
import datetime
import os
from typing import List, Dict, Any
from neo4j import GraphDatabase
from agents.base import BaseAgent

logger = logging.getLogger("agents.caretaker.evolution")


class EvolutionAgent(BaseAgent):
    """
    SCS - Evolution Agent
    Analyzes the Knowledge Graph for performance bottlenecks and proposes experiments.
    """

    def __init__(self, agent_id: str = "SCS-Evolution"):
        super().__init__(agent_id, ["graph_analysis", "evolution_loop", "caretaking"])
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7693")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_pass = os.getenv("NEO4J_PASSWORD", "")

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queries Neo4j for learning data and suggests improvements.
        """
        suggestions = []

        try:
            with GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_pass)
            ) as driver:
                with driver.session() as session:
                    # 1. Look for Model Performance bottlenecks
                    perf_bottlenecks = self._find_performance_bottlenecks(session)
                    for bn in perf_bottlenecks:
                        suggestions.append(
                            {
                                "suggestion": f"Optimize model routing for: {bn['model']}",
                                "rationale": f"Measured performance on {bn['machine']} is below threshold ({bn['speed']} t/s).",
                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        )

                    # 2. Look for recent Failures to create Improvement Hypotheses
                    recent_failures = self._find_recent_failures(session)
                    for failure in recent_failures:
                        suggestions.append(
                            {
                                "suggestion": f"Create Hypothesis for failure resolution: {failure['id']}",
                                "rationale": f"Failure detected during task execution. Evolution loop requires a resolution strategy.",
                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        )
        except Exception as e:
            logger.error(f"EvolutionAgent failed to connect to Neo4j: {e}")
            suggestions.append(
                {
                    "suggestion": "Check Neo4j connectivity",
                    "rationale": f"EvolutionAgent could not reach graph: {e}",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        return {"status": "Evolution Analysis Complete", "suggestions": suggestions}

    def _find_performance_bottlenecks(self, session) -> List[Dict[str, Any]]:
        query = "MATCH (p:PerformanceProfile) WHERE p.tokens_per_sec < 40 RETURN p.model AS model, p.machine AS machine, p.tokens_per_sec AS speed LIMIT 3"
        result = session.run(query)
        return [record.data() for record in result]

    def _find_recent_failures(self, session) -> List[Dict[str, Any]]:
        query = "MATCH (f:Failure) RETURN f.id AS id LIMIT 3"
        result = session.run(query)
        return [record.data() for record in result]
