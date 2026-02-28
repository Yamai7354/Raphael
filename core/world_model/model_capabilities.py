"""
WORLD-403 — Model Capability Mapping.

Tracks LLMs, embedding models, and specialized models.
Includes size, hardware requirements, specialization,
latency metrics, and performance benchmarks.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("core.world_model.model_capabilities")


class ModelSpecialization(str, Enum):
    GENERAL = "general"
    CODING = "coding"
    REASONING = "reasoning"
    EMBEDDING = "embedding"
    VISION = "vision"
    CREATIVE = "creative"
    MATH = "math"
    INSTRUCTION = "instruction"


@dataclass
class ModelRecord:
    """A model available in the swarm."""

    model_id: str = field(default_factory=lambda: f"model_{uuid.uuid4().hex[:8]}")
    name: str = ""
    family: str = ""  # llama, mistral, phi, etc.
    parameter_count: str = ""  # e.g. "8B", "70B"
    quantization: str = ""  # e.g. "Q4_K_M", "FP16"
    specializations: list[ModelSpecialization] = field(default_factory=list)
    min_vram_gb: float = 0.0
    min_ram_gb: float = 0.0
    context_length: int = 4096
    avg_latency_ms: float = 0.0
    tokens_per_second: float = 0.0
    benchmark_scores: dict = field(default_factory=dict)
    hosted_on: list[str] = field(default_factory=list)  # machine hostnames
    available: bool = True
    registered_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "family": self.family,
            "params": self.parameter_count,
            "quant": self.quantization,
            "specializations": [s.value for s in self.specializations],
            "min_vram_gb": self.min_vram_gb,
            "context": self.context_length,
            "latency_ms": round(self.avg_latency_ms, 1),
            "tps": round(self.tokens_per_second, 1),
            "hosted_on": self.hosted_on,
            "available": self.available,
        }


class ModelCapabilityMap:
    """Registry of all models with capability-based querying."""

    def __init__(self):
        self._models: dict[str, ModelRecord] = {}
        self._by_name: dict[str, str] = {}

    def register(self, name: str, **kwargs) -> ModelRecord:
        if name in self._by_name:
            m = self._models[self._by_name[name]]
            for k, v in kwargs.items():
                if hasattr(m, k):
                    setattr(m, k, v)
            return m

        m = ModelRecord(name=name, **kwargs)
        self._models[m.model_id] = m
        self._by_name[name] = m.model_id
        logger.info(
            "model_registered name=%s params=%s specs=%s",
            name,
            m.parameter_count,
            [s.value for s in m.specializations],
        )
        return m

    def find_best_for_task(
        self, task_type: str, max_vram_gb: float | None = None
    ) -> ModelRecord | None:
        """Find the best model for a given task type."""
        spec_map = {
            "code": ModelSpecialization.CODING,
            "reasoning": ModelSpecialization.REASONING,
            "embedding": ModelSpecialization.EMBEDDING,
            "vision": ModelSpecialization.VISION,
            "creative": ModelSpecialization.CREATIVE,
            "math": ModelSpecialization.MATH,
        }
        target = spec_map.get(task_type.lower(), ModelSpecialization.GENERAL)

        candidates = [
            m
            for m in self._models.values()
            if m.available
            and target in m.specializations
            and (max_vram_gb is None or m.min_vram_gb <= max_vram_gb)
        ]
        if not candidates:
            # Fallback to general models
            candidates = [m for m in self._models.values() if m.available]

        if not candidates:
            return None

        # Sort by tokens/sec (higher is better)
        candidates.sort(key=lambda m: m.tokens_per_second, reverse=True)
        return candidates[0]

    def get_by_specialization(self, spec: ModelSpecialization) -> list[ModelRecord]:
        return [m for m in self._models.values() if spec in m.specializations and m.available]

    def get_by_host(self, hostname: str) -> list[ModelRecord]:
        return [m for m in self._models.values() if hostname in m.hosted_on]

    def update_latency(self, name: str, latency_ms: float, tps: float) -> None:
        mid = self._by_name.get(name)
        if mid and mid in self._models:
            m = self._models[mid]
            # Exponential moving average
            m.avg_latency_ms = (
                m.avg_latency_ms * 0.7 + latency_ms * 0.3 if m.avg_latency_ms else latency_ms
            )
            m.tokens_per_second = (
                m.tokens_per_second * 0.7 + tps * 0.3 if m.tokens_per_second else tps
            )

    def get_all(self) -> list[dict]:
        return [m.to_dict() for m in self._models.values()]

    def get_stats(self) -> dict:
        available = [m for m in self._models.values() if m.available]
        specs: dict[str, int] = {}
        for m in available:
            for s in m.specializations:
                specs[s.value] = specs.get(s.value, 0) + 1
        return {
            "total_models": len(self._models),
            "available": len(available),
            "by_specialization": specs,
        }
