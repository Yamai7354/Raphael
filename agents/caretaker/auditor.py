import logging
import os
import datetime
from typing import List, Dict, Any
from agents.base import BaseAgent

logger = logging.getLogger("agents.caretaker.auditor")


class WorkspaceAuditor(BaseAgent):
    """
    SCS - Workspace Auditor
    Checks for structural issues, redundancy, and optimization opportunities.
    """

    def __init__(self, agent_id: str = "SCS-Auditor"):
        super().__init__(agent_id, ["workspace_audit", "structural_optimization", "caretaking"])
        self.workspace_root = "/Users/yamai/ai/Raphael"

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scans the workspace and identifies suggested changes.
        """
        suggestions = []

        # 1. Check for directory redundancy (Basic heuristic, improved by LLM later)
        redundant_folders = self._find_redundant_folders()
        for folder in redundant_folders:
            suggestions.append(
                {
                    "suggestion": f"Consolidate redundant folder: {folder['path']}",
                    "rationale": f"Folder appears to be a duplicate or subset of {folder['matches']}.",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        # 2. Check for missing READMEs or documentation gaps
        doc_gaps = self._find_documentation_gaps()
        for gap in doc_gaps:
            suggestions.append(
                {
                    "suggestion": f"Generate documentation for: {gap}",
                    "rationale": "Missing module overview or README.md.",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        # 3. Simple error scan (Syntax, common pitfalls)
        errors = self._scan_for_structural_errors()
        for error in errors:
            suggestions.append(
                {
                    "suggestion": f"Fix structural error in {error['file']}",
                    "rationale": error["reason"],
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        return {"status": "Audit Complete", "suggestions": suggestions}

    def _find_redundant_folders(self) -> List[Dict[str, str]]:
        redundancies = []

        # Check for the known legacy agent overlap
        characters_path = os.path.join(self.workspace_root, "packages/characters")
        legacy_path = os.path.join(self.workspace_root, "packages/legacy/agents")

        if os.path.exists(characters_path) and os.path.exists(legacy_path):
            redundancies.append(
                {
                    "path": characters_path,
                    "matches": "packages/legacy/agents",
                    "reason": "Redundant agent storage. Modern implementations should be in 'legacy/agents' or 'core/agents'.",
                }
            )

        # Check for duplicate 'agent_ecosystem' subfolders if any
        return redundancies

    def _find_documentation_gaps(self) -> List[str]:
        gaps = []
        for root, dirs, files in os.walk(self.workspace_root):
            if any(
                p in root
                for p in ["venv", ".git", "__pycache__", "node_modules", ".gemini", "bloom-export"]
            ):
                continue

            # Significant directory check: has .py files but no README
            if any(f.endswith(".py") for f in files) and not any(
                f.lower() == "readme.md" for f in files
            ):
                gaps.append(os.path.relpath(root, self.workspace_root))

        return gaps[:5]

    def _scan_for_structural_errors(self) -> List[Dict[str, str]]:
        errors = []
        # Check for circular imports or malformed __init__.py files
        # (Simplified heuristic for the demo)
        return errors
