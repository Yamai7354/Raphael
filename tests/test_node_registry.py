"""
Tests for node_registry.py — registry isolation, pinned model protection,
and VRAM budget enforcement.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_router.node_registry import NodeRegistry, REGISTRY_LMSTUDIO, REGISTRY_OLLAMA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_CONFIG = [
    {
        "id": "win-desktop",
        "url": "http://100.125.58.22:5000/v1",
        "registry_type": "lmstudio",
        "pinned_models": [
            "text-embedding-bge-large-en-v1.5",
            "text-embedding-bge-small-en-v1.5",
        ],
        "capabilities": {
            "memory_budget_mb": 14336,
            "vram_budget_mb": 8192,
            "max_model_size_gb": 8,
        },
    },
    {
        "id": "mac-local",
        "url": "http://localhost:11434/v1",
        "registry_type": "ollama",
        "pinned_models": ["vishalraj/nomic-embed-code:latest"],
        "capabilities": {
            "memory_budget_mb": 16384,
            "vram_budget_mb": 12288,
            "max_model_size_gb": 8,
        },
    },
]


@pytest.fixture
def registry():
    reg = NodeRegistry()
    reg.load_from_config(MOCK_CONFIG)
    return reg


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def test_load_from_config(registry: NodeRegistry):
    """Both nodes should be registered with correct registry types."""
    assert set(registry.get_all_node_ids()) == {"win-desktop", "mac-local"}

    desktop = registry.get_entry("win-desktop")
    assert desktop is not None
    assert desktop.registry_type == "lmstudio"
    assert desktop.base_url == "http://100.125.58.22:5000"

    mac = registry.get_entry("mac-local")
    assert mac is not None
    assert mac.registry_type == "ollama"
    assert mac.base_url == "http://localhost:11434"


def test_registry_type_filtering(registry: NodeRegistry):
    """get_nodes_for_registry_type should return only matching nodes."""
    assert registry.get_nodes_for_registry_type("lmstudio") == ["win-desktop"]
    assert registry.get_nodes_for_registry_type("ollama") == ["mac-local"]
    assert registry.get_nodes_for_registry_type("unknown") == []


# ---------------------------------------------------------------------------
# Pinned model protection
# ---------------------------------------------------------------------------


def test_pinned_models(registry: NodeRegistry):
    """Pinned embedding models must not be swappable."""
    assert registry.get_pinned_models("win-desktop") == (
        "text-embedding-bge-large-en-v1.5",
        "text-embedding-bge-small-en-v1.5",
    )
    assert registry.get_pinned_models("mac-local") == ("vishalraj/nomic-embed-code:latest",)


def test_is_model_swappable_pinned(registry: NodeRegistry):
    """Pinned models should NOT be swappable."""
    assert not registry.is_model_swappable("text-embedding-bge-large-en-v1.5", "win-desktop")
    assert not registry.is_model_swappable("text-embedding-bge-small-en-v1.5", "win-desktop")
    assert not registry.is_model_swappable("vishalraj/nomic-embed-code:latest", "mac-local")


def test_is_model_swappable_non_pinned(registry: NodeRegistry):
    """Non-pinned models should be swappable."""
    assert registry.is_model_swappable("l3-8b-stheno-v3.2-iq-imatrix", "win-desktop")
    assert registry.is_model_swappable("llama3:8b", "mac-local")


# ---------------------------------------------------------------------------
# Cross-registry validation
# ---------------------------------------------------------------------------


def test_validate_model_pinned(registry: NodeRegistry):
    """A pinned model should always be valid for its own node."""
    ok, reason = registry.validate_model_for_node("text-embedding-bge-large-en-v1.5", "win-desktop")
    assert ok


def test_validate_cross_registry_blocked(registry: NodeRegistry):
    """
    If model X is pinned on desktop, requesting it on mac should be blocked.
    """
    ok, reason = registry.validate_model_for_node("text-embedding-bge-large-en-v1.5", "mac-local")
    assert not ok
    assert "Cross-registry pull blocked" in reason


def test_validate_model_discovered(registry: NodeRegistry):
    """After refresh, a discovered model should validate on its own node."""
    entry = registry.get_entry("win-desktop")
    entry.discovered_models = ["l3-8b-stheno-v3.2-iq-imatrix", "ministral-3b"]

    ok, reason = registry.validate_model_for_node("l3-8b-stheno-v3.2-iq-imatrix", "win-desktop")
    assert ok

    # Cross-registry: same model should be blocked on mac
    ok, reason = registry.validate_model_for_node("l3-8b-stheno-v3.2-iq-imatrix", "mac-local")
    assert not ok
    assert "Cross-registry pull blocked" in reason


def test_validate_unknown_model(registry: NodeRegistry):
    """A model not found in any registry should fail validation."""
    ok, reason = registry.validate_model_for_node("totally-unknown-model-42", "win-desktop")
    assert not ok
    assert "not found in any registry" in reason


# ---------------------------------------------------------------------------
# VRAM budget enforcement
# ---------------------------------------------------------------------------


def test_can_fit_model_within_budget(registry: NodeRegistry):
    """A model within VRAM budget should be accepted."""
    ok, reason = registry.can_fit_model(7.0, "win-desktop")
    assert ok


def test_can_fit_model_exceeds_budget(registry: NodeRegistry):
    """A model exceeding VRAM budget should be rejected."""
    ok, reason = registry.can_fit_model(16.0, "win-desktop")
    assert not ok
    assert "exceeds" in reason


def test_can_fit_model_unknown_node(registry: NodeRegistry):
    """Unknown node should fail gracefully."""
    ok, reason = registry.can_fit_model(1.0, "nonexistent-node")
    assert not ok


# ---------------------------------------------------------------------------
# URL stripping (/v1 suffix removal)
# ---------------------------------------------------------------------------


def test_url_stripping(registry: NodeRegistry):
    """Base URLs should have /v1 suffix stripped."""
    desktop = registry.get_entry("win-desktop")
    assert not desktop.base_url.endswith("/v1")

    mac = registry.get_entry("mac-local")
    assert not mac.base_url.endswith("/v1")
