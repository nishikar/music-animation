"""Timeline, display, palette, and path configuration."""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1280, 720
CX, CY = WIDTH / 2.0, HEIGHT / 2.0
FPS = 30
SONG_DURATION = 7 * 60 + 51  # 07:51 exactly

SCRIPT_DIR = Path(__file__).resolve().parent.parent
AUDIO_FILE = SCRIPT_DIR / "hey_joe.mp3"
DEFAULT_EXPORT = SCRIPT_DIR / "hey_joe.mp4"

# ---------------------------------------------------------------------------
# Scene timeline (start seconds inclusive)
# ---------------------------------------------------------------------------
SCENE_TIMES = [
    (0.0, 45.0, "nada"),          # Primordial Resonance
    (45.0, 90.0, "enigma"),       # Revolving Enigma
    (90.0, 140.0, "raudra"),      # Flare of Raudra
    (140.0, 185.0, "paisley"),    # Fatal Descent
    (185.0, 240.0, "confession"), # Polyrhythmic Confession
    (240.0, 320.0, "jhala"),      # Raga-Rock Solo
    (320.0, 380.0, "desert"),     # Desert Flight
    (380.0, 435.0, "wings"),      # Unraveling Noose & Wings
    (435.0, 471.0, "samadhi"),    # Dissolution / Samadhi
]

TRANSITION_SEC = 1.8  # soft crossfade between scenes

# ---------------------------------------------------------------------------
# Palette (RGB 0–1 floats) — named for scene use
# ---------------------------------------------------------------------------
MIDNIGHT_NAVY = (0.04, 0.06, 0.16)
DARK_INDIGO = (0.10, 0.08, 0.28)
GOLD = (0.95, 0.78, 0.22)
MARIGOLD = (0.98, 0.72, 0.12)
IVORY = (0.97, 0.94, 0.86)
DEEP_AMETHYST = (0.28, 0.12, 0.38)
CHARCOAL = (0.10, 0.10, 0.12)
NAVY = (0.06, 0.10, 0.24)
BLOOD_CRIMSON = (0.72, 0.05, 0.08)
VOLCANIC_BURGUNDY = (0.38, 0.04, 0.10)
ELECTRIC_SAFFRON = (1.0, 0.72, 0.05)
PEACOCK_TEAL = (0.05, 0.28, 0.32)
ACID_PURPLE = (0.55, 0.08, 0.72)
MAGENTA = (0.85, 0.10, 0.55)
SAFFRON = (0.98, 0.62, 0.08)
TEAL = (0.08, 0.55, 0.52)
TERRACOTTA = (0.78, 0.32, 0.14)
ROYAL_BLUE = (0.12, 0.28, 0.78)
TURQUOISE = (0.15, 0.72, 0.68)
VIOLET = (0.42, 0.18, 0.58)
DARK_GOLD = (0.55, 0.42, 0.12)
BINDU_GOLD = (1.0, 0.86, 0.35)
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
