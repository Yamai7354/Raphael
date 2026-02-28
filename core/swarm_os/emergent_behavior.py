"""
SOS-515 — Emergent Behavior Monitoring.

Detects and analyzes emergent swarm behaviors: unusual cooperation
patterns, unexpected strategies, and system-wide trends.
"""

import logging
import time
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.emergent_behavior")


@dataclass
class EmergentPattern:
    """A detected emergent behavior pattern."""

    pattern_id: str = ""
    pattern_type: str = ""  # cooperation, strategy, clustering, specialization
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    significance: float = 0.5  # 0-1
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "type": self.pattern_type,
            "description": self.description,
            "significance": round(self.significance, 3),
            "evidence": self.evidence[:5],
        }


class EmergentBehaviorMonitor:
    """Monitors for emergent behaviors in the swarm."""

    def __init__(self, min_significance: float = 0.3):
        self.min_significance = min_significance
        self._interaction_log: list[dict] = []  # agent interactions
        self._task_strategies: list[dict] = []
        self._patterns: list[EmergentPattern] = []
        self._pattern_counter = 0

    def record_interaction(
        self, agent_a: str, agent_b: str, interaction_type: str = "collaboration"
    ) -> None:
        self._interaction_log.append(
            {
                "agents": (agent_a, agent_b),
                "type": interaction_type,
                "timestamp": time.time(),
            }
        )
        if len(self._interaction_log) > 2000:
            self._interaction_log = self._interaction_log[-1000:]

    def record_task_strategy(self, agent: str, task_type: str, strategy: str) -> None:
        self._task_strategies.append(
            {
                "agent": agent,
                "task_type": task_type,
                "strategy": strategy,
                "timestamp": time.time(),
            }
        )
        if len(self._task_strategies) > 2000:
            self._task_strategies = self._task_strategies[-1000:]

    def analyze(self) -> list[EmergentPattern]:
        """Run emergent behavior detection."""
        patterns: list[EmergentPattern] = []

        # 1. Detect unusual cooperation clusters
        pair_counts: Counter = Counter()
        for log in self._interaction_log[-200:]:
            pair = tuple(sorted(log["agents"]))
            pair_counts[pair] += 1

        for pair, count in pair_counts.most_common(5):
            if count >= 5:
                self._pattern_counter += 1
                patterns.append(
                    EmergentPattern(
                        pattern_id=f"ep_{self._pattern_counter}",
                        pattern_type="cooperation",
                        description=f"Frequent collaboration: {pair[0]} ↔ {pair[1]} ({count} interactions)",
                        evidence=[f"pair:{pair[0]},{pair[1]}", f"count:{count}"],
                        significance=min(1.0, count / 20),
                    )
                )

        # 2. Detect unexpected task strategies
        strategy_counts: Counter = Counter()
        for log in self._task_strategies[-200:]:
            key = f"{log['task_type']}:{log['strategy']}"
            strategy_counts[key] += 1

        for strategy, count in strategy_counts.most_common(3):
            if count >= 3:
                self._pattern_counter += 1
                patterns.append(
                    EmergentPattern(
                        pattern_id=f"ep_{self._pattern_counter}",
                        pattern_type="strategy",
                        description=f"Repeated strategy: {strategy} ({count} occurrences)",
                        evidence=[f"strategy:{strategy}", f"count:{count}"],
                        significance=min(1.0, count / 15),
                    )
                )

        # 3. Detect agent specialization drift
        agent_task_types: dict[str, Counter] = {}
        for log in self._task_strategies[-100:]:
            agent = log["agent"]
            if agent not in agent_task_types:
                agent_task_types[agent] = Counter()
            agent_task_types[agent][log["task_type"]] += 1

        for agent, counts in agent_task_types.items():
            total = sum(counts.values())
            if total >= 5:
                top_type, top_count = counts.most_common(1)[0]
                ratio = top_count / total
                if ratio > 0.8:
                    self._pattern_counter += 1
                    patterns.append(
                        EmergentPattern(
                            pattern_id=f"ep_{self._pattern_counter}",
                            pattern_type="specialization",
                            description=f"Agent {agent} specializing in {top_type} ({ratio:.0%} of tasks)",
                            evidence=[f"agent:{agent}", f"focus:{top_type}", f"ratio:{ratio:.2f}"],
                            significance=ratio,
                        )
                    )

        # Filter by significance
        patterns = [p for p in patterns if p.significance >= self.min_significance]
        self._patterns.extend(patterns)
        if patterns:
            logger.info("emergent_behaviors detected: %d patterns", len(patterns))
        return patterns

    def get_patterns(self, limit: int = 20) -> list[dict]:
        return [p.to_dict() for p in self._patterns[-limit:]]

    def get_report(self) -> dict:
        """Generate a summary report."""
        by_type: dict[str, int] = {}
        for p in self._patterns:
            by_type[p.pattern_type] = by_type.get(p.pattern_type, 0) + 1

        return {
            "total_patterns": len(self._patterns),
            "by_type": by_type,
            "interactions_logged": len(self._interaction_log),
            "strategies_logged": len(self._task_strategies),
            "recent_patterns": [p.to_dict() for p in self._patterns[-5:]],
        }

    def get_stats(self) -> dict:
        return {
            "total_patterns": len(self._patterns),
            "interactions": len(self._interaction_log),
            "strategies": len(self._task_strategies),
        }
