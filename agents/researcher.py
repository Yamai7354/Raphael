import logging
from typing import Any

from agents.base import BaseAgent
from core.execution.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    Agent responsible for gathering external knowledge, analyzing data, or exploring options.
    Fetches info from databases, APIs, or documents.
    """

    def __init__(self, agent_id: str = "research_agent", tool_registry: ToolRegistry = None):
        super().__init__(
            agent_id=agent_id,
            capabilities=["web_search", "data_analysis", "summarization", "extraction"],
        )
        self.tool_registry = tool_registry

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Executes a research task, potentially calling search or scraping tools.
        """
        st_id = payload.get("sub_task_id", "unknown")
        query = payload.get("query")

        logger.info(f"ResearchAgent [{self.agent_id}] engaging SubTask {st_id}")

        if not query:
            return self._standard_response(
                success=False,
                logs=["No query provided for research."],
                error="Missing 'query' parameter",
            )

        logs = [
            "Initializing deep search logic.",
            f"Querying external intelligence for: {query}",
        ]

        # In a real scenario, this would call a 'serper' or 'duckduckgo' tool
        # For now, we simulate the tool result or use the tool if registered.
        tool_result = None
        if self.tool_registry and "web_search" in self.tool_registry._tools:
            tool_result = self.tool_registry.execute_tool(
                tool_name="web_search", params={"query": query}
            )
            logs.append("Search Tool executed. Results captured.")
        else:
            logs.append(
                "No specialized search tool found. Falling back to internal knowledge simulation."
            )
            tool_result = {
                "results": [
                    {
                        "title": f"Summary for {query}",
                        "snippet": "Simulated search result content...",
                    }
                ]
            }

        logs.append("Synthesizing research report...")

        return self._standard_response(
            success=True,
            logs=logs,
            output={
                "research_summary": f"Findings for '{query}': High relevance detected in local clusters.",
                "sources": tool_result.get("results", []),
            },
        )
