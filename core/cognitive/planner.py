import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ExecutionPlanner:
    """
    Takes the messy graph of SubTasks mapped by Layer 3 Decomposition
    and structurally sorts them into a linear or parallel execution sequence.
    """

    def generate_plan(self, enriched_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a context-enriched task, evaluates SubTask dependencies,
        and generates an ordered execution array.
        """
        sub_tasks = enriched_task.get("sub_tasks", [])

        # We need to sort by dependencies.
        # Simple topological sort mock
        ordered_sequence = []
        pending = {st["sub_task_id"]: st for st in sub_tasks}
        completed_set = set()

        # Max iteration constraint to prevent infinite loops in bad graphs
        max_iters = len(sub_tasks) * 2
        iters = 0

        while pending and iters < max_iters:
            for st_id, st_data in list(pending.items()):
                deps = st_data.get("dependencies", [])

                # If it has no dependencies, or all its deps are completed
                if not deps or all(d in completed_set for d in deps):
                    ordered_sequence.append(st_data)
                    completed_set.add(st_id)
                    del pending[st_id]
            iters += 1

        # Fallback if graphs couldn't resolve
        if pending:
            logger.warning(
                f"Planner could not resolve dependencies for {len(pending)} nodes. Forcing them to end of sequence."
            )
            for _, st_data in pending.items():
                ordered_sequence.append(st_data)

        # Build the final execution schema
        execution_plan = {
            "plan_id": f"plan_{enriched_task.get('task_id')}",
            "task_id": enriched_task.get("task_id"),
            "original_intent": enriched_task.get("original_intent"),
            "memory_context": enriched_task.get("memory_context", []),
            "execution_sequence": ordered_sequence,
        }

        logger.debug(
            f"Generated Execution Plan {execution_plan['plan_id']} with {len(ordered_sequence)} steps."
        )
        return execution_plan
