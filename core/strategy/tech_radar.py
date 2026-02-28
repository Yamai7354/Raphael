import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class TechRadar:
    """
    Scans incoming technology trends or tools and assigns a relevance score
    based on the current active system goals.
    """

    def __init__(self):
        pass

    def evaluate_topics(self, topics: List[str], current_goal: str) -> List[Dict[str, Any]]:
        """
        Scores external topics. A higher score means the Learning Engine should
        prioritize exploring or ingesting this technology.
        """
        evaluated = []

        # Simple mock logic for architectural validation:
        # If any word from the topic exists in the goal, it's highly relevant.
        goal_keywords = set(current_goal.lower().split())

        for topic in topics:
            topic_keywords = set(topic.lower().split())

            # Intersection gives a massive boost
            match_count = len(goal_keywords.intersection(topic_keywords))

            base_score = 0.1  # Every tech gets a baseline curiosity score
            score = min(1.0, base_score + (match_count * 0.4))

            evaluated.append(
                {"topic": topic, "relevance_score": score, "aligned_with_goal": match_count > 0}
            )

        # Sort highest first
        evaluated.sort(key=lambda x: x["relevance_score"], reverse=True)
        logger.info(f"TechRadar evaluated {len(evaluated)} topics against goal.")

        return evaluated
