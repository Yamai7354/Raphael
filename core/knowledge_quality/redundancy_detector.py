"""
KQ-612 — Research Redundancy Detector.

Detects duplicate research missions, suggests consolidation,
redirects agents to unexplored gaps.
"""

import logging
import time
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.redundancy")


@dataclass
class RedundancyAlert:
    topic: str = ""
    agent_count: int = 0
    agents: list[str] = field(default_factory=list)
    suggestion: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "agents": self.agents,
            "count": self.agent_count,
            "suggestion": self.suggestion,
        }


class RedundancyDetector:
    """Detects when agents research the same topic repeatedly."""

    def __init__(self, redundancy_threshold: int = 3):
        self.threshold = redundancy_threshold
        self._research_log: list[dict] = []
        self._alerts: list[RedundancyAlert] = []
        self._covered_topics: set[str] = set()

    def record_research(self, agent: str, topic: str) -> None:
        self._research_log.append(
            {
                "agent": agent,
                "topic": topic.lower(),
                "timestamp": time.time(),
            }
        )
        self._covered_topics.add(topic.lower())
        if len(self._research_log) > 5000:
            self._research_log = self._research_log[-3000:]

    def detect(self, window_hours: float = 24) -> list[RedundancyAlert]:
        """Detect redundant research within a time window."""
        cutoff = time.time() - window_hours * 3600
        recent = [r for r in self._research_log if r["timestamp"] >= cutoff]

        topic_agents: dict[str, list[str]] = {}
        for r in recent:
            topic_agents.setdefault(r["topic"], []).append(r["agent"])

        alerts: list[RedundancyAlert] = []
        for topic, agents in topic_agents.items():
            unique = list(set(agents))
            if len(agents) >= self.threshold:
                alert = RedundancyAlert(
                    topic=topic,
                    agent_count=len(agents),
                    agents=unique,
                    suggestion=f"Consolidate {len(agents)} research attempts on '{topic}'",
                )
                alerts.append(alert)

        self._alerts.extend(alerts)
        return alerts

    def suggest_gaps(self, all_topics: list[str]) -> list[str]:
        """Suggest under-explored topics."""
        topic_counts = Counter(r["topic"] for r in self._research_log)
        return [
            t for t in all_topics if t.lower() not in topic_counts or topic_counts[t.lower()] < 2
        ]

    def get_alerts(self, limit: int = 20) -> list[dict]:
        return [a.to_dict() for a in self._alerts[-limit:]]

    def get_stats(self) -> dict:
        return {
            "research_logged": len(self._research_log),
            "topics_covered": len(self._covered_topics),
            "alerts": len(self._alerts),
        }
