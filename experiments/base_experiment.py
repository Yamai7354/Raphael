import abc
from typing import Any, Dict
from uuid import uuid4


class BaseExperiment(abc.ABC):
    """
    Abstract base class for Swarm Experiments.
    Experiments are sandboxed workloads that the Swarm Director can
    deploy during idle time to train agents, gather performance metrics,
    and discover optimal Habitat Blueprints.
    """

    def __init__(self, name: str, description: str, difficulty: int = 1):
        self.experiment_id = str(uuid4())
        self.name = name
        self.description = description
        self.difficulty = difficulty  # 1 (Easy) to 10 (Complex)

    @abc.abstractmethod
    async def generate_workload_payload(self) -> Dict[str, Any]:
        """
        Produce a mock task payload that looks identical to a real user request.
        Example: {"prompt": "Solve this equation: 2x + 5 = 15", "type": "math"}
        """
        pass

    @abc.abstractmethod
    async def evaluate_result(self, result: Dict[str, Any]) -> float:
        """
        Given the result from the habitat, determine a success score (0.0 to 1.0).
        This score is fed back into HabitatMetrics to optimize future blueprints.
        """
        pass

    def as_task_request(self) -> Dict[str, Any]:
        """Format the experiment into a standard Task queue item."""
        return {
            "task_id": f"exp-{self.experiment_id}",
            "description": f"Experiment: {self.name}",
            "priority": 1,  # Lowest priority so real user tasks preempt experiments
            "metadata": {
                "is_experiment": True,
                "experiment_class": self.__class__.__name__,
                "difficulty": self.difficulty,
            },
        }
