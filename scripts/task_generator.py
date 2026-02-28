import logging
import uuid
from typing import Any, Dict, Optional
from ..models.task import Task, TaskPriority, TaskStatus
from .event_bus import EventBus

logger = logging.getLogger("task_generator")


class TaskGenerator:
    """
    Subscribes to events and generates Tasks based on predefined logic.
    Part of RAPHAEL-201.
    """

    def __init__(self, bus: EventBus, task_callback: Optional[Any] = None):
        self.bus = bus
        self.task_callback = task_callback

    async def start(self):
        """Start listening to observatory events."""
        await self.bus.subscribe("observatory_events", self._handle_observatory_event)
        logger.info("TaskGenerator started and subscribed to 'observatory_events'")

    async def _handle_observatory_event(self, event_data: Dict[str, Any]):
        """
        Convert observatory threats into Raphael Tasks.
        Example event_data:
        {
            "severity": "critical",
            "category": "brute_force",
            "title": "Brute Force Attack from 192.168.1.50",
            "description": "...",
            "source_ip": "192.168.1.50",
            "block_command": "iptables ..."
        }
        """
        severity = event_data.get("severity", "low").lower()
        if severity not in ["high", "critical"]:
            logger.debug(f"Skipping low severity event: {event_data.get('title')}")
            return

        logger.info(
            f"Generating task for high-severity event: {event_data.get('title')}"
        )

        # Map severity to TaskPriority
        priority = TaskPriority.HIGH if severity == "high" else TaskPriority.CRITICAL

        # Create a Task
        task = Task(
            title=f"Security Alert: {event_data.get('title')}",
            description=event_data.get("description", "No description provided"),
            priority=priority,
            status=TaskStatus.PENDING,
            input_data={
                "event": event_data,
                "recommended_action": event_data.get(
                    "recommended_action", "Investigate and block if necessary"
                ),
            },
            metadata={
                "source": "network_observatory",
                "category": event_data.get("category"),
                "detected_at": event_data.get("timestamp"),
            },
        )

        if self.task_callback:
            if asyncio.iscoroutinefunction(self.task_callback):
                await self.task_callback(task)
            else:
                self.task_callback(task)
        else:
            # Default fallback: Log it
            logger.info(f"Generated Task {task.id}: {task.title}")


import asyncio
