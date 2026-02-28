"""
Task Manager Adapter — Placeholder for external task/issue tracking integration.
"""

from typing import Dict, List


def task_manager_list_tasks(status: str = "open") -> Dict[str, str]:
    return {"status": "success", "tasks": "placeholder"}


def task_manager_create_task(title: str, description: str) -> Dict[str, str]:
    return {"status": "success", "task_id": "placeholder"}


TASK_MANAGER_TOOLS = {
    "task_manager_list_tasks": {
        "fn": task_manager_list_tasks,
        "description": "List tasks from external tracker",
        "permission": "read",
    },
    "task_manager_create_task": {
        "fn": task_manager_create_task,
        "description": "Create a new task in external tracker",
        "permission": "write",
    },
}


def get_tools() -> Dict[str, Dict]:
    return TASK_MANAGER_TOOLS


def list_tools() -> List[str]:
    return list(TASK_MANAGER_TOOLS.keys())
