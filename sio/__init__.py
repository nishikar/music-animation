"""Shake It Off — Himalayan synthwave music visualizer (ModernGL + Pygame)."""

from __future__ import annotations

BPM = 118.0
BEAT_SEC = 60.0 / BPM
SONG_DURATION = 4 * 60 + 32  # 4:32
WIDTH, HEIGHT = 1080, 720  # match seek_and_destroy_mv.py
FPS = 60

AUDIO_CANDIDATES = (
    "shake_it_off.mp3",
    "shake_it_off_stub.mp3",
)

# Scene timeline (seconds)
SCENES = (
    (0.0, 41.0, "mountain"),
    (41.0, 72.0, "mandala"),
    (72.0, 158.0, "corridor"),
    (158.0, 186.0, "chai"),
    (186.0, 235.0, "pagoda"),
    (235.0, SONG_DURATION, "twilight"),
)

# Palette
INDIGO = (0.05, 0.04, 0.14)
MAGENTA = (0.85, 0.15, 0.55)
CYAN = (0.15, 0.85, 0.95)
VERMILLION = (0.95, 0.18, 0.12)
MARIGOLD = (1.0, 0.72, 0.12)
GOLD = (0.98, 0.82, 0.22)
TEEJ_RED = (0.86, 0.08, 0.18)
AMBER = (1.0, 0.55, 0.12)
PLUM = (0.35, 0.08, 0.28)
CRIMSON = (0.55, 0.05, 0.12)
