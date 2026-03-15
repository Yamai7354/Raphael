"""
Node Registry — registry-aware model discovery for multi-node clusters.

Prevents cross-registry model pulls by querying each node's native API
and enforcing pinned-model protection.

Desktop-node (LM Studio): GET {url}/v1/models  → OpenAI-compatible listing
Mac-node     (Ollama):     GET {url}/api/tags   → Ollama-native listing
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("ai_router.node_registry")

# ---------------------------------------------------------------------------
# Supported registry types
# ---------------------------------------------------------------------------
REGISTRY_LMSTUDIO = "lmstudio"
REGISTRY_OLLAMA = "ollama"


@dataclass
class NodeRegistryEntry:
    """Snapshot of a node's registry state."""

    node_id: str
    registry_type: str  # "lmstudio" | "ollama"
    base_url: str  # e.g. "http://100.125.58.22:5000" (no trailing /v1)
    pinned_models: tuple[str, ...] = ()
    discovered_models: list[str] = field(default_factory=list)
    memory_budget_mb: int = 0
    vram_budget_mb: int = 0
    max_model_size_gb: int = 0


class NodeRegistry:
    """
    Registry-aware model catalogue.

    * Queries each node using its *native* API only.
    * Validates that model IDs are never cross-pulled between registries.
    * Protects pinned (embedding) models from being swapped out.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, NodeRegistryEntry] = {}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def load_from_config(self, nodes_config: list[dict]) -> None:
        """Populate the registry from the `nodes` section of config.json."""
        for node in nodes_config:
            node_id = node["id"]
            raw_url = node.get("url", "")
            # Strip /v1 suffix if present — we want the bare base URL.
            base_url = raw_url.rstrip("/")
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]

            caps = node.get("capabilities", {})

            entry = NodeRegistryEntry(
                node_id=node_id,
                registry_type=node.get("registry_type", REGISTRY_OLLAMA),
                base_url=base_url,
                pinned_models=tuple(node.get("pinned_models", [])),
                memory_budget_mb=caps.get("memory_budget_mb", 0),
                vram_budget_mb=caps.get("vram_budget_mb", 0),
                max_model_size_gb=caps.get("max_model_size_gb", 0),
            )
            self._nodes[node_id] = entry
            logger.info(
                "node_registry_loaded node_id=%s type=%s pinned=%s",
                node_id,
                entry.registry_type,
                entry.pinned_models,
            )

    # ------------------------------------------------------------------
    # Model discovery  (registry-specific API calls)
    # ------------------------------------------------------------------

    async def refresh_models(self, node_id: str, timeout: float = 8.0) -> list[str]:
        """
        Query the node's native model-listing endpoint and cache results.

        * LM Studio  → GET {base}/v1/models  (OpenAI format)
        * Ollama     → GET {base}/api/tags    (Ollama format)
        """
        entry = self._nodes.get(node_id)
        if not entry:
            logger.warning("refresh_models: unknown node_id=%s", node_id)
            return []

        models: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if entry.registry_type == REGISTRY_LMSTUDIO:
                    models = await self._list_lmstudio(client, entry.base_url)
                elif entry.registry_type == REGISTRY_OLLAMA:
                    models = await self._list_ollama(client, entry.base_url)
                else:
                    logger.error(
                        "Unknown registry_type=%s for node=%s",
                        entry.registry_type,
                        node_id,
                    )
        except Exception as e:
            logger.error("refresh_models failed node_id=%s error=%s", node_id, e)

        entry.discovered_models = models
        logger.info(
            "node_models_refreshed node_id=%s count=%d models=%s",
            node_id,
            len(models),
            models,
        )
        return models

    async def refresh_all(self, timeout: float = 8.0) -> dict[str, list[str]]:
        """Refresh models on every registered node."""
        results: dict[str, list[str]] = {}
        for node_id in self._nodes:
            results[node_id] = await self.refresh_models(node_id, timeout)
        return results

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def get_entry(self, node_id: str) -> Optional[NodeRegistryEntry]:
        return self._nodes.get(node_id)

    def get_pinned_models(self, node_id: str) -> tuple[str, ...]:
        entry = self._nodes.get(node_id)
        return entry.pinned_models if entry else ()

    def is_model_swappable(self, model_id: str, node_id: str) -> bool:
        """True if the model is NOT pinned on this node (safe to unload)."""
        entry = self._nodes.get(node_id)
        if not entry:
            return False
        return model_id not in entry.pinned_models

    def validate_model_for_node(self, model_id: str, node_id: str) -> tuple[bool, str]:
        """
        Check whether *model_id* belongs to *node_id*'s registry.

        Returns ``(True, reason)`` if valid, ``(False, reason)`` otherwise.
        """
        entry = self._nodes.get(node_id)
        if not entry:
            return False, f"Node {node_id} not registered"

        if model_id in entry.discovered_models:
            return True, "model_found_in_registry"

        if model_id in entry.pinned_models:
            return True, "model_is_pinned"

        # Cross-registry guard: check if this model exists on a *different* node
        for other_id, other_entry in self._nodes.items():
            if other_id == node_id:
                continue
            if model_id in other_entry.discovered_models or model_id in other_entry.pinned_models:
                return (
                    False,
                    f"Model '{model_id}' belongs to {other_id} "
                    f"({other_entry.registry_type}), not {node_id} "
                    f"({entry.registry_type}). Cross-registry pull blocked.",
                )

        return False, f"Model '{model_id}' not found in any registry"

    def can_fit_model(self, model_size_gb: float, node_id: str) -> tuple[bool, str]:
        """Check whether the node has enough VRAM budget for the model."""
        entry = self._nodes.get(node_id)
        if not entry:
            return False, f"Node {node_id} not registered"
        if entry.max_model_size_gb and model_size_gb > entry.max_model_size_gb:
            return (
                False,
                f"Model {model_size_gb} GB exceeds node budget ({entry.max_model_size_gb} GB max)",
            )
        return True, "within_budget"

    def get_all_node_ids(self) -> list[str]:
        return list(self._nodes.keys())

    def get_nodes_for_registry_type(self, registry_type: str) -> list[str]:
        """Return node IDs that run the given registry type."""
        return [nid for nid, entry in self._nodes.items() if entry.registry_type == registry_type]

    # ------------------------------------------------------------------
    # Private API helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _list_lmstudio(client: httpx.AsyncClient, base_url: str) -> list[str]:
        """LM Studio: OpenAI-compatible GET /v1/models."""
        url = f"{base_url}/v1/models"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        rows = data.get("data", []) if isinstance(data, dict) else []
        models = [
            str(r.get("id", "")).strip()
            for r in rows
            if isinstance(r, dict) and str(r.get("id", "")).strip()
        ]
        return models

    @staticmethod
    async def _list_ollama(client: httpx.AsyncClient, base_url: str) -> list[str]:
        """Ollama: GET /api/tags."""
        url = f"{base_url}/api/tags"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        model_list = data.get("models", []) if isinstance(data, dict) else []
        models = [
            str(m.get("name", "")).strip()
            for m in model_list
            if isinstance(m, dict) and str(m.get("name", "")).strip()
        ]
        return models


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
node_registry = NodeRegistry()
