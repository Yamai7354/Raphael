from abc import ABC, abstractmethod
from typing import Any, Dict


class PerceptionModelBase(ABC):
    """Abstract base class for all semantic models in Layer 2."""

    @abstractmethod
    def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Take a normalized payload and extract semantic meaning."""
        pass


class MockVisionModel(PerceptionModelBase):
    """
    Placeholder for Moondream/vision integration.
    Extracts structured scene data from simulated visual bytes.
    """

    def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = payload.copy()
        raw = payload.get("raw_text", "")
        if "image_bytes" in raw or "visual:" in raw:
            result["scene_description"] = "Simulated visual scene processed."
            result["detected_objects"] = ["computer", "desk", "user"]
            result["modality"] = "vision"
        return result


class MockSpeechModel(PerceptionModelBase):
    """
    Placeholder for Whisper/audio integration.
    Extracts transcribed text from simulated audio.
    """

    def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = payload.copy()
        raw = payload.get("raw_text", "")
        if "audio_bytes" in raw or "speech:" in raw:
            # Simulated transcription
            transcribed = raw.replace("speech:", "").strip()
            result["transcription"] = (
                transcribed if transcribed else "Simulated speech transcribed."
            )
            result["modality"] = "speech"
        return result


class TextUnderstandingModel(PerceptionModelBase):
    """
    Evaluates pure text streams (e.g. CLI input, log files)
    for initial intent and entity recognition.
    """

    def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = payload.copy()
        # If it wasn't caught by vision or speech, treat as text
        if "modality" not in result:
            result["modality"] = "text"
            text_str = str(payload)
            if "error" in text_str.lower() or "exception" in text_str.lower():
                result["intent"] = "system_alert"
                result["urgency"] = "high"
            elif "user_command" in text_str.lower() or "prompt:" in text_str.lower():
                result["intent"] = "user_directive"
                result["urgency"] = "medium"
            else:
                result["intent"] = "background_info"
                result["urgency"] = "low"
        return result
