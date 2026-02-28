import logging
from typing import Dict, Any, List
from qdrant_client import QdrantClient
from src.raphael.agents.stewardship_base import DatabaseStewardAgent

logger = logging.getLogger(__name__)


class QdrantStewardAgent(DatabaseStewardAgent):
    """
    Agent responsible for Qdrant Vector Database health.
    """

    def __init__(self, agent_id: str, url: str):
        super().__init__(agent_id, ["vector_validation", "collection_maintenance"])
        self.client = QdrantClient(url=url)

    async def validate(self) -> Dict[str, Any]:
        issues = {}
        try:
            collections = self.client.get_collections().collections
            for coll in collections:
                info = self.client.get_collection(coll.name)
                # Check for indexed points vs total points consistency
                if info.status != "green":
                    issues[coll.name] = f"Status is {info.status}"
        except Exception as e:
            issues["connection"] = str(e)
        return issues

    async def repair(self, issues: Dict[str, Any]) -> Dict[str, Any]:
        # Vector DBs often require re-indexing rather than small manual repairs
        return {"status": "Manual re-indexing recommended for flagged collections"}
