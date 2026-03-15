"""
Shared data models for the Swarm Director.

Kept separate from modules to avoid import cycles with neo4j.
"""

from dataclasses import dataclass


@dataclass
class BlueprintCandidate:
    """A habitat blueprint that could solve a task."""

    name: str
    helm_chart: str
    recommended_agents: int
    capabilities: list[str]
    agents: list[dict]  # [{name, count, role}]
    services: list[str]
    score: float = 0.0  # relevance score
