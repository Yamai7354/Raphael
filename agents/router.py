import logging
from typing import Any
from data.schemas import SystemEvent, EventType, LayerContext
from event_bus.event_bus import SystemEventBus

from agents.base_agent import BaseAgent
from agents.system import SystemAgent
from agents.coder.coding_agent import CodingAgent
from agents.remote import RemoteAgent
from agents.planner.planner_agent import PlannerAgent
from agents.evaluator.evaluator_agent import EvaluatorAgent
from agents.auditor_agent import AuditorAgent
from agents.neo4j_steward import Neo4jStewardAgent
from agents.qdrant_steward import QdrantStewardAgent
from agents.relational_steward import RelationalStewardAgent
from agents.graph_optimizer_agent import GraphOptimizerAgent
from agents.portfolio_agent import PortfolioAgent
from agents.researcher.research_agent import ResearchAgent
from agents.universal import UniversalAgent
from core.execution.tool_registry import ToolRegistry
from core.execution.tools import BashExecutionTool, PythonExecutionTool
from core.execution.browser_tool import WebBrowserTool

logger = logging.getLogger(__name__)


class AgentRouter:
    """
    Connects worker Agents (Layer 7) to the global Event Bus.
    Listens for AGENT_DISPATCH_REQUESTED from Layer 6 Swarm Manager.
    Executes the task, and fires SUBTASK_COMPLETED.
    """

    def __init__(self, bus: SystemEventBus):
        self.bus = bus
        self.layer_ctx = LayerContext(layer_number=7, module_name="AgentRouter")

        # Initialize Default Tool Registry for Node
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_tool(BashExecutionTool())
        self.tool_registry.register_tool(PythonExecutionTool())
        self.tool_registry.register_tool(WebBrowserTool())

        # Link the string IDs coming from Layer 6 ModelRouter to actual class instances
        self.agent_registry: dict[str, BaseAgent] = {
            "node_mac": UniversalAgent(agent_id="node_mac", tool_registry=self.tool_registry),
            "node_desktop": RemoteAgent(
                agent_id="node_desktop",
                ip_address="192.168.1.198",
                capabilities=["heavy_compute", "amd_gpu"],
            ),
            "node_router": RemoteAgent(
                agent_id="node_router",
                ip_address="192.168.1.1",
                capabilities=["network_audit", "dns"],
            ),
            "agent_omega": CodingAgent(agent_id="agent_omega", tool_registry=self.tool_registry),
            "researcher": ResearchAgent(agent_id="researcher", tool_registry=self.tool_registry),
            "planner": PlannerAgent(agent_id="planner", event_bus=self.bus),
            "evaluator": EvaluatorAgent(agent_id="evaluator", event_bus=self.bus),
            "auditor": AuditorAgent(agent_id="auditor", event_bus=self.bus),
            # Stewardship Agents
            "kg_steward": Neo4jStewardAgent(
                agent_id="kg_steward",
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            ),
            "kg_optimizer": GraphOptimizerAgent(agent_id="kg_optimizer"),
            "vector_steward": QdrantStewardAgent(
                agent_id="vector_steward", url="http://localhost:6333"
            ),
            "db_steward": RelationalStewardAgent(agent_id="db_steward", db_path="data/raphael.db"),
            "portfolio_agent": PortfolioAgent(
                agent_id="portfolio_agent", portfolio_root="/Users/yamai/ai/portfolio"
            ),
        }

    def register_subscriptions(self):
        """Listen to incoming agent dispatches."""
        self.bus.subscribe(EventType.AGENT_DISPATCH_REQUESTED, self.handle_dispatch)

    async def handle_dispatch(self, event: SystemEvent):
        """
        Catches the dispatch event, invokes the correct agent class,
        and reports back up the stack.
        """
        payload: dict[str, Any] = event.payload
        agent_id = payload.get("assigned_agent")
        sub_task_id = payload.get("sub_task_id")
        plan_id = payload.get("plan_id")

        if agent_id not in self.agent_registry:
            logger.error(f"Layer 7 received dispatch for unknown agent ID: {agent_id}. Crashing.")
            # Trigger crash report...
            return

        worker = self.agent_registry[agent_id]

        logger.debug(
            f"Layer 7 Routing task {sub_task_id} to {agent_id} ({worker.__class__.__name__})"
        )

        # Execute the task asynchronously
        try:
            result = await worker.execute(payload)
            success = result.get("success", False)

            if success:
                # Tell Swarm Manager we are done!
                completion_event = SystemEvent(
                    event_type=EventType.SUBTASK_COMPLETED,
                    source_layer=self.layer_ctx,
                    priority=5,
                    payload={
                        "plan_id": plan_id,
                        "sub_task_id": sub_task_id,
                        "agent_id": agent_id,
                        "result": result,
                    },
                )
                await self.bus.publish(completion_event)
            else:
                logger.error(f"Task {sub_task_id} failed on {agent_id}. Full Result: {result}")
                # Here we could publish a SUBTASK_FAILED event to trigger a retry

        except Exception as e:
            logger.error(f"Agent {agent_id} crashed during execution of {sub_task_id}: {e}")
            crash_event = SystemEvent(
                event_type=EventType.CRASH_REPORT,
                source_layer=self.layer_ctx,
                priority=10,
                payload={"error": str(e), "failed_subtask": sub_task_id},
            )
            await self.bus.publish(crash_event)
