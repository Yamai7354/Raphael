import logging
from typing import Dict, Any, List
import uuid

logger = logging.getLogger(__name__)


class ExperimentDesigner:
    """
    Takes a Hypothesis and constructs a pipeline of Task payloads
    intended for the Swarm Orchestrator. Safely forces them into a Sandbox.
    """

    def __init__(self):
        pass

    def design_experiment(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds a safe, sandboxed workflow out of a hypothesis.
        """
        topic = hypothesis.get("source_topic", "unknown")
        exp_id = f"exp-{uuid.uuid4().hex[:6]}"

        # Create the formal experiment workflow
        experiment = {
            "experiment_id": exp_id,
            "target_hypothesis": hypothesis,
            "requires_sandbox": True,  # CRITICAL: Layer 11 autonomous tasks must be sandboxed
            "tasks": [
                {
                    "task_id": f"{exp_id}-t1",
                    "capability_required": "bash",
                    "instruction": f"Run basic diagnostics for {topic}",
                    "context": {"isolated_execution": True},
                },
                {
                    "task_id": f"{exp_id}-t2",
                    "capability_required": "reasoning",
                    "instruction": f"Analyze diagnostics against expected outcome: {hypothesis.get('expected_outcome')}",
                    "context": {"isolated_execution": True},
                },
            ],
        }

        logger.info(f"Constructed experiment {exp_id} containing {len(experiment['tasks'])} tasks.")
        return experiment
