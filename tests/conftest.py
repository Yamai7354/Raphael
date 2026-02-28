import pytest
from unittest.mock import AsyncMock, MagicMock
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.memory.working_memory import WorkingMemory
from src.raphael.memory.episodic_memory import EpisodicMemory
from src.raphael.memory.operational_kg import OperationalKG
from src.raphael.memory.research_kg import ResearchKG
from src.raphael.memory.vector_store import VectorStore


@pytest.fixture
def mock_event_bus():
    bus = SystemEventBus()
    bus.publish = AsyncMock()
    bus.subscribe = MagicMock()
    return bus


@pytest.fixture
def mock_working_memory():
    mock = AsyncMock(spec=WorkingMemory)
    mock.put.return_value = True
    mock.get.return_value = None
    mock.delete.return_value = True
    return mock


@pytest.fixture
def mock_episodic_memory():
    mock = AsyncMock(spec=EpisodicMemory)
    mock.store_task.return_value = "mock_task_id"
    mock.log_event.return_value = "mock_event_id"
    mock.get_task.return_value = {"status": "completed"}
    return mock


@pytest.fixture
def mock_operational_kg():
    mock = AsyncMock(spec=OperationalKG)
    mock.record_task.return_value = "mock_node_id"
    mock.record_model_execution.return_value = "mock_exec_id"
    return mock


@pytest.fixture
def mock_research_kg():
    mock = AsyncMock(spec=ResearchKG)
    mock.record_insight.return_value = "mock_insight_id"
    return mock


@pytest.fixture
def mock_vector_store():
    mock = AsyncMock(spec=VectorStore)
    mock.store_embedding.return_value = "mock_vector_id"
    mock.search_similar.return_value = []
    return mock


@pytest.fixture
def sample_layer_context():
    return LayerContext(layer_number=1, module_name="TestModule")
