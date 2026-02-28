from typing import Dict, Any


class AttentionFilter:
    """
    Evaluates semantically processed payloads to assign routing priority.
    Filters noise and escalates critical context (like direct commands or crash logs)
    to the System Event Bus.
    """

    def calculate_priority(self, semantic_payload: Dict[str, Any]) -> int:
        """
        Determines event priority based on extracted intent and modality.
        Scale: 1 (Lowest/Background) to 10 (Highest/Critical).
        """
        intent = semantic_payload.get("intent", "unknown")
        urgency = semantic_payload.get("urgency", "low")
        modality = semantic_payload.get("modality", "text")

        # Base Priority
        priority = 5

        # Elevate critical system alerts
        if intent == "system_alert":
            priority = 9

        # Elevate explicit user directives (e.g., spoken voice or typed prompt)
        elif intent == "user_directive":
            priority = 8
            if modality == "speech":
                # Voice commands imply immediate physical presence/waiting
                priority = 9

        # Deprioritize background noise
        elif intent == "background_info":
            # Typical telemetry or background chatter
            priority = 2

        # Slight bump for active visual scenes (implies context change)
        if modality == "vision" and priority < 7:
            priority += 1

        # Bound check (1 to 10 is enforced by SystemEvent schema, but
        # we defensively bound it here)
        return max(1, min(10, priority))

    def process(self, semantic_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Injects the calculated priority score and drops irrelevant data if necessary.
        """
        processed = semantic_payload.copy()
        processed["attention_priority"] = self.calculate_priority(semantic_payload)
        return processed
