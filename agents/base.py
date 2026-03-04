"""
Backward-compatibility shim: agents.base re-exports BaseAgent from agents.base_agent.
Prefer importing from agents.base_agent in new code.
"""
from agents.base_agent import BaseAgent

__all__ = ["BaseAgent"]
