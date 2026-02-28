"""
LM Studio Role Runtime Adapter for AI Router.

Translates role + selected model into LM Studio load parameters.
Applies quantization policy, context cap, and decoding defaults.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any
import httpx

from .roles import AgentRole
from .model_mapping import ModelSpec
from .policy import policy_registry

logger = logging.getLogger("ai_router.lmstudio_adapter")


@dataclass
class LoadParameters:
    """Parameters for loading a model in LM Studio."""

    model_path: str
    context_length: int
    gpu_layers: int = -1  # -1 = auto
    temperature: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model_path,
            "context_length": self.context_length,
            "n_gpu_layers": self.gpu_layers,
        }


class LMStudioAdapter:
    """
    Adapter for LM Studio API operations.
    Serializes load/unload operations.
    """

    def __init__(self):
        self._loading = False  # Serialization lock (simplified)

    def build_load_params(
        self, role: AgentRole, model_spec: ModelSpec, node_max_context: int
    ) -> LoadParameters:
        """
        Build load parameters from role and model spec.
        Applies policy constraints.
        """
        # Determine effective context (minimum of role, model, node, global)
        policy = policy_registry.policy
        effective_context = min(
            role.max_context_tokens,
            model_spec.context_length,
            node_max_context,
            policy.global_max_context_tokens,
        )

        params = LoadParameters(
            model_path=model_spec.model_id,
            context_length=effective_context,
            temperature=role.default_temperature,
        )

        logger.info(
            "load_params_built role=%s model=%s context=%d temp=%.2f",
            role.role_id,
            model_spec.model_id,
            effective_context,
            role.default_temperature,
        )

        return params

    async def load_model(
        self, node_url: str, params: LoadParameters, timeout: float = 60.0
    ) -> tuple[bool, str]:
        """
        Load a model on a node via LM Studio API.
        Returns (success, message).
        """
        if self._loading:
            return (False, "Another load operation in progress")

        self._loading = True
        try:
            # LM Studio uses POST /lms/load for loading models
            url = f"{node_url.rstrip('/')}/lms/load"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=params.to_dict(),
                    timeout=timeout,
                )

                if response.status_code == 200:
                    logger.info(
                        "model_loaded model=%s node=%s", params.model_path, node_url
                    )
                    return (True, "Model loaded successfully")
                else:
                    error = f"Load failed: HTTP {response.status_code}"
                    logger.error(
                        "model_load_failed model=%s node=%s error=%s",
                        params.model_path,
                        node_url,
                        error,
                    )
                    return (False, error)

        except httpx.TimeoutException:
            logger.error(
                "model_load_timeout model=%s node=%s", params.model_path, node_url
            )
            return (False, "Load operation timed out")
        except Exception as e:
            logger.error(
                "model_load_exception model=%s node=%s error=%s",
                params.model_path,
                node_url,
                type(e).__name__,
            )
            return (False, f"Load exception: {type(e).__name__}")
        finally:
            self._loading = False

    async def unload_model(
        self, node_url: str, model_id: str, timeout: float = 30.0
    ) -> tuple[bool, str]:
        """
        Unload a model from a node via LM Studio API.
        Returns (success, message).
        """
        try:
            url = f"{node_url.rstrip('/')}/lms/unload"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={"model": model_id},
                    timeout=timeout,
                )

                if response.status_code == 200:
                    logger.info("model_unloaded model=%s node=%s", model_id, node_url)
                    return (True, "Model unloaded successfully")
                else:
                    logger.warning(
                        "model_unload_failed model=%s status=%d",
                        model_id,
                        response.status_code,
                    )
                    return (False, f"Unload failed: HTTP {response.status_code}")

        except Exception as e:
            logger.error(
                "model_unload_exception model=%s error=%s", model_id, type(e).__name__
            )
            return (False, f"Unload exception: {type(e).__name__}")

    async def get_loaded_models(self, node_url: str, timeout: float = 5.0) -> list[str]:
        """
        Get list of currently loaded models on a node.
        Returns empty list on failure.
        """
        try:
            url = f"{node_url.rstrip('/')}/models"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=timeout)

                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    return models
                return []

        except Exception as e:
            logger.debug(
                "get_loaded_models_failed node=%s error=%s", node_url, type(e).__name__
            )
            return []


# Global singleton instance
lmstudio_adapter = LMStudioAdapter()
