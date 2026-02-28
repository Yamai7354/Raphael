import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class KnowledgeManager:
    """
    Acts as a systemic clearinghouse, granting or gating agent access
    to specific domains within the central Memory based on clearance.
    """

    def __init__(self):
        # Clearance levels: 1 (basic) to 5 (root)
        self.access_matrix = {
            "public_docs": 1,
            "agent_logs": 2,
            "architecture_specs": 3,
            "security_policies": 4,
            "system_root": 5,
        }

    def request_access(self, agent_id: str, clearance_level: int, domain: str) -> Dict[str, Any]:
        """
        Evaluates if an agent has the required clearance to access a memory domain.
        """
        required_clearance = self.access_matrix.get(domain)

        if not required_clearance:
            logger.warning(f"KnowledgeManager: Domain {domain} not found.")
            return {"agent_id": agent_id, "access_granted": False, "reason": "Unknown domain"}

        if clearance_level >= required_clearance:
            logger.info(f"KnowledgeManager: Agent {agent_id} granted access to {domain}.")
            return {
                "agent_id": agent_id,
                "access_granted": True,
                "domain": domain,
                "token": f"access_{domain}_{agent_id[:4]}",
            }
        else:
            logger.warning(
                f"KnowledgeManager: Agent {agent_id} denied access to {domain}. Requires {required_clearance}, has {clearance_level}."
            )
            return {
                "agent_id": agent_id,
                "access_granted": False,
                "domain": domain,
                "reason": "Insufficient clearance level",
            }
