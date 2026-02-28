"""
Browser Adapter — Placeholder for web navigation and interaction tools.
"""

from typing import Dict, List


def browser_navigate(url: str) -> Dict[str, str]:
    return {"status": "success", "url": url}


def browser_extract_text(selector: str) -> Dict[str, str]:
    return {"status": "success", "text": "placeholder"}


BROWSER_TOOLS = {
    "browser_navigate": {
        "fn": browser_navigate,
        "description": "Navigate to a URL",
        "permission": "read",
    },
    "browser_extract_text": {
        "fn": browser_extract_text,
        "description": "Extract text from current page using selector",
        "permission": "read",
    },
}


def get_tools() -> Dict[str, Dict]:
    return BROWSER_TOOLS


def list_tools() -> List[str]:
    return list(BROWSER_TOOLS.keys())
