"""Global timing, resolution, and path constants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FPS = 30
SONG_DURATION = 337.0  # 5m 37s
TOTAL_FRAMES = int(SONG_DURATION * FPS)  # 10110

PREVIEW_WIDTH = 1280
PREVIEW_HEIGHT = 720
EXPORT_WIDTH = 1920
EXPORT_HEIGHT = 1080

AUDIO_CANDIDATES = (
    ROOT / "rhcp_ds.mp3",
    ROOT / "assets" / "audio" / "rhcp_ds.mp3",
)

DEFAULT_EXPORT_PATH = ROOT / "desecration_smile.mp4"

# Scene time windows (seconds)
SCENES = (
    ("crawl", 0.0, 14.0),
    ("europe", 14.0, 52.0),
    ("istanbul", 52.0, 75.0),
    ("persia", 75.0, 112.0),
    ("khyber", 112.0, 165.0),
    ("varanasi", 165.0, 204.0),
    ("himalaya", 204.0, 245.0),
    ("kathmandu", 245.0, 280.0),
    ("rooftop", 280.0, 320.0),
    ("outro", 320.0, 337.0),
)

CRAWL_TEXT = (
    "The Chili Peppers travel\n"
    "the silk route to Nepal\n"
    "to meet the legendary\n"
    "Narayan Gopal"
)

CAMERA_UBO_BINDING = 0
CAMERA_UBO_SIZE = 144  # 2 * mat4 (64*2) + vec4 (16) = 144

GOLD_CRAWL = (1.0, 0.910, 0.122)  # #FFE81F
