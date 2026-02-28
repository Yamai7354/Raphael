from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SemanticMemory(ABC):
    """Abstract base class for Semantic Memory."""

    @abstractmethod
    async def add(
        self, text: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a semantic entry."""
        pass

    @abstractmethod
    async def search(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar entries."""
        pass
