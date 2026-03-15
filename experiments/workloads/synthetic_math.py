import random
from typing import Any, Dict
from experiments.base_experiment import BaseExperiment


class SyntheticMathExperiment(BaseExperiment):
    """
    A simple synthetic workload that asks the Swarm to compute
    basic algebraic equations. Useful for testing basic reasoning
    and ensuring the Coder/Planner agents are working correctly
    without consuming heavy compute.
    """

    def __init__(self):
        super().__init__(
            name="Synthetic Math Benchmark",
            description="Evaluates agents' ability to parse and solve linear equations.",
            difficulty=2,
        )
        self.current_equation = ""
        self.expected_answer = 0.0

    async def generate_workload_payload(self) -> Dict[str, Any]:
        # Generate random linear equation: a * x + b = c
        a = random.randint(2, 10)
        b = random.randint(1, 20)
        x = random.randint(1, 50)
        c = (a * x) + b

        self.current_equation = f"{a} * x + {b} = {c}"
        self.expected_answer = float(x)

        return {
            "prompt": f"Solve for x given the equation: {self.current_equation}. Return only the numeric value of x.",
            "type": "math_reasoning",
            "constraints": ["Return ONLY numbers, no markdown or text."],
        }

    async def evaluate_result(self, result: Dict[str, Any]) -> float:
        """Score the agent's math output."""
        try:
            # Check if the agent's output exactly matches our expected 'x'
            agent_answer_str = str(result.get("output", "")).strip()
            agent_answer = float(agent_answer_str)

            if abs(agent_answer - self.expected_answer) < 0.01:
                return 1.0  # Perfect score
            return 0.0  # Wrong answer
        except ValueError:
            # Agent returned text instead of just a number
            return 0.0
