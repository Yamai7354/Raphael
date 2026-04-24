import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock all external dependencies before importing VoiceOrchestrator
sys.modules["speech_recognition"] = MagicMock()
sys.modules["ollama"] = MagicMock()
sys.modules["pykakasi"] = MagicMock()
sys.modules["pydub"] = MagicMock()

import asyncio
from agents.voice_orchestrator import VoiceOrchestrator

async def test_process_command_uses_subprocess():
    print("Running test_process_command_uses_subprocess...")
    stats_file = "test_stats.json"
    with open(stats_file, "w") as f:
        f.write("{}")

    with patch("agents.voice_orchestrator.HanamaruSynthesizer"), \
         patch("speech_recognition.Recognizer"), \
         patch("agents.voice_orchestrator.sr.Microphone"):
        orchestrator = VoiceOrchestrator(assets_path="/tmp/assets", stats_file=stats_file)

        orchestrator.translate_to_japanese = AsyncMock(return_value="こんにちは")
        orchestrator.synthesizer.synthesize = AsyncMock()

        with patch("subprocess.run") as mock_run:
            await orchestrator.process_command("hello")
            mock_run.assert_called_once_with(["afplay", "response.wav"], check=True)
            print("  - Passed!")

async def test_handle_audio_input_wake_word_uses_subprocess():
    print("Running test_handle_audio_input_wake_word_uses_subprocess...")
    stats_file = "test_stats.json"

    with patch("agents.voice_orchestrator.HanamaruSynthesizer"), \
         patch("speech_recognition.Recognizer"), \
         patch("agents.voice_orchestrator.sr.Microphone"):
        orchestrator = VoiceOrchestrator(assets_path="/tmp/assets", stats_file=stats_file)
        orchestrator.synthesizer.synthesize = AsyncMock()

        with patch("subprocess.run") as mock_run:
            await orchestrator._handle_audio_input("raphael")
            mock_run.assert_called_once_with(["afplay", "wake.wav"], check=True)
            print("  - Passed!")

async def main():
    try:
        await test_process_command_uses_subprocess()
        await test_handle_audio_input_wake_word_uses_subprocess()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
