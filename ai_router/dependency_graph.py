"""
Task Dependency Management for AI Router.

Provides DAG-based dependency tracking between tasks and subtasks.
Enforces execution order and detects cycles.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
from collections import deque

logger = logging.getLogger("ai_router.dependencies")


# =============================================================================
# DEPENDENCY TYPES
# =============================================================================


class DependencyType(str, Enum):
    """Types of dependencies."""

    TASK = "task"  # Task depends on another task
    SUBTASK = "subtask"  # Subtask depends on another subtask
    OUTPUT = "output"  # Depends on specific output key


@dataclass
class Dependency:
    """A single dependency declaration."""

    source_id: str  # The task/subtask that has the dependency
    target_id: str  # The task/subtask being depended on
    dependency_type: DependencyType
    output_key: Optional[str] = None  # Specific output key required

    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.dependency_type.value,
            "output_key": self.output_key,
        }


# =============================================================================
# DEPENDENCY GRAPH
# =============================================================================


class DependencyGraph:
    """
    DAG for tracking task/subtask dependencies.

    Nodes are task_ids or subtask_ids.
    Edges represent dependencies (source depends on target).
    """

    def __init__(self):
        self._graph: Dict[str, Set[str]] = {}  # node -> nodes it depends on
        self._reverse: Dict[str, Set[str]] = {}  # node -> nodes that depend on it
        self._dependencies: Dict[str, List[Dependency]] = {}  # detailed info

    def add_node(self, node_id: str) -> None:
        """Add a node to the graph."""
        if node_id not in self._graph:
            self._graph[node_id] = set()
            self._reverse[node_id] = set()

    def add_dependency(self, dep: Dependency) -> bool:
        """
        Add a dependency. Returns False if it would create a cycle.
        """
        self.add_node(dep.source_id)
        self.add_node(dep.target_id)

        # Check for cycle before adding
        if self._would_create_cycle(dep.source_id, dep.target_id):
            logger.warning(
                "dependency_cycle_detected source=%s target=%s",
                dep.source_id,
                dep.target_id,
            )
            return False

        # Add edge
        self._graph[dep.source_id].add(dep.target_id)
        self._reverse[dep.target_id].add(dep.source_id)

        # Store detailed info
        if dep.source_id not in self._dependencies:
            self._dependencies[dep.source_id] = []
        self._dependencies[dep.source_id].append(dep)

        logger.info(
            "dependency_added source=%s target=%s type=%s",
            dep.source_id,
            dep.target_id,
            dep.dependency_type.value,
        )
        return True

    def _would_create_cycle(self, source: str, target: str) -> bool:
        """Check if adding source->target would create a cycle."""
        # If target can reach source, adding source->target creates cycle
        visited = set()
        queue = deque([target])

        while queue:
            node = queue.popleft()
            if node == source:
                return True
            if node in visited:
                continue
            visited.add(node)

            for dep in self._graph.get(node, set()):
                queue.append(dep)

        return False

    def get_dependencies(self, node_id: str) -> List[str]:
        """Get nodes that this node depends on."""
        return list(self._graph.get(node_id, set()))

    def get_dependents(self, node_id: str) -> List[str]:
        """Get nodes that depend on this node."""
        return list(self._reverse.get(node_id, set()))

    def are_dependencies_satisfied(self, node_id: str, completed: Set[str]) -> bool:
        """Check if all dependencies for a node are satisfied."""
        deps = self._graph.get(node_id, set())
        return deps.issubset(completed)

    def get_ready_nodes(self, completed: Set[str]) -> List[str]:
        """Get all nodes whose dependencies are satisfied."""
        ready = []
        for node_id in self._graph:
            if node_id not in completed:
                if self.are_dependencies_satisfied(node_id, completed):
                    ready.append(node_id)
        return ready

    def topological_sort(self) -> List[str]:
        """
        Return nodes in topological order (dependencies first).
        Raises ValueError if graph has cycles.
        """
        in_degree = {node: len(deps) for node, deps in self._graph.items()}
        queue = deque([n for n, d in in_degree.items() if d == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            for dependent in self._reverse.get(node, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._graph):
            raise ValueError("Graph contains cycles")

        return result

    def get_execution_order(self) -> List[List[str]]:
        """
        Get execution order as levels (parallel batches).
        Each level can be executed in parallel.
        """
        levels: List[List[str]] = []
        completed: Set[str] = set()
        remaining = set(self._graph.keys())

        while remaining:
            level = []
            for node in remaining:
                if self.are_dependencies_satisfied(node, completed):
                    level.append(node)

            if not level:
                raise ValueError("Graph contains cycles or unsatisfied dependencies")

            levels.append(level)
            completed.update(level)
            remaining -= set(level)

        return levels

    def to_dict(self) -> Dict:
        """Export graph structure."""
        return {
            "nodes": list(self._graph.keys()),
            "edges": [
                {"from": src, "to": tgt}
                for src, targets in self._graph.items()
                for tgt in targets
            ],
            "dependencies": {
                node: [d.to_dict() for d in deps]
                for node, deps in self._dependencies.items()
            },
        }


# =============================================================================
# DEPENDENCY RESOLVER
# =============================================================================


class DependencyResolver:
    """
    Resolves dependencies for task execution.
    """

    def __init__(self):
        self._graphs: Dict[str, DependencyGraph] = {}  # task_id -> graph
        self._global_graph = DependencyGraph()  # cross-task dependencies

    def get_task_graph(self, task_id: str) -> DependencyGraph:
        """Get or create graph for a task."""
        if task_id not in self._graphs:
            self._graphs[task_id] = DependencyGraph()
        return self._graphs[task_id]

    def add_subtask_dependency(
        self,
        task_id: str,
        source_subtask: str,
        target_subtask: str,
        output_key: Optional[str] = None,
    ) -> bool:
        """Add dependency between subtasks in same task."""
        graph = self.get_task_graph(task_id)
        dep = Dependency(
            source_id=source_subtask,
            target_id=target_subtask,
            dependency_type=DependencyType.SUBTASK,
            output_key=output_key,
        )
        return graph.add_dependency(dep)

    def add_task_dependency(
        self,
        source_task: str,
        target_task: str,
    ) -> bool:
        """Add dependency between tasks."""
        dep = Dependency(
            source_id=source_task,
            target_id=target_task,
            dependency_type=DependencyType.TASK,
        )
        return self._global_graph.add_dependency(dep)

    def get_subtask_order(self, task_id: str) -> List[List[str]]:
        """Get subtask execution order for a task."""
        graph = self._graphs.get(task_id)
        if not graph:
            return []
        return graph.get_execution_order()

    def can_execute_subtask(
        self,
        task_id: str,
        subtask_id: str,
        completed: Set[str],
    ) -> bool:
        """Check if subtask can be executed."""
        graph = self._graphs.get(task_id)
        if not graph:
            return True  # No dependencies
        return graph.are_dependencies_satisfied(subtask_id, completed)

    def get_ready_subtasks(
        self,
        task_id: str,
        completed: Set[str],
    ) -> List[str]:
        """Get subtasks ready for execution."""
        graph = self._graphs.get(task_id)
        if not graph:
            return []
        return graph.get_ready_nodes(completed)


# Global singleton
dependency_resolver = DependencyResolver()
