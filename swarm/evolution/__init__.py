"""
Swarm Evolution Framework — Package init.

Provides agent evolution, fitness scoring, reputation tracking,
population control, mutation strategies, task markets, and more.
"""

from .dna import AgentDNA
from .fitness import FitnessScorer, FitnessScore
from .reputation import ReputationTracker
from .population import PopulationController
from .mutation import MutationEngine
from .engine import EvolutionCycleEngine
from .task_market import TaskMarket
from .collective_intel import CollectiveIntelligence
from .vision import SwarmVision
from .monitor import CentralIntelligenceMonitor
from .consolidation import KnowledgeConsolidator
from .discovery_economy import DiscoveryEconomy
from .idle_regulation import IdleRegulator

__all__ = [
    "AgentDNA",
    "FitnessScorer",
    "FitnessScore",
    "ReputationTracker",
    "PopulationController",
    "MutationEngine",
    "EvolutionCycleEngine",
    "TaskMarket",
    "CollectiveIntelligence",
    "SwarmVision",
    "CentralIntelligenceMonitor",
    "KnowledgeConsolidator",
    "DiscoveryEconomy",
    "IdleRegulator",
]
