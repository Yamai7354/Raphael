from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID, uuid4
from abc import ABC, abstractmethod


class MemoryType(str, Enum):
    WORKING = "working"  # Transient, active task context
    EPISODIC = "episodic"  # Historical task experiences
    SEMANTIC = "semantic"  # General knowledge & embeddings
    PROCEDURAL = "procedural"  # Execution heuristics & strategies


class MemoryMetadata(BaseModel):
    source_agent: str
    correlation_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class MemoryPayload(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    memory_type: MemoryType
    content: Any
    metadata: MemoryMetadata


class MemoryContract(ABC):
    """MEM-1: Standardized contract for memory access across ecosystem components."""

    @abstractmethod
    async def store(self, payload: MemoryPayload):
        """Cross-project storage contract."""
        pass

    @abstractmethod
    async def retrieve(
        self, query: str, filters: Dict[str, Any]
    ) -> List[MemoryPayload]:
        """Cross-project retrieval contract."""
        pass

    @abstractmethod
    async def forget(self, policy: Dict[str, Any]):
        """Sanitization and pruning contract."""
        pass
