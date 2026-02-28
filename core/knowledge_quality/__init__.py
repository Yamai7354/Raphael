"""
Knowledge Quality & Trust Framework — core/knowledge_quality package.

Evaluates, scores, validates, and maintains the quality of knowledge
stored in the swarm's memory and embeddings.
"""

from .quality_scoring import QualityScoringEngine, QualityScore
from .evidence_tracker import EvidenceTracker, Evidence
from .contradiction_detector import ContradictionDetector, Contradiction
from .validation_pipeline import ValidationPipeline, ValidationRecord
from .noise_reduction import NoiseReduction
from .lifecycle_manager import LifecycleManager, KnowledgeState
from .agent_reputation import AgentReputationSystem, ReputationRecord
from .embedding_filter import EmbeddingQualityFilter
from .confidence_propagation import ConfidencePropagation
from .review_agents import ReviewAgentManager, ReviewTask
from .quality_dashboard import QualityDashboard
from .redundancy_detector import RedundancyDetector
from .drift_monitor import DriftMonitor
from .value_scoring import LongTermValueScorer
from .promotion_pipeline import PromotionPipeline, PromotionStage, PromotionCriteria
from .research_event_processor import ResearchEventProcessor, ResearchEvent
from .self_healing import SelfHealingScheduler

__all__ = [
    "QualityScoringEngine",
    "QualityScore",
    "EvidenceTracker",
    "Evidence",
    "ContradictionDetector",
    "Contradiction",
    "ValidationPipeline",
    "ValidationRecord",
    "NoiseReduction",
    "LifecycleManager",
    "KnowledgeState",
    "AgentReputationSystem",
    "ReputationRecord",
    "EmbeddingQualityFilter",
    "ConfidencePropagation",
    "ReviewAgentManager",
    "ReviewTask",
    "QualityDashboard",
    "RedundancyDetector",
    "DriftMonitor",
    "LongTermValueScorer",
    "PromotionPipeline",
    "PromotionStage",
    "PromotionCriteria",
    "ResearchEventProcessor",
    "ResearchEvent",
    "SelfHealingScheduler",
]
