"""
Calendar Adapter — Placeholder for calendar management tools.
"""

from typing import Dict, List


def calendar_list_events(date: str) -> Dict[str, str]:
    return {"status": "success", "events": "placeholder"}


def calendar_create_event(title: str, time: str) -> Dict[str, str]:
    return {"status": "success", "event_id": "placeholder"}


CALENDAR_TOOLS = {
    "calendar_list_events": {
        "fn": calendar_list_events,
        "description": "List events for a specific date",
        "permission": "read",
    },
    "calendar_create_event": {
        "fn": calendar_create_event,
        "description": "Create a new calendar event",
        "permission": "write",
    },
}


def get_tools() -> Dict[str, Dict]:
    return CALENDAR_TOOLS


def list_tools() -> List[str]:
    return list(CALENDAR_TOOLS.keys())
