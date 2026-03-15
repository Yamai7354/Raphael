"""
Node Capabilities for AI Router.

Nodes declare what roles they can safely host based on their
hardware capabilities (context size, model sizes, quantizations).
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from .roles import QuantizationPolicy, AgentRole

logger = logging.getLogger("ai_router.capabilities")


@dataclass(frozen=True)
class NodeCapabilities:
    """
    Immutable declaration of a node's hardware capabilities.
    Used to determine if a node can safely host a role.
    """

    node_id: str
    max_context_supported: int  # Maximum context tokens the node can handle
    supported_model_sizes: tuple  # e.g., ("3B", "7B", "13B")
    supported_quantizations: tuple  # e.g., (Q4_ONLY, Q8_ONLY, Q8_OR_HIGHER)
    concurrent_role_limit: int = 1  # How many roles can run simultaneously
    hosted_models: tuple = ()  # List of model IDs available on the node
    registry_type: str = "ollama"  # "ollama" or "lmstudio"
    pinned_models: tuple = ()  # Models that must stay loaded (embeddings)
    memory_budget_mb: int = 0  # Total system RAM available (MB)
    vram_budget_mb: int = 0  # Total VRAM available (MB)
    max_model_size_gb: int = 0  # Largest single model that can be loaded (GB)

    def can_host_model(self, model_id: str) -> bool:
        """Check if the node has the specific model available."""
        return model_id in self.hosted_models

    def can_fit_model(self, model_size_gb: float) -> tuple[bool, str]:
        """Check whether the node has enough VRAM budget for the model."""
        if self.max_model_size_gb and model_size_gb > self.max_model_size_gb:
            return (
                False,
                f"Model {model_size_gb} GB exceeds node budget ({self.max_model_size_gb} GB max)",
            )
        return True, "within_budget"

    def is_model_pinned(self, model_id: str) -> bool:
        """True if this model must not be unloaded (e.g. embedding model)."""
        return model_id in self.pinned_models

    def can_host_role(self, role: AgentRole) -> tuple[bool, str]:
        """
        Check if this node can safely host the given role.
        Returns (can_host, reason).
        """
        # Check context limit
        if role.max_context_tokens > self.max_context_supported:
            return (
                False,
                f"Role requires {role.max_context_tokens} context, "
                f"node supports max {self.max_context_supported}",
            )

        # Check model size
        if role.preferred_model_size_max not in self.supported_model_sizes:
            return (
                False,
                f"Role prefers {role.preferred_model_size_max} model, "
                f"node supports {self.supported_model_sizes}",
            )

        # Check quantization compatibility
        if not self._quant_compatible(role.quantization_policy):
            return (
                False,
                f"Role requires {role.quantization_policy.value} quantization, "
                f"node supports {[q.value for q in self.supported_quantizations]}",
            )

        return (True, "compatible")

    def _quant_compatible(self, role_quant: QuantizationPolicy) -> bool:
        """Check if node supports the role's quantization policy."""
        # ANY matches anything
        if role_quant == QuantizationPolicy.ANY:
            return True

        # Specific policy must be in supported list
        if role_quant in self.supported_quantizations:
            return True

        # Q8_OR_HIGHER is satisfied by Q8_ONLY or FP16_ONLY
        if role_quant == QuantizationPolicy.Q8_OR_HIGHER:
            return (
                QuantizationPolicy.Q8_ONLY in self.supported_quantizations
                or QuantizationPolicy.FP16_ONLY in self.supported_quantizations
                or QuantizationPolicy.Q8_OR_HIGHER in self.supported_quantizations
            )

        return False


class CapabilityRegistry:
    """
    Registry of all node capabilities.
    Loaded at startup from config.
    """

    def __init__(self):
        self._capabilities: dict[str, NodeCapabilities] = {}
        self._loaded = False

    def register_node(self, caps: NodeCapabilities) -> None:
        """Register capability for a single node (dynamic)."""
        self._capabilities[caps.node_id] = caps
        logger.info("node_capability_registered node_id=%s", caps.node_id)

    def load_from_config(self, nodes_config: List[dict]) -> None:
        """
        Load capabilities from node configuration.
        Each node in config should have a 'capabilities' section.
        """
        if self._loaded:
            raise RuntimeError("Capabilities already loaded. Registry is immutable.")

        for node in nodes_config:
            node_id = node["id"]
            caps_config = node.get("capabilities", {})

            if not caps_config:
                logger.warning("node_id=%s has no capabilities defined, using defaults", node_id)
                caps_config = {}

            # Parse quantizations
            quant_strs = caps_config.get("supported_quantizations", ["any"])
            try:
                quants = tuple(QuantizationPolicy(q) for q in quant_strs)
            except ValueError as e:
                raise ValueError(f"Invalid quantization for node {node_id}: {e}")

            caps = NodeCapabilities(
                node_id=node_id,
                max_context_supported=caps_config.get("max_context_supported", 32768),
                supported_model_sizes=tuple(caps_config.get("supported_model_sizes", ["7B"])),
                supported_quantizations=quants,
                concurrent_role_limit=caps_config.get("concurrent_role_limit", 1),
                registry_type=node.get("registry_type", "ollama"),
                pinned_models=tuple(node.get("pinned_models", [])),
                memory_budget_mb=caps_config.get("memory_budget_mb", 0),
                vram_budget_mb=caps_config.get("vram_budget_mb", 0),
                max_model_size_gb=caps_config.get("max_model_size_gb", 0),
            )

            self._capabilities[node_id] = caps
            logger.info(
                "node_capabilities_loaded node_id=%s max_context=%d model_sizes=%s",
                node_id,
                caps.max_context_supported,
                caps.supported_model_sizes,
            )

        self._loaded = True
        logger.info("capability_registry_loaded total_nodes=%d", len(self._capabilities))

    def get_capabilities(self, node_id: str) -> Optional[NodeCapabilities]:
        """Get capabilities for a node, or None if not found."""
        return self._capabilities.get(node_id)

    def get_compatible_nodes(self, role: AgentRole) -> List[str]:
        """Return list of node IDs that can host the given role."""
        compatible = []
        for node_id, caps in self._capabilities.items():
            can_host, reason = caps.can_host_role(role)
            if can_host:
                compatible.append(node_id)
            else:
                logger.debug(
                    "node_id=%s cannot_host role=%s reason=%s",
                    node_id,
                    role.role_id,
                    reason,
                )
        return compatible

    def update_node_models(self, node_id: str, models: List[str]) -> None:
        """Update the list of models hosted by a node."""
        current = self.get_capabilities(node_id)
        if current:
            # Create new immutable instance with updated models
            from dataclasses import replace

            new_caps = replace(current, hosted_models=tuple(models))
            self._capabilities[node_id] = new_caps
            logger.info("node_models_updated node_id=%s models=%s", node_id, models)

    def is_loaded(self) -> bool:
        """Check if capabilities have been loaded."""
        return self._loaded


# Global singleton instance
capability_registry = CapabilityRegistry()
