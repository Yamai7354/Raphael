import os
import sys
import asyncio
import subprocess
import logging
import json
import time
from typing import Optional

# Fix path to include 'src' if not present
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import speech_recognition as sr
from agents.voice_utils import HanamaruSynthesizer
import ollama

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("VoiceOrchestrator")


class VoiceOrchestrator:
    """
    Agent responsible for English STT, En->Ja Translation, and synthesis.
    Works in an 'always listening' loop.
    """

    def __init__(self, assets_path: str, stats_file: str):
        self.assets_path = assets_path
        self.stats_file = stats_file
        self.synthesizer = HanamaruSynthesizer(assets_path)
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300  # Adjust based on environment
        self.recognizer.dynamic_energy_threshold = True
        self.is_listening = False
        self.wake_words = ["raphael", "hanamaru", "hana-chan", "raffaele"]
        self.is_awake = False
        self.last_wake_time = 0
        self.wake_timeout = 10  # Seconds to stay awake after trigger

    async def translate_to_japanese(self, text: str) -> str:
        """
        Translates English text to Japanese using the local LLM.
        """
        try:
            prompt = f"Translate the following English phrase into Japanese for a helpful AI assistant. Respond in polite Japanese (desu/masu). Provide ONLY the translation. English: {text}"
            # Using a faster model for real-time translation
            response = ollama.generate(model="llama3:8b", prompt=prompt)
            translation = response["response"].strip()
            # Remove quotes if generated
            translation = translation.replace('"', "").replace("'", "")
            return translation
        except Exception as e:
            logger.error(f"Translation Error: {e}")
            return "すみません、翻訳中にエラーが発生しました。"

    def update_dashboard_subtitles(self, english: str, japanese: str):
        """
        Updates the stats.json with the latest subtitles for the dashboard.
        """
        try:
            data = {}
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r") as f:
                    data = json.load(f)

            data["subtitles"] = {
                "en": english,
                "ja": japanese,
                "timestamp": time.strftime("%H:%M:%S"),
            }

            # Update feed
            if "feed" not in data:
                data["feed"] = []
            data["feed"].insert(
                0,
                {
                    "type": "Observation",
                    "time": time.strftime("%H:%M:%S"),
                    "summary": f"Voice Input: {english}",
                },
            )
            data["feed"] = data["feed"][:10]

            with open(self.stats_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Dashboard Update Error: {e}")

    async def process_command(self, english_text: str):
        """
        The full pipeline: Listen -> Translate -> Synthesize -> Play
        """
        if not english_text or len(english_text.strip()) < 2:
            return

        logger.info(f"🎤 Transcribed: {english_text}")

        # 1. Translate
        japanese_text = await self.translate_to_japanese(english_text)
        logger.info(f"🎌 Translation: {japanese_text}")

        # 2. Update Dashboard (Subtitles)
        self.update_dashboard_subtitles(english_text, japanese_text)

        # 3. Synthesize
        output_wav = "response.wav"
        try:
            await self.synthesizer.synthesize(japanese_text, output_wav)

            # 4. Playback (afplay is built into macOS)
            subprocess.run(["afplay", output_wav], check=True)
        except Exception as e:
            logger.error(f"Synthesis/Playback Error: {e}")

    async def _handle_audio_input(self, transcript: str):
        """Processes the transcript and toggles wake state."""
        clean_text = transcript.lower().strip()

        # Check for wake words
        found_wake = any(ww in clean_text for ww in self.wake_words)

        if found_wake:
            self.is_awake = True
            self.last_wake_time = int(time.time())
            logger.info("✨ Raphael is AWAKE.")
            # If they just said the wake word, maybe respond with a short sound or synthesis
            if len(clean_text.split()) <= 2:  # "Hey Raphael"
                try:
                    await self.synthesizer.synthesize("はい、なんでしょう？", "wake.wav")
                    subprocess.run(["afplay", "wake.wav"], check=True)
                except Exception as e:
                    logger.error(f"Wake Sound Error: {e}")
                return

        # Regular processing if awake
        if self.is_awake:
            # Check for timeout
            if time.time() - self.last_wake_time > self.wake_timeout:
                self.is_awake = False
                logger.info("💤 Raphael is sleeping...")
                return

            # Reset timeout on activity
            self.last_wake_time = int(time.time())

            # Remove wake word from processing to avoid "Raphael what time is it" -> "なんですか ラファエル"
            processing_text = transcript
            for ww in self.wake_words:
                processing_text = processing_text.lower().replace(ww, "").strip()

            if processing_text:
                await self.process_command(processing_text)

    def _listen_callback(self, recognizer, audio):
        """
        Callback for background listening.
        """
        try:
            transcript = recognizer.recognize_google(audio, language="en-US")
            asyncio.run_coroutine_threadsafe(self._handle_audio_input(transcript), self.loop)
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            logger.error(f"STT Service Error: {e}")

    async def start(self):
        """
        Starts the background listening loop.
        """
        self.loop = asyncio.get_running_loop()
        logger.info("🎤 Voice Orchestrator starting... (Always Listening)")

        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

        # Non-blocking background listening
        self.stop_listening = self.recognizer.listen_in_background(
            sr.Microphone(), self._listen_callback
        )
        self.is_listening = True

        while self.is_listening:
            await asyncio.sleep(1)

    def stop(self):
        self.is_listening = False
        if hasattr(self, "stop_listening"):
            self.stop_listening(wait_for_stop=False)
        logger.info("🎤 Voice Orchestrator stopped.")


if __name__ == "__main__":
    assets = "/Users/yamai/ai/speech"
    stats = "/Users/yamai/ai/Raphael/swarm-dashboard/public/stats.json"
    orchestrator = VoiceOrchestrator(assets, stats)

    try:
        asyncio.run(orchestrator.start())
    except KeyboardInterrupt:
        orchestrator.stop()
