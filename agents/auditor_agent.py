import logging
import uuid
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.raphael.agents.base import BaseAgent
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.understanding.schemas import Task

logger = logging.getLogger("raphael.agents.auditor")


class AuditorAgent(BaseAgent):
    """
    Agent responsible for auditing code quality and suggesting refactorings.
    RAPHAEL-503
    """

    def __init__(self, agent_id: str = "Auditor", capabilities: List[str] = None):
        super().__init__(agent_id, capabilities or ["audit", "qa", "code_review"])

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an audit request on a codebase or specific file.
        Payload expected: {"file_path": str, "content": str}
        """
        logs = []
        try:
            file_path = payload.get("file_path")
            content = payload.get("content", "")

            if not file_path:
                logs.append("No file path provided for audit.")
                return self._standard_response(False, logs, None)

            logs.append(f"Analyzing code for {file_path}")

            # Analyze code (Heuristic or LLM-based)
            issues = self._analyze_code(file_path, content)

            if issues:
                logs.append(f"Issues found: {len(issues)}. Creating refactoring subtask.")
                await self._create_refactor_task(file_path, issues, logs)
            else:
                logs.append("No issues found. Audit passed cleanly.")

            return self._standard_response(True, logs, {"issues": issues})

        except Exception as e:
            msg = f"Error in AuditorAgent: {str(e)}"
            logger.error(msg)
            logs.append(msg)
            return self._standard_response(False, logs, None)

    def _analyze_code(self, file_path: str, content: str) -> List[str]:
        """
        Simple heuristic analysis for finding common code issues.
        """
        issues = []
        if not content:
            return ["Empty content"]

        lines = content.splitlines()

        # Heuristic 1: File too long
        if len(lines) > 500:
            issues.append("File too long (>500 lines)")

        # Heuristic 2: explicit trigger for testing
        if "# TODO: REFACTOR" in content:
            issues.append("Explicit refactor marker found")

        # Heuristic 3: Complex function (naive check for indentation depth)
        for line_no, line in enumerate(lines, 1):
            if line.startswith("                ") and (
                "if " in line or "for " in line or "while " in line
            ):
                # 16 spaces = 4 levels deep
                issues.append(f"High nesting complexity at line {line_no}")
                break

        return issues

    async def _create_refactor_task(self, file_path: str, issues: List[str], logs: List[str]):
        """Publish a TASK_CREATED event to schedule a refactoring task."""
        try:
            task_id = str(uuid.uuid4())
            new_task = {
                "task_id": task_id,
                "original_intent": f"Refactor {os.path.basename(file_path)} based on audit",
                "status": "pending",
                "priority": 4,  # High priority for refactoring
                "payload": {
                    "file_path": file_path,
                    "issues": issues,
                    "description": f"Refactoring required. Issues: {', '.join(issues)}",
                },
                "dependencies": [],
                "created_at": datetime.now().isoformat(),
            }

            task_obj = Task(**new_task)

            bus = SystemEventBus()
            event = SystemEvent(
                event_type=EventType.TASK_CREATED,
                source_layer=LayerContext(layer_number=9, module_name="auditor_agent"),
                payload={"task": task_obj.model_dump()},
                priority=4,
            )

            await bus.publish(event)
            logs.append(f"Published TASK_CREATED event: {task_id} for refactoring.")
        except Exception as e:
            logs.append(f"Failed to mock-publish refactor task: {e}")
            logger.error(f"Failed to mock-publish refactor task: {e}")
