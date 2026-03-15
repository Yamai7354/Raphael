import asyncio
import logging
import random
from typing import List, Optional

from experiments.base_experiment import BaseExperiment
from experiments.workloads.synthetic_math import SyntheticMathExperiment

logger = logging.getLogger("experiments.scheduler")


class ExperimentScheduler:
    """
    Manages the lifecycle of autonomous performance experiments.
    When the Swarm Director's primary Task Queue falls below a certain
    threshold, this scheduler injects synthetic simulated workloads to
    verify agent integrity and train optimization models on the resulting metrics.
    """

    def __init__(self, check_interval_seconds: int = 60, idle_threshold: int = 5):
        self._interval = check_interval_seconds
        self._threshold = idle_threshold
        self._running = False

        # Registry of available synthetic workloads
        self.available_experiments: List[BaseExperiment] = [
            SyntheticMathExperiment(),
            # Add more benchmark classes here (e.g., CodeDebuggingExperiment, NetworkAuditExperiment)
        ]

    async def start(self, task_queue):
        """Begin polling for idle time."""
        self._running = True
        logger.info("ExperimentScheduler started. Monitoring queue for idle time.")
        asyncio.create_task(self._poll_loop(task_queue))

    def stop(self):
        """Halt the autonomous experiment generation."""
        self._running = False

    async def _poll_loop(self, task_queue):
        while self._running:
            try:
                # E.g., qsize = await task_queue.qsize() (Assuming an asyncio.Queue or Redis proxy)
                qsize = 0  # Placeholder for actual queue size lookup

                if qsize < self._threshold:
                    logger.debug(
                        f"Queue below threshold ({qsize}/{self._threshold}). Injecting experiment."
                    )
                    await self._inject_random_experiment(task_queue)

            except Exception as e:
                logger.error(f"ExperimentScheduler error: {e}")

            await asyncio.sleep(self._interval)

    async def _inject_random_experiment(self, task_queue):
        """Picks a random synthetic workload and pushes it to the swarm."""
        if not self.available_experiments:
            return

        experiment = random.choice(self.available_experiments)

        # In a real scenario, this payload goes to the Event Bus (TASK_CREATED)
        # or pushed directly onto the Redis queue.
        payload = experiment.as_task_request()

        logger.info(
            f"Injecting autonomous experiment workload: {experiment.name} (ID: {experiment.experiment_id})"
        )
        # await task_queue.put(payload)
