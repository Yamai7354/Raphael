import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SystemSelfModel:
    """
    The ultimate source of truth regarding the Raphael OS state.
    Aggregates lower-level engine outputs into a single holistic representation.
    """

    def __init__(self):
        pass

    def compile_state(
        self,
        health_data: Dict[str, Any],
        agent_counts: Dict[str, int],
        current_policy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Builds the unified self-representation tree.
        """
        # In a real environment, this might be saved to a persistent Document Store.
        state = {
            "identity": "Raphael OS Layer 12",
            "system_health": health_data.get("status", "unknown"),
            "critical_flags": health_data.get("flags", []),
            "workforce": {
                "total_active_agents": sum(agent_counts.values()),
                "distribution": agent_counts,
            },
            "active_directives": current_policy,
        }

        logger.debug("SystemSelfModel state compiled successfully.")
        return state
