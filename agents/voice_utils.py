import os
import sys
import asyncio
import logging
from typing import List, Dict, Optional
from pydub import AudioSegment
import pykakasi
import json

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("VoiceUtils")

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if project_root not in sys.path:
    sys.path.append(project_root)


class HanamaruSynthesizer:
    """
    A lightweight concatenative synthesizer using Mambetsu Hanamaru voice assets.
    """

    def __init__(self, assets_path: str):
        self.assets_path = assets_path
        self.kks = pykakasi.kakasi()
        self.phoneme_map = self._load_phoneme_map()
        self.pre_recorded_phrases = self._load_pre_recorded_phrases()

    def _load_phoneme_map(self) -> Dict[str, str]:
        """
        Maps phonemes (Hiragana/Romaji) to .wav file paths in the UTAU library using oto.ini.
        """
        mapping = {}
        usual_path = os.path.join(self.assets_path, "満別花丸通常連続音")
        syllable_dirs = ["A4", "C4", "F4", "裏声"]

        for s_dir in syllable_dirs:
            full_dir = os.path.join(usual_path, s_dir)
            oto_path = os.path.join(full_dir, "oto.ini")
            if not os.path.exists(oto_path):
                continue

            content = ""
            for encoding in ["shift-jis", "utf-8", "cp932"]:
                try:
                    with open(oto_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if not content:
                continue

            for line in content.splitlines():
                if "=" not in line or "," not in line:
                    continue
                parts = line.split("=")
                wav_file = parts[0].strip()
                params = parts[1].split(",")
                alias = params[0].strip()

                # UTAU aliases can be "a", "あ", or "a あA4"
                # We normalize and map to as many variants as possible
                alias_parts = alias.split(" ")
                for p in alias_parts:
                    # Clean suffixes like A4, C4
                    clean = p
                    for tone in syllable_dirs:
                        clean = clean.replace(tone, "")
                    clean = clean.lower().strip()
                    if clean and clean not in mapping:
                        mapping[clean] = os.path.join(full_dir, wav_file)

        logger.info(f"Loaded {len(mapping)} phoneme aliases.")
        return mapping

    def _load_pre_recorded_phrases(self) -> Dict[str, str]:
        """
        Maps specific Japanese phrases to pre-recorded high-quality .wav files.
        """
        phrases = {}
        source_dir = os.path.join(self.assets_path, "満別花丸_ボイス素材（仮）")
        if os.path.exists(source_dir):
            for f in os.listdir(source_dir):
                if f.endswith(".wav"):
                    # Example filename: "4_こんにちは_1.wav"
                    parts = f.split("_")
                    if len(parts) >= 2:
                        phrase = parts[1]
                        if phrase not in phrases:
                            phrases[phrase] = os.path.join(source_dir, f)
        return phrases

    def text_to_phonemes(self, text: str) -> List[str]:
        """
        Converts Japanese text to a list of Hiragana/Romaji phonemes.
        """
        result = self.kks.convert(text)
        phonemes = []
        for item in result:
            # UTAU banks often use Hiragana aliases. Let's try both.
            hira = item["kana"]
            romaji = item["hepburn"].lower()

            # Simple Hiragana split (e.g., "こんにちは" -> ["こ", "ん", "に", "ち", "は"])
            for char in hira:
                phonemes.append(char)

            # Also add Romaji if it's a special character or single sound
            if not hira:
                phonemes.append(romaji)
        return phonemes

    async def synthesize(self, text: str, output_path: str):
        """
        Stitches together audio samples for the given text.
        """
        # 1. Check for pre-recorded phrase first
        if text in self.pre_recorded_phrases:
            audio = AudioSegment.from_wav(self.pre_recorded_phrases[text])
            audio.export(output_path, format="wav")
            return

        # 2. Dynamic synthesis
        phonemes = self.text_to_phonemes(text)
        combined = AudioSegment.empty()

        for p in phonemes:
            if p in self.phoneme_map:
                segment = AudioSegment.from_wav(self.phoneme_map[p])
                # UTAU samples are often long; we'd ideally use oto.ini to crop them.
                # For MVP, we'll just take the first 300ms if it's too long.
                if len(segment) > 300:
                    segment = segment[:300]

                if len(combined) > 0:
                    combined = combined.append(segment, crossfade=15)
                else:
                    combined = segment
            else:
                # Add silence for unknown phonemes
                combined += AudioSegment.silent(duration=100)

        if len(combined) > 0:
            combined.export(output_path, format="wav")
        else:
            raise ValueError(f"Could not synthesize any audio for text: {text}")


if __name__ == "__main__":
    # Test script
    assets = "/Users/yamai/ai/speech"
    syn = HanamaruSynthesizer(assets)
    asyncio.run(syn.synthesize("こんにちは", "test_output.wav"))
    print("Test synthesis complete.")
