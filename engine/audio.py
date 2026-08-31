"""Audio timeline helpers with procedural mock fallback."""

from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path
from typing import Optional

import pygame

from .config import AUDIO_CANDIDATES, SONG_DURATION


def find_audio() -> Optional[Path]:
    for p in AUDIO_CANDIDATES:
        if p.is_file():
            return p
    return None


def synthesize_mock_audio(path: Path, duration: float = SONG_DURATION, sample_rate: int = 22050) -> Path:
    """Write a lightweight procedural WAV used when the MP3 is missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(duration * sample_rate)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n):
            t = i / sample_rate
            # fingerpicked-ish plucked envelope + soft drone + tabla-ish pulse
            env = 0.35 * math.exp(-((t % 0.55) * 4.0))
            tone = math.sin(2 * math.pi * 196 * t) * 0.25 + math.sin(2 * math.pi * 293.66 * t) * 0.12
            drone = math.sin(2 * math.pi * 98 * t) * 0.08
            tabla = (0.2 if (t % 0.5) < 0.04 else 0.0) * math.sin(2 * math.pi * 90 * t)
            # gentle scene swells
            swell = 0.5 + 0.5 * math.sin(2 * math.pi * t / 40.0)
            sample = (tone * env + drone + tabla) * swell * 0.85
            sample = max(-1.0, min(1.0, sample))
            frames += struct.pack("<h", int(sample * 30000))
        wf.writeframes(frames)
    return path


def ensure_audio() -> Path:
    found = find_audio()
    if found is not None:
        return found
    mock = Path(tempfile.gettempdir()) / "desecration_smile_mock.wav"
    return synthesize_mock_audio(mock)


class AudioClock:
    """pygame.mixer playback — visual time still driven by frame index."""

    def __init__(self, audio_path: Path, start_muted: bool = False):
        self.path = audio_path
        self.enabled = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.load(str(audio_path))
            self.enabled = True
            if start_muted:
                pygame.mixer.music.set_volume(0.0)
            else:
                pygame.mixer.music.set_volume(1.0)
        except pygame.error:
            self.enabled = False

    def play(self, start_seconds: float = 0.0) -> None:
        if not self.enabled:
            return
        try:
            pygame.mixer.music.play(start=max(0.0, start_seconds))
        except TypeError:
            # older pygame without start=
            pygame.mixer.music.play()

    def stop(self) -> None:
        if self.enabled:
            pygame.mixer.music.stop()
