import logging
import asyncio
import os
import httpx
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from pathlib import Path

from . import bus
from event_bus.event_bus import Event

logger = logging.getLogger("ai_router.interaction")


class VoiceBankConfig(BaseModel):
    base_path: str = "/users/yamai/ai/speech"
    mood_folders: Dict[str, str] = {
        "normal": "満別花丸通常連続音",
        "shout": "満別花丸叫び連続音",
        "whisper": "満別花丸囁き連続音",
        "expressions": "満別花丸_ボイス素材（仮）",
    }


class VoiceBankManager:
    """Manages local character voice assets and phrase mapping."""

    def __init__(self, config: VoiceBankConfig = VoiceBankConfig()):
        self.config = config
        self.expressions: Dict[str, Path] = {}
        self.base_path = Path(config.base_path)

    async def scan_assets(self):
        """Index pre-recorded expressions for quick playback."""
        expr_path = self.base_path / self.config.mood_folders["expressions"]
        if not expr_path.exists():
            logger.warning(f"Expression folder not found: {expr_path}")
            return

        # Mapping for common phrases in the Hanarmaru voice bank
        phrase_map = {
            "hello": "こんにちは",
            "good_morning": "おはようございます",
            "good_evening": "こんばんは",
            "thanks": "ありがとう",
            "sorry": "すみませ",  # Match "sumimasen" part
            "goodbye": "さようなら",
            "nice_to_meet_you": "初めまして",
        }

        try:
            for p in expr_path.glob("*.wav"):
                filename = p.name
                for eng_key, jap_key in phrase_map.items():
                    if jap_key in filename:
                        self.expressions[eng_key] = p
                        break
            logger.info(
                f"VoiceBank indexed {len(self.expressions)} character expressions."
            )
        except Exception as e:
            logger.error(f"Error scanning voice assets: {e}")

    def get_expression(self, key: str) -> Optional[bytes]:
        """Retrieve bytes of a pre-recorded expression."""
        path = self.expressions.get(key)
        if path and path.exists():
            return path.read_bytes()
        return None

    def get_mood_folder(self, mood: str) -> str:
        """Get the Japanese folder name for a given mood."""
        return self.config.mood_folders.get(
            mood.lower(), self.config.mood_folders["normal"]
        )


class AudioConfig(BaseModel):
    stt_backend: str = "whisper"
    tts_backend: str = "voicevox"
    voicevox_url: str = "http://localhost:50021"
    speaker_id: int = 1
    whisper_model: str = "base"
    default_mood: str = "normal"


class AudioInteractionManager:
    """
    Manages Speech-to-Text and Text-to-Speech interactions.
    Bridges the gap between raw audio and the AI Router's cognitive spine.
    """

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self._is_running = False
        self._client = httpx.AsyncClient(timeout=30.0)
        self.voice_bank = VoiceBankManager()

    async def start(self):
        self._is_running = True
        await self.voice_bank.scan_assets()
        logger.info(
            f"Audio Interaction Manager started (STT={self.config.stt_backend}, TTS={self.config.tts_backend})"
        )

    async def stop(self):
        self._is_running = False
        await self._client.aclose()
        logger.info("Audio Interaction Manager stopped.")

    async def speech_to_text(self, audio_data: bytes) -> str:
        """Transcribe audio data to text."""
        if self.config.stt_backend == "whisper":
            logger.warning("Local Whisper STT not yet fully implemented, using mock.")
            return "Hello, this is a transcribed test message."
        return "STT_NOT_IMPLEMENTED"

    async def text_to_speech(self, text: str, mood: str = "normal") -> Optional[bytes]:
        """Convert text to speech audio data."""
        # 1. Check for dedicated expressions first
        clean_text = text.lower().strip("!.,? ")
        if clean_text in self.voice_bank.expressions:
            audio = self.voice_bank.get_expression(clean_text)
            if audio:
                logger.info(f"Using pre-recorded expression for: {clean_text}")
                return audio

        # 2. Synthesis fallback
        if self.config.tts_backend == "voicevox":
            logger.debug(
                f"Synthesizing with mood: {mood} (folder: {self.voice_bank.get_mood_folder(mood)})"
            )
            return await self._process_voicevox(text)

        return None

    async def _process_voicevox(self, text: str) -> Optional[bytes]:
        """Process TTS via VOICEVOX engine."""
        try:
            query_res = await self._client.post(
                f"{self.config.voicevox_url}/audio_query",
                params={"text": text, "speaker": self.config.speaker_id},
            )
            if query_res.status_code != 200:
                return None

            synth_res = await self._client.post(
                f"{self.config.voicevox_url}/synthesis",
                params={"speaker": self.config.speaker_id},
                json=query_res.json(),
            )
            return synth_res.content if synth_res.status_code == 200 else None
        except Exception as e:
            logger.error(f"VOICEVOX processing error: {e}")
            return None

    async def process_interaction(
        self,
        audio_in: Optional[bytes] = None,
        text_in: Optional[str] = None,
        mood: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Processes a full interaction loop."""
        text = text_in
        if audio_in and not text:
            text = await self.speech_to_text(audio_in)

        if not text:
            return {"error": "No input provided"}

        # Determine mood
        detected_mood = mood or self.config.default_mood
        lower_text = text.lower()
        if any(w in lower_text for w in ["urgent", "critical", "error", "warning"]):
            detected_mood = "shout"
        elif any(w in lower_text for w in ["quiet", "secret", "whisper"]):
            detected_mood = "whisper"

        if bus.event_bus:
            await bus.event_bus.publish(
                Event(
                    topic="user.interaction",
                    payload={
                        "text": text,
                        "source": "audio" if audio_in else "text",
                        "mood": detected_mood,
                    },
                    correlation_id="voice-interaction",
                )
            )

        response_text = (
            f"I heard you say: '{text}'. How can I help with the RAPHAEL ecosystem?"
        )
        audio_out = await self.text_to_speech(response_text, mood=detected_mood)

        return {
            "input_text": text,
            "response_text": response_text,
            "detected_mood": detected_mood,
            "audio_output": audio_out.hex() if audio_out else None,
        }


interaction_manager = AudioInteractionManager()
