# Swarm Experiments

The **Experiments** layer (`experiments/`) is the foundation for the Swarm's autonomous self-improvement cycle.

## Overview

When the primary task queue in the Swarm Director falls below the `idle_threshold`, the `ExperimentScheduler` activates. Instead of wasting idle compute cycles, the Director injects sandboxed, synthetic workloads (Experiments) into the system.

## Anatomy of an Experiment

All workloads inherit from `BaseExperiment` (`experiments/base_experiment.py`). 

An experiment must define:
1. `generate_workload_payload()`: Creates a mock user request payload (e.g., a math problem or a synthetic coding prompt).
2. `evaluate_result()`: Definitively scores the output produced by the spawned Habitat (0.0 to 1.0).

## Current Workloads

### `SyntheticMathExperiment`
Feeds randomized algebraic equations to the swarm, enforcing constraints like "Return ONLY numbers." This cheaply tests the Planner and Coder agents' ability to reason and strictly follow output constraints.

## The Evolution Cycle

1. **Schedule**: `ExperimentScheduler` sees idle time and injects `SyntheticMathExperiment`.
2. **Execute**: The Director spawns a `coding-habitat` to solve it.
3. **Score**: The Experiment scores the answer resulting in a success/fail.
4. **Learn**: `HabitatMetrics` and `HabitatEvolver` record the outcome in the Neo4j Knowledge Graph. If the habitat succeeded quickly and cheaply, the Blueprint is promoted. If it failed, the Evolver proposes a mutation (e.g., adding a reviewer agent).
