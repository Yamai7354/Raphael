"""
ResearchEvent Processor.

Agents create ResearchEvents instead of Knowledge nodes directly.
This processor evaluates, deduplicates, and converts worthy
research into proper Knowledge nodes — preventing graph flooding.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.knowledge_quality.research_event_processor")


@dataclass
class ResearchEvent:
    """An agent's raw research output — NOT a graph node yet."""

    event_id: str = field(default_factory=lambda: f"re_{uuid.uuid4().hex[:10]}")
    agent_name: str = ""
    topic: str = ""
    content: str = ""
    source_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    processed: bool = False
    outcome: str = ""  # promoted, merged, discarded

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "agent": self.agent_name,
            "topic": self.topic,
            "confidence": round(self.confidence, 3),
            "outcome": self.outcome,
        }


class ResearchEventProcessor:
    """
    Processes ResearchEvents into Knowledge nodes.

    Flow:
      Agent → ResearchEvent (buffer)
      Processor → deduplicate, score, filter
      Worthy events → Knowledge node creation
      Low-value events → discarded (never touch the graph)
    """

    def __init__(
        self,
        min_confidence: float = 0.3,
        min_content_length: int = 20,
        similarity_threshold: float = 0.85,
        max_buffer_size: int = 1000,
    ):
        self.min_confidence = min_confidence
        self.min_content_length = min_content_length
        self.similarity_threshold = similarity_threshold
        self.max_buffer_size = max_buffer_size
        self._buffer: list[ResearchEvent] = []
        self._processed: list[ResearchEvent] = []
        self._topic_index: dict[str, list[str]] = {}  # topic → [event_ids]
        self._stats = {"submitted": 0, "promoted": 0, "merged": 0, "discarded": 0}

    def submit(
        self,
        agent_name: str,
        topic: str,
        content: str = "",
        source_refs: list[str] | None = None,
        confidence: float = 0.5,
    ) -> ResearchEvent:
        """Agent submits a research event. It is NOT written to the graph yet."""
        event = ResearchEvent(
            agent_name=agent_name,
            topic=topic,
            content=content,
            source_refs=source_refs or [],
            confidence=confidence,
        )
        self._buffer.append(event)
        self._topic_index.setdefault(topic.lower(), []).append(event.event_id)
        self._stats["submitted"] += 1

        # Prevent buffer explosion
        if len(self._buffer) > self.max_buffer_size:
            self._buffer = self._buffer[-self.max_buffer_size :]

        logger.info(
            "research_submitted agent=%s topic=%s confidence=%.2f", agent_name, topic, confidence
        )
        return event

    def process_batch(self) -> dict:
        """Process all buffered events. Returns promotion results."""
        results = {"promoted": [], "merged": [], "discarded": []}
        pending = [e for e in self._buffer if not e.processed]

        for event in pending:
            outcome = self._evaluate(event)
            event.processed = True
            event.outcome = outcome

            if outcome == "promoted":
                results["promoted"].append(event)
                self._stats["promoted"] += 1
            elif outcome == "merged":
                results["merged"].append(event)
                self._stats["merged"] += 1
            else:
                results["discarded"].append(event)
                self._stats["discarded"] += 1

            self._processed.append(event)

        # Clear processed from buffer
        self._buffer = [e for e in self._buffer if not e.processed]

        logger.info(
            "batch_processed promoted=%d merged=%d discarded=%d",
            len(results["promoted"]),
            len(results["merged"]),
            len(results["discarded"]),
        )
        return {k: [e.to_dict() for e in v] for k, v in results.items()}

    def _evaluate(self, event: ResearchEvent) -> str:
        """Evaluate a single research event."""
        # Filter: too low confidence
        if event.confidence < self.min_confidence:
            return "discarded"

        # Filter: no meaningful content
        if len(event.content.strip()) < self.min_content_length:
            return "discarded"

        # Dedup: check if topic already has recent research
        topic_events = self._topic_index.get(event.topic.lower(), [])
        if len(topic_events) > 3:
            # Too many events on same topic — merge signal
            return "merged"

        # Check for near-duplicate content in processed events
        event_words = set(event.content.lower().split())
        for prev in self._processed[-100:]:
            if prev.outcome == "promoted" and prev.topic.lower() == event.topic.lower():
                prev_words = set(prev.content.lower().split())
                if event_words and prev_words:
                    jaccard = len(event_words & prev_words) / len(event_words | prev_words)
                    if jaccard >= self.similarity_threshold:
                        return "merged"

        return "promoted"

    def get_promoted_events(self) -> list[ResearchEvent]:
        """Get events ready to become Knowledge nodes."""
        return [e for e in self._processed if e.outcome == "promoted"]

    def get_buffer_size(self) -> int:
        return len(self._buffer)

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "buffer_size": len(self._buffer),
            "processed_total": len(self._processed),
            "promotion_rate": (
                round(self._stats["promoted"] / max(1, self._stats["submitted"]), 3)
            ),
        }
