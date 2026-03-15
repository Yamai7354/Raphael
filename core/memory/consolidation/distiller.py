import logging
import json
import os
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("memory_distiller")


class LLMDistiller:
    """NAR-1: Distills episodic logs into semantic insights and procedural rules.
    Wired to the local AI Router using a structured JSON prompt and the 'memory' role.
    """

    def __init__(self, model_override: Optional[str] = None):
        self.role = "memory"
        self.api_url = os.getenv("AI_ROUTER_URL", "http://127.0.0.1:8000/v1/chat/completions")

    async def distill_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights from a completed task using the local AI router."""
        task_id = str(task_data.get("id", "unknown"))
        logger.info(f"Distilling task: {task_id} using role {self.role}")

        prompt = f"""
You are an AI Memory Distiller. Your job is to analyze a completed task and extract core insights for long-term memory.
You must return only valid JSON matching this schema:
{{
  "summary": "A concise 1-2 sentence semantic summary of what was accomplished and learned.",
  "rule": {{
    "condition": "A short, descriptive trigger key (e.g. 'auth_error' or 'deploy_neo4j')",
    "strategy": "The actual procedure or heuristic learned to solve the condition",
    "confidence": 0.0 to 1.0 (float)
  }} // or null if no reusable procedural rule can be extracted
}}

Task Data:
{json.dumps(task_data, indent=2)}
        """

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Content-Type": "application/json",
                    },
                    json={
                        "role": self.role,
                        "messages": [
                            {"role": "system", "content": "You are a JSON-only response agent."},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                result_text = response.json()["choices"][0]["message"]["content"]

                # Parse the JSON response
                parsed = json.loads(result_text)

                return {
                    "summary": parsed.get("summary", "Task completed."),
                    "rule": parsed.get("rule", None),
                    "metadata": {
                        "distilled_at": datetime.utcnow().isoformat(),
                        "source_task_id": task_id,
                        "distiller_role": self.role,
                    },
                }

        except Exception as e:
            logger.error(f"Failed to distill task {task_id} via local LLM: {e}")
            return self._mock_distill(task_data)

    def _mock_distill(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback mock implementation if API fails."""
        title = task_data.get("title", "Unknown")
        assigned_to = task_data.get("assigned_to", "Unknown")

        semantic_summary = f"Agent {assigned_to} successfully completed '{title}'. "
        if "refactor" in title.lower() or "optimize" in title.lower():
            semantic_summary += "Demonstrated capability in code maintenance."
        else:
            semantic_summary += "Demonstrated general task execution proficiency."

        procedural_rule = None
        if str(task_data.get("priority", "")).lower() == "high":
            procedural_rule = {
                "condition": f"prefer_agent:{assigned_to}",
                "strategy": f"use_for:{task_data.get('category', 'general')}",
                "confidence": 0.85,
            }

        return {
            "summary": semantic_summary,
            "rule": procedural_rule,
            "metadata": {
                "distilled_at": datetime.utcnow().isoformat(),
                "source_task_id": str(task_data.get("id")),
                "fallback": True,
            },
        }
