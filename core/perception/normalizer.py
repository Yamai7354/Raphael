import json
from datetime import datetime, timezone
from typing import Any, Dict


class InputNormalizer:
    """
    Standardizes raw input from Layer 1 (Environment) into a uniform,
    predictable semantic format before model ingestion.
    """

    @staticmethod
    def normalize_timestamp(raw_timestamp: Any) -> str:
        """Ensures all timestamps resolve to standard ISO 8601 UTC strings."""
        if isinstance(raw_timestamp, datetime):
            return raw_timestamp.astimezone(timezone.utc).isoformat()
        if isinstance(raw_timestamp, str):
            try:
                # Attempt to parse a string timestamp to enforce format
                parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                return parsed.astimezone(timezone.utc).isoformat()
            except ValueError:
                pass

        # Fallback to current UTC time if unparseable or missing
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def normalize_payload(raw_payload: Any) -> Dict[str, Any]:
        """Ensures the payload is a valid dictionary structure."""
        if isinstance(raw_payload, dict):
            return raw_payload

        if isinstance(raw_payload, str):
            try:
                # Try to parse stringified JSON
                parsed = json.loads(raw_payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            # If it's just a raw text string context
            return {"raw_text": raw_payload}

        # Fallback wrapper for odd types (lists, bytes representation)
        return {"raw_data": str(raw_payload)}

    def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main pipeline to format an incoming environment dictionary.
        Expects a dict describing the raw event and standardizes `timestamp` and `payload`.
        """
        standardized = {
            "source": raw_data.get("source", "unknown_environment_sensor"),
            "timestamp": self.normalize_timestamp(raw_data.get("timestamp")),
            "payload": self.normalize_payload(raw_data.get("payload", {})),
        }
        return standardized
