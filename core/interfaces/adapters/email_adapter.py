"""
Email Adapter — Placeholder for email generation and extraction tools.
"""

from typing import Dict, List


def email_read_inbox(limit: int = 10) -> Dict[str, str]:
    return {"status": "success", "emails": "placeholder"}


def email_send(to: str, subject: str, body: str) -> Dict[str, str]:
    return {"status": "success", "message_id": "placeholder"}


EMAIL_TOOLS = {
    "email_read_inbox": {
        "fn": email_read_inbox,
        "description": "Read recent emails from inbox",
        "permission": "read",
    },
    "email_send": {
        "fn": email_send,
        "description": "Send a new email",
        "permission": "write",
    },
}


def get_tools() -> Dict[str, Dict]:
    return EMAIL_TOOLS


def list_tools() -> List[str]:
    return list(EMAIL_TOOLS.keys())
