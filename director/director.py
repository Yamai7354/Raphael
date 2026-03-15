"""
SwarmDirector — The top-level orchestration loop.

The Director continuously:
  1. Observes tasks from the TaskManager
  2. Queries the GraphReasoner for habitat blueprints
  3. Selects the best blueprint via HabitatSelector
  4. Deploys it via HelmController
  5. Monitors it via HabitatMonitor
  6. Cleans up after completion
"""

import asyncio
import logging

from graph.graph_api import Neo4jGraphStore
from director.graph_reasoner import GraphReasoner
from director.habitat_monitor import HabitatMonitor, HabitatRecord
from director.habitat_selector import HabitatSelector
from director.helm_controller import HelmController
from director.task_manager import SwarmTask, TaskManager, TaskState

logger = logging.getLogger("director")


class SwarmDirector:
    """
    The Swarm Director is the orchestration brain.

    It runs a continuous loop:
      observe → reason → select → deploy → monitor → destroy
    """

    def __init__(
        self,
        graph_store: Neo4jGraphStore,
        helm: HelmController,
        poll_interval: float = 5.0,
        monitor_interval: float = 30.0,
    ):
        self.task_manager = TaskManager()
        self.graph_reasoner = GraphReasoner(graph_store)
        self.habitat_selector = HabitatSelector()
        self.helm = helm
        self.monitor = HabitatMonitor(helm, check_interval=monitor_interval)

        self._poll_interval = poll_interval
        self._running = False
        self._graph = graph_store

    async def start(self):
        """Start the Director loop and monitor in parallel."""
        self._running = True
        logger.info("🚀 Swarm Director starting...")

        await asyncio.gather(
            self._director_loop(),
            self.monitor.run(),
        )

    async def stop(self):
        """Gracefully stop the Director."""
        self._running = False
        self.monitor.stop()
        logger.info("Swarm Director stopped.")

    async def submit_task(
        self, description: str, capabilities: list[str], priority: int = 5
    ) -> SwarmTask:
        """Submit a new task to the swarm."""
        task = SwarmTask(
            description=description,
            required_capabilities=capabilities,
            priority=priority,
        )
        await self.task_manager.submit(task)
        return task

    async def _director_loop(self):
        """Main orchestration loop."""
        logger.info("Director loop running...")

        while self._running:
            try:
                # 1. Observe — get next pending task
                task = await self.task_manager.next_task()
                if task is None:
                    await asyncio.sleep(self._poll_interval)
                    continue

                logger.info(f"Processing task: {task.id} — {task.description}")

                # 2. Reason — query graph for matching blueprints
                candidates = await self.graph_reasoner.find_blueprints_for_capabilities(
                    task.required_capabilities
                )

                if not candidates:
                    logger.warning(f"No blueprints found for task {task.id}")
                    self.task_manager.transition(
                        task.id, TaskState.FAILED, error="No matching habitat blueprints found"
                    )
                    continue

                # 3. Select — choose the best blueprint
                blueprint = self.habitat_selector.select(task, candidates)
                if not blueprint:
                    self.task_manager.transition(
                        task.id, TaskState.FAILED, error="Habitat selection failed"
                    )
                    continue

                # 4. Deploy — install the Helm chart
                release_name = f"habitat-{task.id[:8]}"
                success = await self.helm.install(
                    release_name=release_name,
                    chart_path=blueprint.helm_chart,
                    values_overrides={"habitat.name": f"{blueprint.name}-{task.id[:8]}"},
                )

                if not success:
                    self.task_manager.transition(
                        task.id,
                        TaskState.FAILED,
                        error=f"Helm install failed for {blueprint.helm_chart}",
                    )
                    continue

                # 5. Monitor — register for health tracking
                self.task_manager.transition(
                    task.id,
                    TaskState.RUNNING,
                    habitat_release=release_name,
                )

                record = HabitatRecord(
                    release_name=release_name,
                    blueprint_name=blueprint.name,
                    task_id=task.id,
                    ttl_seconds=3600,
                )
                self.monitor.register(record)

                # Record in graph for future learning
                # Create the Task node first
                await self._graph.store_node(
                    label="Task",
                    uuid=task.id,
                    memory_type="task",
                    properties={
                        "description": task.description,
                        "required_capabilities": ",".join(task.required_capabilities),
                        "priority": task.priority,
                        "state": task.state.value,
                    },
                )
                await self.graph_reasoner.record_task_solution(task.id, blueprint.name)

                logger.info(
                    f"✅ Task {task.id[:8]} → {blueprint.name} deployed as '{release_name}'"
                )

            except Exception as e:
                logger.error(f"Director loop error: {e}", exc_info=True)
                await asyncio.sleep(self._poll_interval)

    async def destroy_habitat(self, task_id: str):
        """Manually destroy a habitat for a given task."""
        task = self.task_manager.get_task(task_id)
        if not task or not task.habitat_release:
            return

        success = await self.helm.uninstall(task.habitat_release)
        if success:
            self.monitor.unregister(task.habitat_release)
            self.task_manager.transition(task_id, TaskState.COMPLETED)
            self.habitat_selector.update_performance(
                self.monitor.get_habitat(task.habitat_release).blueprint_name
                if self.monitor.get_habitat(task.habitat_release)
                else "unknown",
                success=True,
            )
            logger.info(f"Destroyed habitat for task {task_id}")

    @property
    def status_summary(self) -> dict:
        """Return a summary of the Director's current state."""
        return {
            "pending_tasks": len(self.task_manager.get_pending_tasks()),
            "running_tasks": len(self.task_manager.get_running_tasks()),
            "active_habitats": self.monitor.active_count,
            "running": self._running,
        }
