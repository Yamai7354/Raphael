"""
Mock Infrastructure for AI Router.

Provides mock tool implementations for testing without external side effects.
Supports latency simulation and failure injection.
"""

import logging
import asyncio
import random
from typing import Dict, Any, Optional
from tools import ToolAdapter, ToolConfig, ToolType

logger = logging.getLogger("ai_router.mock_infra")


# =============================================================================
# MOCK TOOL
# =============================================================================


class MockTool(ToolAdapter):
    """
    Mock implementation of a tool for testing.
    """

    def __init__(
        self,
        config: ToolConfig,
        mock_response: Optional[Dict[str, Any]] = None,
        latency_ms: float = 100.0,
        failure_rate: float = 0.0,
    ):
        super().__init__(config)
        self.mock_response = mock_response or {"status": "success", "mock": True}
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mock logic."""
        # Validate inputs first
        self.validate_inputs(inputs)

        # Simulate latency
        if self.latency_ms > 0:
            delay = self.latency_ms / 1000.0
            await asyncio.sleep(delay)

        # Simulate failure
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            raise RuntimeError(f"Mock failure simulated for {self.name}")

        # Dynamic mock response if needed
        response = self.mock_response.copy()
        response["inputs_echo"] = inputs

        return response

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Mock validation."""
        # Simple check: fails if 'fail_validation' key is present
        if "fail_validation" in inputs:
            raise ValueError("Input validation failed (simulated)")
        return True


# =============================================================================
# PRE-BUILT MOCKS
# =============================================================================


def create_mock_database(name: str = "mock_db") -> MockTool:
    """Create a mock database tool."""
    config = ToolConfig(
        name=name,
        tool_type=ToolType.DATABASE,
        description="Mock database for validation",
        allowed_roles={"heavy_inference"},
        mock_mode=True,
    )
    return MockTool(config, {"rows": [{"id": 1, "value": "test"}]})


def create_mock_api(name: str = "mock_api") -> MockTool:
    """Create a mock API tool."""
    config = ToolConfig(
        name=name,
        tool_type=ToolType.API,
        description="Mock API for validation",
        allowed_roles={"fast_inference", "heavy_inference"},
        mock_mode=True,
    )
    return MockTool(config, {"result": "ok"})


# Global test suite
TEST_SUITE = {
    "db": create_mock_database(),
    "api": create_mock_api(),
}
