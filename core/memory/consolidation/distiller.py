import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger("memory_distiller")


class LLMDistiller:
    """NAR-1: Distills episodic logs into semantic insights and procedural rules.
    In a production environment, this would call an LLM (e.g., DeepSeek, GPT-4).
    For Phase 4 execution, we provide a structured mock implementation.
    """

    async def distill_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights from a completed task."""
        logger.info(f"Distilling task: {task_data.get('id')}")

        # Simulated LLM logic: Extract semantic meaning
        title = task_data.get("title", "Unknown")
        assigned_to = task_data.get("assigned_to", "Unknown")

        semantic_summary = f"Agent {assigned_to} successfully completed '{title}'. "
        if "refactor" in title.lower() or "optimize" in title.lower():
            semantic_summary += (
                "Demonstrated capability in code maintenance and optimization."
            )
        else:
            semantic_summary += "Demonstrated general task execution proficiency."

        # Extract procedural rule if priority was high or success was notable
        procedural_rule = None
        if task_data.get("priority") == "high":
            procedural_rule = {
                "condition": f"prefer_agent:{assigned_to}",
                "strategy": f"use_specifically_for:{task_data.get('category', 'general')}",
                "confidence": 0.85,
            }

        return {
            "summary": semantic_summary,
            "rule": procedural_rule,
            "metadata": {
                "distilled_at": datetime.utcnow().isoformat(),
                "source_task_id": str(task_data.get("id")),
            },
        }
