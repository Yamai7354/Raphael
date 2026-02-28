import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class InnovationEngine:
    """
    Receives raw insights from autonomous research and scores them to prioritize
    which new systemic capabilities should be formally acquired by the Learning Engine.
    """

    def __init__(self):
        pass

    def prioritize_discoveries(
        self, research_outputs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Ranks a backlog of discoveries based on simulated impact and ease of integration.
        """
        ranked_innovations = []

        for output in research_outputs:
            discoverer = output.get("discoverer", "unknown")
            concept = output.get("concept", "unknown")

            # Simulated scoring logic: Impact (1-10) - Friction (1-10)
            impact = output.get("estimated_impact", 5)
            friction = output.get("integration_friction", 5)

            # Calculate an "Innovation ROI" score
            roi = impact - (friction * 0.5)

            ranked_innovations.append(
                {
                    "concept": concept,
                    "discoverer": discoverer,
                    "innovation_roi": roi,
                    "status": "pending_acquisition" if roi > 3.0 else "archived",
                }
            )

        # Sort highest ROI first
        ranked_innovations.sort(key=lambda x: x["innovation_roi"], reverse=True)

        logger.info(f"InnovationEngine ranked {len(ranked_innovations)} new discoveries.")
        return ranked_innovations
