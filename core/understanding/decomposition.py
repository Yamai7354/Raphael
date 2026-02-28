from typing import List
from src.raphael.understanding.schemas import Task, SubTask
import re


class DecompositionEngine:
    """
    Breaks high-level Tasks into an executable graph of SubTasks.
    (This is a placeholder for an LLM/Cognitive evaluation layer).
    """

    def decompose(self, task: Task) -> Task:
        """
        Evaluates the `original_intent` and injects the dependency graph
        into `task.sub_tasks`.
        """
        intent = task.original_intent.lower()

        # Simulated LLM Decomposition based on keywords
        if "deploy" in intent or "build" in intent:
            # Step 1: Verification
            st1 = SubTask(
                parent_task_id=task.task_id,
                description="Verify repository constraints and permissions.",
                required_capabilities=["filesystem"],
            )
            # Step 2: Execution (Depends on 1)
            st2 = SubTask(
                parent_task_id=task.task_id,
                description="Execute the physical build/deploy script.",
                dependencies=[st1.sub_task_id],
                required_capabilities=["bash"],
            )
            task.sub_tasks = [st1, st2]

        elif "exception" in intent or "error" in intent:
            # Crash resolution pipeline
            st1 = SubTask(
                parent_task_id=task.task_id,
                description="Read full stack trace from system monitor logs",
                required_capabilities=["read_logs"],
            )
            st2 = SubTask(
                parent_task_id=task.task_id,
                description="Analyze root cause against source code",
                dependencies=[st1.sub_task_id],
                required_capabilities=["python", "reasoning"],
            )
            task.sub_tasks = [st1, st2]

        else:
            # Generic single-step execution
            st1 = SubTask(
                parent_task_id=task.task_id,
                description="Execute inferred direct user command.",
                required_capabilities=["general_agent"],
            )
            task.sub_tasks = [st1]

        return task
