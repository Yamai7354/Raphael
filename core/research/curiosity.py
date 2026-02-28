import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class CuriosityEngine:
    """
    Scans the system's memory (mocked) to identify areas lacking data.
    Generates formal Knowledge Gaps for the system to explore.
    """

    def __init__(self):
        # Mocked memory state for Layer 11
        self.known_domains = {
            "file_system_io": {"confidence": 0.95},
            "python_execution": {"confidence": 0.98},
            "rust_compilation": {"confidence": 0.10},  # Gap
            "network_latency": {"confidence": 0.20},  # Gap
        }

    def scan_for_gaps(self) -> List[Dict[str, Any]]:
        """
        Identifies domains with low confidence scores.
        Returns a sorted list of Knowledge Gaps (highest priority / lowest confidence first).
        """
        gaps = []
        for domain, data in self.known_domains.items():
            if data["confidence"] < 0.5:
                # Calculate priority: lower confidence = higher priority
                priority = 1.0 - data["confidence"]
                gaps.append(
                    {
                        "topic": domain,
                        "gap_description": f"Insufficient data on {domain}",
                        "confidence_level": data["confidence"],
                        "priority": priority,
                    }
                )

        # Sort by highest priority
        gaps.sort(key=lambda x: x["priority"], reverse=True)
        logger.info(f"Curiosity Engine identified {len(gaps)} knowledge gaps.")
        return gaps
