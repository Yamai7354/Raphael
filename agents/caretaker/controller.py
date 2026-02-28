import logging
import datetime
import os
from typing import List, Dict, Any, Optional
from src.raphael.agents.base import BaseAgent
from src.raphael.agents.caretaker.auditor import WorkspaceAuditor
from src.raphael.agents.caretaker.sage import DocumentationSage
from src.raphael.agents.caretaker.evolution import EvolutionAgent

logger = logging.getLogger("raphael.agents.caretaker.controller")


class CaretakerController(BaseAgent):
    """
    SCS - Controller
    Orchestrates the Caretaker Suite: Auditor, Sage, and Evolution agents.
    Implements model fallback logic for cloud -> local.
    """

    def __init__(self, agent_id: str = "SCS-Controller"):
        super().__init__(agent_id, ["caretaking_orchestration", "model_fallback"])
        self.report_path = "/Users/yamai/ai/Raphael/docs/caretaker_report.md"

        # Primary Models (Cloud)
        self.primary_models = ["glm-5:cloud", "qwen3-coder-next:cloud", "kimi-k2.5:cloud"]
        # Fallback Models (Local)
        self.fallback_models = ["llama3:8b", "deepseek-coder:6.7b"]

        # Initialize sub-agents
        self.auditor = WorkspaceAuditor()
        self.sage = DocumentationSage()
        self.evolution = EvolutionAgent()

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs the full caretaking cycle.
        """
        logger.info("Starting Swarm Caretaker Suite (SCS) cycle...")

        all_suggestions = []

        # 1. Run Auditor
        auditor_results = await self.auditor.execute({})
        all_suggestions.extend(auditor_results.get("suggestions", []))

        # 2. Run Sage
        sage_results = await self.sage.execute({})
        all_suggestions.extend(sage_results.get("suggestions", []))

        # 3. Run Evolution
        evolution_results = await self.evolution.execute({})
        all_suggestions.extend(evolution_results.get("suggestions", []))

        # 4. Generate Report
        self._generate_report(all_suggestions)

        return {
            "status": "Caretaking Cycle Complete",
            "report": self.report_path,
            "suggestion_count": len(all_suggestions),
        }

    def _generate_report(self, suggestions: List[Dict[str, Any]]):
        """
        Writes the caretaker_report.md with suggestions.
        """
        now = datetime.datetime.now()
        report_header = f"""# Swarm Caretaker Suggested Changes Report
Generated: {now.strftime("%Y-%m-%d %H:%M:%S")}

This report contains suggested improvements, consolidations, and optimizations for the Raphael workspace.
Each suggestion requires manual verification before execution.

---

| Date | Time | Suggestion | Rationale |
|---|---|---|---|
"""
        rows = ""
        for s in suggestions:
            # We assume the sub-agents might have formatted their own timestamp,
            # but we can also use the generation time if needed.
            ts = datetime.datetime.strptime(s["timestamp"], "%Y-%m-%d %H:%M:%S")
            date_str = ts.strftime("%Y-%m-%d")
            time_str = ts.strftime("%H:%M:%S")
            rows += f"| {date_str} | {time_str} | {s['suggestion']} | {s['rationale']} |\n"

        content = report_header + rows

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.report_path), exist_ok=True)

        with open(self.report_path, "w") as f:
            f.write(content)

        logger.info(f"Report generated at {self.report_path}")

    def get_effective_model(self, task_type: str) -> str:
        """
        Implements fallback logic.
        (Drafting logic for future integration with a live router)
        """
        # Logic to check cloud availability would go here
        # For now, we favor primary cloud models
        if task_type == "coding":
            return "qwen3-coder-next:cloud"
        elif task_type == "reasoning":
            return "kimi-k2.5:cloud"
        return "glm-5:cloud"
