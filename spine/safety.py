import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    """Raised when a task payload trips a hardcoded safety boundary."""

    pass


class SafetyGate:
    """
    The absolute boundary against destructive or misaligned execution.
    Scans incoming task payloads for explicitly forbidden operations.
    """

    # Simple regex/keyword blocklist for dangerous OS commands
    FORBIDDEN_KEYWORDS = [
        "rm -rf /",
        "mkfs",
        "dd if=/dev/zero",
        ":(){ :|:& };:",  # Fork bomb
        "DROP TABLE",
    ]

    def evaluate_payload(self, payload: Dict[str, Any]) -> bool:
        """
        Recursively scans a task payload's string values against the blocklist.
        Raises SecurityViolation if a match is hit.
        Returns True if safe.
        """

        def _scan_obj(obj: Any):
            if isinstance(obj, str):
                for keyword in self.FORBIDDEN_KEYWORDS:
                    if keyword.lower() in obj.lower():
                        raise SecurityViolation(f"Forbidden command sequence detected: '{keyword}'")
            elif isinstance(obj, dict):
                for v in obj.values():
                    _scan_obj(v)
            elif isinstance(obj, list):
                for item in obj:
                    _scan_obj(item)

        try:
            _scan_obj(payload)
            return True
        except SecurityViolation as e:
            logger.critical(f"Safety Gate blocked execution: {e}")
            raise
