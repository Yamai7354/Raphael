"""
Role-to-Model Mapping Registry for AI Router.

Creates a mapping layer from roles → acceptable models.
Models are selected deterministically based on ordered preference lists.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from .roles import QuantizationPolicy

logger = logging.getLogger("ai_router.model_mapping")


@dataclass(frozen=True)
class ModelSpec:
    """
    Specification for a model that can fulfill a role.
    """

    model_id: str  # e.g., "qwen2.5-7B-instruct-q8"
    size: str  # e.g., "7B"
    quantization: QuantizationPolicy
    context_length: int


@dataclass
class RoleModelMapping:
    """
    Mapping from a role to its acceptable models (ordered by preference).
    """

    role_id: str
    models: List[ModelSpec]  # Ordered preference list (first = preferred)

    def get_preferred_model(self) -> Optional[ModelSpec]:
        """Get the most preferred model."""
        return self.models[0] if self.models else None

    def get_fallback_models(self) -> List[ModelSpec]:
        """Get fallback models (all except first)."""
        return self.models[1:] if len(self.models) > 1 else []

    def find_compatible_model(
        self, available_models: List[str], max_context: int
    ) -> Optional[ModelSpec]:
        """
        Find the first model that's available and fits within context limit.
        Returns None if no compatible model found.
        """
        for model_spec in self.models:
            if model_spec.model_id in available_models:
                if model_spec.context_length <= max_context:
                    return model_spec
                else:
                    logger.debug(
                        "model=%s context=%d exceeds limit=%d",
                        model_spec.model_id,
                        model_spec.context_length,
                        max_context,
                    )
        return None


class ModelMappingRegistry:
    """
    Registry of role-to-model mappings.
    Loaded at startup from config.
    """

    def __init__(self):
        self._mappings: Dict[str, RoleModelMapping] = {}
        self._loaded = False

    def load_from_config(self, mappings_config: List[dict]) -> None:
        """
        Load role-to-model mappings from configuration.
        """
        if self._loaded:
            raise RuntimeError("Mappings already loaded. Registry is immutable.")

        for mapping in mappings_config:
            role_id = mapping["role_id"]
            models_config = mapping.get("models", [])

            models = []
            for m in models_config:
                try:
                    quant = QuantizationPolicy(m.get("quantization", "any"))
                except ValueError:
                    raise ValueError(f"Invalid quantization for model {m['model_id']}")

                model_spec = ModelSpec(
                    model_id=m["model_id"],
                    size=m.get("size", "7B"),
                    quantization=quant,
                    context_length=m.get("context_length", 8192),
                )
                models.append(model_spec)

            self._mappings[role_id] = RoleModelMapping(
                role_id=role_id,
                models=models,
            )

            logger.info(
                "role_model_mapping_loaded role=%s model_count=%d preferred=%s",
                role_id,
                len(models),
                models[0].model_id if models else "none",
            )

        self._loaded = True
        logger.info(
            "model_mapping_registry_loaded total_mappings=%d", len(self._mappings)
        )

    def get_mapping(self, role_id: str) -> Optional[RoleModelMapping]:
        """Get the model mapping for a role."""
        return self._mappings.get(role_id)

    def select_model_for_role(
        self, role_id: str, available_models: List[str], max_context: int
    ) -> Optional[ModelSpec]:
        """
        Select the best available model for a role.
        Returns None if no compatible model is available.
        """
        mapping = self._mappings.get(role_id)
        if not mapping:
            logger.warning("role=%s has no model mapping", role_id)
            return None

        model = mapping.find_compatible_model(available_models, max_context)
        if model:
            logger.info(
                "model_selected role=%s model=%s size=%s",
                role_id,
                model.model_id,
                model.size,
            )
        else:
            logger.warning(
                "role=%s no_compatible_model available=%s", role_id, available_models
            )
        return model

    def is_loaded(self) -> bool:
        """Check if mappings have been loaded."""
        return self._loaded


# Global singleton instance
model_mapping_registry = ModelMappingRegistry()
