"""
SOS-506 — Swarm Communication Bus.

Reliable agent-to-agent and agent-to-engine messaging with
high-throughput async support and world model integration.
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.comm_bus")


@dataclass
class SwarmMessage:
    """A message on the swarm communication bus."""

    msg_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    sender: str = ""
    recipient: str = ""  # empty = broadcast
    channel: str = "general"
    msg_type: str = "data"  # data, task, discovery, alert, query
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "channel": self.channel,
            "type": self.msg_type,
            "payload": self.payload,
        }


class SwarmCommBus:
    """Communication backbone for the swarm."""

    def __init__(self, history_limit: int = 1000):
        self.history_limit = history_limit
        self._subscribers: dict[str, list[str]] = defaultdict(list)  # channel -> [agent_names]
        self._inbox: dict[str, list[SwarmMessage]] = defaultdict(list)  # agent -> [messages]
        self._message_log: list[SwarmMessage] = []
        self._stats = {"sent": 0, "broadcast": 0, "direct": 0}

    def subscribe(self, agent_name: str, channel: str) -> None:
        if agent_name not in self._subscribers[channel]:
            self._subscribers[channel].append(agent_name)

    def unsubscribe(self, agent_name: str, channel: str) -> None:
        if agent_name in self._subscribers[channel]:
            self._subscribers[channel].remove(agent_name)

    def send(
        self,
        sender: str,
        recipient: str,
        payload: dict,
        channel: str = "general",
        msg_type: str = "data",
    ) -> SwarmMessage:
        """Send a direct message to a specific agent."""
        msg = SwarmMessage(
            sender=sender,
            recipient=recipient,
            channel=channel,
            msg_type=msg_type,
            payload=payload,
        )
        self._inbox[recipient].append(msg)
        self._log(msg)
        self._stats["sent"] += 1
        self._stats["direct"] += 1
        return msg

    def broadcast(
        self, sender: str, channel: str, payload: dict, msg_type: str = "data"
    ) -> SwarmMessage:
        """Broadcast a message to all subscribers of a channel."""
        msg = SwarmMessage(
            sender=sender,
            channel=channel,
            msg_type=msg_type,
            payload=payload,
        )
        for agent in self._subscribers.get(channel, []):
            if agent != sender:
                self._inbox[agent].append(msg)
        self._log(msg)
        self._stats["sent"] += 1
        self._stats["broadcast"] += 1
        return msg

    def receive(self, agent_name: str, limit: int = 10) -> list[SwarmMessage]:
        """Get pending messages for an agent."""
        messages = self._inbox.get(agent_name, [])[:limit]
        self._inbox[agent_name] = self._inbox.get(agent_name, [])[limit:]
        return messages

    def peek(self, agent_name: str) -> int:
        """Check how many messages are pending."""
        return len(self._inbox.get(agent_name, []))

    def acknowledge(self, msg_id: str) -> None:
        for msg in self._message_log:
            if msg.msg_id == msg_id:
                msg.acknowledged = True
                break

    def _log(self, msg: SwarmMessage) -> None:
        self._message_log.append(msg)
        if len(self._message_log) > self.history_limit:
            self._message_log = self._message_log[-self.history_limit :]

    def get_channel_subscribers(self, channel: str) -> list[str]:
        return list(self._subscribers.get(channel, []))

    def get_recent_messages(self, channel: str = "", limit: int = 20) -> list[dict]:
        msgs = (
            self._message_log
            if not channel
            else [m for m in self._message_log if m.channel == channel]
        )
        return [m.to_dict() for m in msgs[-limit:]]

    def get_stats(self) -> dict:
        return {
            "channels": len(self._subscribers),
            "total_subscribers": sum(len(v) for v in self._subscribers.values()),
            "pending_messages": sum(len(v) for v in self._inbox.values()),
            **self._stats,
        }
