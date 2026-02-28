import pytest
import asyncio
from src.raphael.research.curiosity import CuriosityEngine
from src.raphael.research.hypothesis import HypothesisGenerator
from src.raphael.research.designer import ExperimentDesigner


def test_curiosity_engine():
    engine = CuriosityEngine()

    # Should identify the two mock domains below 0.5 confidence
    gaps = engine.scan_for_gaps()
    assert len(gaps) == 2

    # Highest priority should be first (rust_compilation has 0.1 confidence = 0.9 priority)
    assert gaps[0]["topic"] == "rust_compilation"
    assert gaps[0]["priority"] == 0.9

    assert gaps[1]["topic"] == "network_latency"
    assert gaps[1]["priority"] == 0.8


def test_hypothesis_generator():
    generator = HypothesisGenerator()

    mock_gap = {"topic": "rust_compilation", "priority": 0.9}

    hypothesis = generator.generate(mock_gap)
    assert hypothesis["source_topic"] == "rust_compilation"
    assert "exit_code == 0" in hypothesis["expected_outcome"]
    assert len(hypothesis["test_variables"]) == 3


def test_experiment_designer():
    designer = ExperimentDesigner()

    mock_hypothesis = {
        "source_topic": "rust_compilation",
        "claim": "Will compile successfully",
        "expected_outcome": "exit_code == 0",
    }

    experiment = designer.design_experiment(mock_hypothesis)

    # Must enforce sandbox logic
    assert experiment["requires_sandbox"] is True

    # Must generate the task sequence
    assert len(experiment["tasks"]) == 2
    assert experiment["tasks"][0]["capability_required"] == "bash"
    assert experiment["tasks"][1]["capability_required"] == "reasoning"
    assert experiment["tasks"][1]["context"]["isolated_execution"] is True


async def run_all_tests():
    print("Running Research Layer 11 tests natively...")

    test_curiosity_engine()
    print("test_curiosity_engine: PASSED")

    test_hypothesis_generator()
    print("test_hypothesis_generator: PASSED")

    test_experiment_designer()
    print("test_experiment_designer: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
