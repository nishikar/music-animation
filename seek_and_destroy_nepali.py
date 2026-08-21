import argparse
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import pygame

# ==============================================================================
# CONFIGURATION & 72 BPM METRIC TIMING
# ==============================================================================
WIDTH, HEIGHT = 1080, 608
FPS = 60
SONG_DURATION_SEC = 313.0  # 5 min 13 sec
BPM = 72.0
BEAT_SEC = 60.0 / BPM
BAR_SEC = BEAT_SEC * 4

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EXPORT_PATH = SCRIPT_DIR / "seek_and_destroy_nepali.mp4"
AUDIO_CANDIDATES = [
    SCRIPT_DIR / "seek_and_destroy_nepali_audio.mp3",
    SCRIPT_DIR / "seek_and_destroy_nepali.mp3",
]

# Palette: Traditional Kathmandu Valley Twilight
COLOR_BLACK = (10, 8, 14)
COLOR_NIGHT_SKY_TOP = (18, 22, 48)
COLOR_NIGHT_SKY_BOT = (72, 48, 68)
COLOR_BRICK_BASE = (148, 58, 46)
COLOR_BRICK_DARK = (88, 34, 28)
COLOR_BRICK_HIGHLIGHT = (178, 78, 58)
COLOR_WOOD_CARVING = (32, 18, 14)
COLOR_GOLD = (245, 195, 60)
COLOR_MARIGOLD_ORANGE = (245, 130, 20)
COLOR_MARIGOLD_YELLOW = (255, 215, 40)
COLOR_STEEL = (220, 230, 245)
COLOR_SNOW = (210, 218, 232)
COLOR_HAZE = (120, 100, 130)

COLOR_HAKU_PATASI_BLACK = (20, 18, 22)
COLOR_HAKU_PATASI_RED = (185, 30, 38)
COLOR_PATUKA_YELLOW = (235, 180, 35)
COLOR_CHOLO_CRIMSON = (145, 25, 35)
COLOR_DAURA_SURUWAL = (46, 38, 46)
COLOR_BLAZER_DARK = (30, 28, 34)
COLOR_SKIN = (212, 160, 126)
COLOR_SKIN_SHADOW = (175, 125, 95)
COLOR_CARPET_RED = (120, 30, 35)

DANCE_ROUTINES = [
    ("MARUNI CHHALANG", "Flowing side-cross strides with sweeping mudras"),
    ("CHARYA DIP & WRIST TWIRL", "Deep knee dip on downbeats with wrist circles"),
    ("GHUMAURO PIRUETTES", "Graceful whirls locked to half-bar phrases"),
    ("ANJALI & TAALI STEP", "Namaste arches and courtyard cross-steps on beats"),
]

# ==============================================================================
# FFMPEG EXPORT
# ==============================================================================
class FfmpegRecorder:
    """Pipe raw RGB frames to ffmpeg and mux optional audio into an MP4."""

    def __init__(self, output_path, fps=FPS, width=WIDTH, height=HEIGHT, audio_path=None):
        self.output_path = Path(output_path)
        self.frame_size = width * height * 3
        self._proc = None
        self.frames_written = 0

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{width}x{height}", "-pix_fmt", "rgb24",
            "-r", str(fps), "-i", "-",
        ]
        self._has_audio = audio_path is not None and Path(audio_path).is_file()
        if self._has_audio:
            cmd.extend(["-i", str(audio_path)])

        cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"])
        if self._has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.extend(["-t", str(SONG_DURATION_SEC)])
        cmd.append(str(self.output_path))

        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    def write_frame(self, surface):
        if self._proc is None or self._proc.stdin is None:
            return
        raw = pygame.image.tostring(surface, "RGB")
        self._proc.stdin.write(raw)
        self.frames_written += 1

    def close(self):
        if self._proc is None:
            return
        if self._proc.stdin:
            self._proc.stdin.close()
        stderr = self._proc.stderr.read().decode("utf-8", errors="replace") if self._proc.stderr else ""
        rc = self._proc.wait()
        self._proc = None
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed (exit {rc}):\n{stderr[-2000:]}")
        return self.output_path


def resolve_audio_path():
    for path in AUDIO_CANDIDATES:
        if not path.is_file():
            continue
        with open(path, "rb") as fh:
            header = fh.read(4)
        if header[:3] == b"ID3" or header[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
            return path
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Seek & Destroy Nepali folk dance animation")
    parser.add_argument("--export", "-e", action="store_true", help="Render to MP4 via ffmpeg")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_EXPORT_PATH, help="Output MP4 path")
    parser.add_argument("--no-preview", action="store_true", help="Headless export (SDL dummy driver)")
    parser.add_argument("--hud", action="store_true", help="Include HUD in exported video")
    return parser.parse_args()


# ==============================================================================
# TIMING & MATH HELPERS
# ==============================================================================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def beat_clock(current_sec):
    """Return beat-aligned timing values for 72 BPM choreography."""
    beat_index = current_sec / BEAT_SEC
    beat_frac = beat_index - int(beat_index)
    bar_index = int(beat_index // 4)
    bar_frac = (beat_index % 4) / 4.0
    beat_pulse = math.sin(beat_frac * math.pi)
    downbeat = beat_frac < 0.12 or beat_frac > 0.88
    phrase_beat = int(beat_index) % 8
    phrase_frac = phrase_beat + beat_frac
    return {
        "beat_index": beat_index,
        "beat_frac": beat_frac,
        "bar_index": bar_index,
        "bar_frac": bar_frac,
        "beat_pulse": beat_pulse,
        "downbeat": downbeat,
        "phrase_beat": phrase_beat,
        "phrase_frac": phrase_frac,
        "cycle": beat_index * math.pi * 2,
        "bar_cycle": bar_frac * math.pi * 2,
    }


def solve_2bone_ik(p_root, p_target, l1, l2, bend_forward=True):
    rx, ry = p_root
    tx, ty = p_target
    dx = tx - rx
    dy = ty - ry
    dist = clamp(math.hypot(dx, dy), 1.0, l1 + l2 - 0.5)
    base_angle = math.atan2(dy, dx)
    cos_a = clamp((l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist), -1.0, 1.0)
    angle_a = math.acos(cos_a)
    joint_angle = (base_angle - angle_a) if bend_forward else (base_angle + angle_a)
    return (rx + l1 * math.cos(joint_angle), ry + l1 * math.sin(joint_angle))


def draw_limb(surface, p1, p2, width, color, joint_r=0):
    pygame.draw.line(surface, color, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), int(width))
    if joint_r > 0:
        pygame.draw.circle(surface, color, (int(p2[0]), int(p2[1])), int(joint_r))


def draw_capsule(surface, p1, p2, radius, color):
    x1, y1 = int(p1[0]), int(p1[1])
    x2, y2 = int(p2[0]), int(p2[1])
    pygame.draw.line(surface, color, (x1, y1), (x2, y2), int(radius * 2))
    pygame.draw.circle(surface, color, (x1, y1), int(radius))
    pygame.draw.circle(surface, color, (x2, y2), int(radius))


# ==============================================================================
# REALISTIC PALM FLAME
# ==============================================================================
class RealisticPalmFire:
    """Layered flame tongues with turbulence, heat glow, and ember sparks."""

    def __init__(self):
        self.particles = []
        self.time = 0.0

    def update_and_draw(self, surface, x, y, intensity=1.0):
        self.time += 1.0 / FPS
        spawn_count = int(4 + intensity * 3)
        for _ in range(spawn_count):
            turb = math.sin(self.time * 14.0 + random.uniform(-1, 1)) * 0.6
            self.particles.append({
                "x": x + random.uniform(-3.0, 3.0),
                "y": y + random.uniform(-1.0, 1.0),
                "vx": turb + random.uniform(-0.5, 0.5),
                "vy": random.uniform(-3.8, -1.8),
                "life": random.uniform(0.6, 1.0),
                "max_life": 1.0,
                "size": random.uniform(3.0, 7.0),
                "hue": random.uniform(0.0, 1.0),
            })

        for p in self.particles[:]:
            p["life"] -= 0.045
            p["vy"] -= 0.06
            p["vx"] *= 0.97
            p["x"] += p["vx"] + math.sin(self.time * 18 + p["y"] * 0.05) * 0.35
            p["y"] += p["vy"]
            p["size"] *= 0.96

            if p["life"] <= 0 or p["size"] < 0.5:
                self.particles.remove(p)
                continue

            life_r = p["life"] / p["max_life"]
            r = max(1, int(p["size"] * life_r))
            if life_r > 0.75:
                col = (255, 252, 230)
            elif life_r > 0.5:
                col = (255, 220, 80)
            elif life_r > 0.25:
                col = (255, 140, 35)
            else:
                col = (180, 45, 15)
            alpha = int(220 * life_r * intensity)

            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, alpha), (r + 2, r + 2), r)
            if life_r > 0.6:
                pygame.draw.circle(s, (255, 255, 240, int(alpha * 0.6)), (r + 2, r + 2), max(1, r // 2))
            surface.blit(s, (int(p["x"] - r - 2), int(p["y"] - r - 2)), special_flags=pygame.BLEND_ADD)

        # Heat halo and blue-white core at palm
        halo_r = int(34 * intensity)
        halo = pygame.Surface((halo_r * 2, halo_r * 2), pygame.SRCALPHA)
        for hr in range(halo_r, 0, -4):
            alpha = int(22 * (1.0 - hr / halo_r) * intensity)
            pygame.draw.circle(halo, (255, 120, 30, alpha), (halo_r, halo_r), hr)
        surface.blit(halo, (int(x - halo_r), int(y - halo_r - 6)), special_flags=pygame.BLEND_ADD)

        core_r = int(8 + math.sin(self.time * 22) * 2)
        core = pygame.Surface((core_r * 2 + 4, core_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(core, (180, 220, 255, int(90 * intensity)), (core_r + 2, core_r + 2), core_r)
        pygame.draw.circle(core, (255, 250, 220, int(160 * intensity)), (core_r + 2, core_r + 2), max(2, core_r // 2))
        surface.blit(core, (int(x - core_r - 2), int(y - core_r - 8)), special_flags=pygame.BLEND_ADD)


# ==============================================================================
# HIMALAYAN BACKDROP
# ==============================================================================
MOUNTAIN_LAYERS = [
    {"base_y": 268, "points": [(0, 268), (90, 210), (210, 248), (340, 175), (480, 230), (620, 155),
                               (760, 205), (900, 168), (1020, 220), (1080, 198), (1080, 608), (0, 608)],
     "fill": (28, 26, 42), "snow": [(340, 175), (355, 188), (325, 195), (340, 175)]},
    {"base_y": 288, "points": [(0, 288), (140, 248), (280, 268), (420, 215), (560, 252), (700, 218),
                               (840, 248), (980, 228), (1080, 248), (1080, 608), (0, 608)],
     "fill": (22, 22, 36), "snow": [(420, 215), (432, 228), (408, 232), (420, 215)]},
    {"base_y": 308, "points": [(0, 308), (120, 278), (260, 295), (400, 258), (540, 285), (680, 262),
                               (820, 288), (960, 270), (1080, 292), (1080, 608), (0, 608)],
     "fill": (18, 18, 30), "snow": []},
]


def draw_gradient_sky(surface, top_color, bottom_color):
    for y in range(0, HEIGHT, 2):
        ratio = y / float(HEIGHT)
        color = lerp_color(top_color, bottom_color, ratio)
        pygame.draw.line(surface, color, (0, y), (WIDTH, y), 2)


def draw_stars(surface, current_sec, beat_pulse):
    random.seed(42)
    for i in range(80):
        sx = random.randint(20, WIDTH - 20)
        sy = random.randint(18, 180)
        twinkle = 0.55 + 0.45 * math.sin(current_sec * 2.5 + i * 1.7)
        alpha = int(120 + twinkle * 80 + beat_pulse * 20)
        size = 1 if i % 3 else 2
        star = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(star, (240, 235, 255, alpha), (size + 1, size + 1), size)
        surface.blit(star, (sx, sy))


def draw_moon(surface, current_sec):
    mx, my = WIDTH - 120, 72
    glow = pygame.Surface((100, 100), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 230, 180, 35), (50, 50), 42)
    surface.blit(glow, (mx - 50, my - 50), special_flags=pygame.BLEND_ADD)
    pygame.draw.circle(surface, (235, 225, 200), (mx, my), 22)
    pygame.draw.circle(surface, (220, 215, 195), (mx - 6, my - 4), 18)


def draw_himalayan_backdrop(surface, current_sec, beat_pulse):
    draw_gradient_sky(surface, COLOR_NIGHT_SKY_TOP, (
        int(COLOR_NIGHT_SKY_BOT[0] + beat_pulse * 14),
        int(COLOR_NIGHT_SKY_BOT[1] + beat_pulse * 10),
        int(COLOR_NIGHT_SKY_BOT[2] + beat_pulse * 8),
    ))
    draw_stars(surface, current_sec, beat_pulse)
    draw_moon(surface, current_sec)

    haze_shift = math.sin(current_sec * 0.15) * 4
    for layer_idx, layer in enumerate(MOUNTAIN_LAYERS):
        pts = [(x + haze_shift * (layer_idx + 1) * 0.15, y) for x, y in layer["points"]]
        pygame.draw.polygon(surface, layer["fill"], pts)
        if layer["snow"]:
            pygame.draw.polygon(surface, COLOR_SNOW, layer["snow"])
            peak = layer["snow"][0]
            snow_glow = pygame.Surface((30, 30), pygame.SRCALPHA)
            pygame.draw.circle(snow_glow, (255, 255, 255, 40), (15, 15), 12)
            surface.blit(snow_glow, (peak[0] - 15, peak[1] - 15), special_flags=pygame.BLEND_ADD)

    # Atmospheric haze over distant peaks
    haze = pygame.Surface((WIDTH, 120), pygame.SRCALPHA)
    for hy in range(0, 120, 4):
        alpha = int(35 * (1.0 - hy / 120))
        pygame.draw.line(haze, (*COLOR_HAZE, alpha), (0, hy), (WIDTH, hy))
    surface.blit(haze, (0, 200))

    # Foreground ridge silhouette
    pygame.draw.polygon(surface, (14, 12, 20), [
        (0, 340), (180, 318), (360, 332), (540, 310), (720, 325), (900, 308), (1080, 322),
        (1080, HEIGHT), (0, HEIGHT),
    ])


# ==============================================================================
# DETAILED PAGODA TEMPLE (NYATAPOLA-STYLE)
# ==============================================================================
def draw_brick_wall(surface, rect, mortar_color=(60, 28, 22)):
    x, y, w, h = rect
    pygame.draw.rect(surface, COLOR_BRICK_BASE, rect)
    for row in range(int(y), int(y + h), 8):
        offset = 0 if (row // 8) % 2 == 0 else 14
        for col in range(int(x) + offset, int(x + w), 28):
            brick_w = min(24, int(x + w - col - 2))
            if brick_w > 4:
                shade = COLOR_BRICK_DARK if (col + row) % 3 == 0 else COLOR_BRICK_HIGHLIGHT
                pygame.draw.rect(surface, shade, (col, row, brick_w, 6))
    pygame.draw.rect(surface, mortar_color, rect, 1)


def draw_tier_roof(surface, cx, eave_y, half_w, scale, upward=True):
    tip_y = eave_y - (22 if upward else 16) * scale
    overhang = 20 * scale
    pts = [
        (cx - half_w - overhang, eave_y + 5 * scale),
        (cx - half_w, eave_y),
        (cx + half_w, eave_y),
        (cx + half_w + overhang, eave_y + 5 * scale),
        (cx, tip_y),
    ]
    pygame.draw.polygon(surface, COLOR_WOOD_CARVING, pts)
    pygame.draw.lines(surface, (190, 75, 45), False, pts[:4], max(1, int(2 * scale)))
    # Carved bracket row
    for bx in range(int(cx - half_w + 8 * scale), int(cx + half_w - 8 * scale), int(14 * scale)):
        bracket_h = 8 * scale
        pygame.draw.polygon(surface, (48, 26, 18), [
            (bx, eave_y), (bx + 4 * scale, eave_y - bracket_h), (bx + 8 * scale, eave_y),
        ])


def draw_lattice_window(surface, cx, cy, w, h):
    frame = pygame.Rect(int(cx - w // 2), int(cy - h // 2), int(w), int(h))
    pygame.draw.rect(surface, (18, 10, 8), frame)
    pygame.draw.rect(surface, COLOR_GOLD, frame, 1)
    for i in range(1, 4):
        lx = frame.x + i * frame.w // 4
        pygame.draw.line(surface, COLOR_GOLD, (lx, frame.y), (lx, frame.bottom), 1)
    for i in range(1, 3):
        ly = frame.y + i * frame.h // 3
        pygame.draw.line(surface, COLOR_GOLD, (frame.x, ly), (frame.right, ly), 1)


def draw_nyatapola(surface, center_x, base_y, scale=1.0, tiers=5):
    cur_y = base_y
    # Stone plinth steps (Nyatapola has five broad terraces)
    for step in range(5):
        sw = (340 - step * 28) * scale
        step_h = 12 * scale
        shade = (70 + step * 8, 65 + step * 6, 72 + step * 5)
        pygame.draw.rect(surface, shade, (center_x - sw // 2, cur_y - step_h, sw, step_h))
        pygame.draw.line(surface, (100, 95, 105), (center_x - sw // 2, cur_y - step_h), (center_x + sw // 2, cur_y - step_h), 1)
        cur_y -= step_h

    tier_widths = [240, 190, 148, 108, 72]
    tier_heights = [38, 34, 30, 26, 22]
    for t in range(min(tiers, len(tier_widths))):
        w = tier_widths[t] * scale
        h = tier_heights[t] * scale
        wall_w = w * 0.62
        wall_rect = (center_x - wall_w // 2, cur_y - h, wall_w, h)
        draw_brick_wall(surface, wall_rect)

        # Tiki jhyaa lattice windows
        win_y = cur_y - h * 0.55
        draw_lattice_window(surface, center_x, win_y, 18 * scale, 22 * scale)
        if t < 2:
            draw_lattice_window(surface, center_x - wall_w * 0.32, win_y, 12 * scale, 16 * scale)
            draw_lattice_window(surface, center_x + wall_w * 0.32, win_y, 12 * scale, 16 * scale)

        eave_y = cur_y - h
        draw_tier_roof(surface, center_x, eave_y, w * 0.5, scale)
        cur_y = eave_y - 12 * scale

    # Gajur (golden spire with discs)
    spire_base = cur_y
    pygame.draw.rect(surface, COLOR_GOLD, (center_x - 3 * scale, spire_base - 8 * scale, 6 * scale, 8 * scale))
    for i, sr in enumerate([10, 7, 5]):
        sy = spire_base - (18 + i * 12) * scale
        pygame.draw.circle(surface, COLOR_GOLD, (int(center_x), int(sy)), int(sr * scale), max(1, int(2 * scale)))
    pygame.draw.polygon(surface, COLOR_GOLD, [
        (center_x - 4 * scale, spire_base - 42 * scale),
        (center_x + 4 * scale, spire_base - 42 * scale),
        (center_x, spire_base - 58 * scale),
    ])


def draw_marigold_garland(surface, p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    steps = 22
    for i in range(steps + 1):
        t = i / float(steps)
        gx = p1[0] + dx * t
        sag = math.sin(t * math.pi) * 20.0
        gy = p1[1] + dy * t + sag
        col = COLOR_MARIGOLD_ORANGE if i % 2 == 0 else COLOR_MARIGOLD_YELLOW
        pygame.draw.circle(surface, col, (int(gx), int(gy)), 4)
        if i % 3 == 0:
            pygame.draw.circle(surface, (255, 240, 180), (int(gx), int(gy)), 2)


def draw_cobblestones(surface, ground_y):
    pygame.draw.rect(surface, (20, 16, 20), (0, ground_y, WIDTH, HEIGHT - ground_y))
    for y in range(ground_y + 8, HEIGHT, 16):
        pygame.draw.line(surface, (35, 28, 34), (0, y), (WIDTH, y), 1)
        shift = (y * 4) % 45
        for x in range(shift, WIDTH, 60):
            pygame.draw.line(surface, (35, 28, 34), (x, y), (x, y + 16), 1)


# ==============================================================================
# NARAYAN GOPAL PERFORMER (IMPROVED HUMANOID)
# ==============================================================================
class NarayanGopalPerformer:
    def __init__(self, base_x, base_y):
        self.x = base_x
        self.y = base_y
        self.scale = 1.35

    def draw(self, surface, timing):
        s = self.scale
        bx, by = self.x, self.y
        beat_pulse = timing["beat_pulse"]
        current_sec = timing["beat_index"] * BEAT_SEC

        pygame.draw.ellipse(surface, COLOR_CARPET_RED, (bx - 65 * s, by - 12 * s, 130 * s, 26 * s))
        pygame.draw.ellipse(surface, COLOR_GOLD, (bx - 65 * s, by - 12 * s, 130 * s, 26 * s), 2)

        harm_x = bx + 16 * s
        harm_y = by - 36 * s
        harm_w = 46 * s
        harm_h = 30 * s
        pygame.draw.rect(surface, (60, 30, 20), (harm_x, harm_y, harm_w, harm_h))
        pygame.draw.rect(surface, (38, 18, 12), (harm_x + 2, harm_y + 2, harm_w - 4, harm_h - 4))

        bellows_pump = (math.sin(timing["bar_cycle"]) + 1.0) * 0.5
        bellows_x = harm_x - 12 * s - (bellows_pump * 8 * s)
        bellows_w = 12 * s + (bellows_pump * 8 * s)
        pygame.draw.polygon(surface, (45, 25, 18), [
            (harm_x, harm_y + 4), (bellows_x, harm_y + 7),
            (bellows_x, harm_y + harm_h - 7), (harm_x, harm_y + harm_h - 4),
        ])
        for fold in range(4):
            fx = bellows_x + fold * (bellows_w / 4.0)
            pygame.draw.line(surface, (200, 180, 140), (fx, harm_y + 7), (fx, harm_y + harm_h - 7), 1)

        pygame.draw.rect(surface, (230, 225, 215), (harm_x + 6 * s, harm_y + 4 * s, harm_w - 12 * s, 8 * s))
        for k in range(int(harm_x + 8 * s), int(harm_x + harm_w - 8 * s), 4):
            pygame.draw.line(surface, (20, 15, 15), (k, harm_y + 4 * s), (k, harm_y + 12 * s), 1)

        # Cross-legged lower body with volume
        pygame.draw.ellipse(surface, COLOR_DAURA_SURUWAL, (bx - 48 * s, by - 30 * s, 72 * s, 28 * s))
        pygame.draw.ellipse(surface, COLOR_SKIN_SHADOW, (bx - 20 * s, by - 18 * s, 18 * s, 10 * s))

        torso_sway = math.sin(timing["bar_cycle"] * 0.5) * (3.0 * s)
        head_sway = math.sin(timing["bar_cycle"] * 0.5 + 0.3) * (4.0 * s)

        pelvis = (bx + torso_sway, by - 26 * s)
        chest = (bx + torso_sway, by - 52 * s)
        neck = (bx + torso_sway * 0.8, by - 58 * s)
        draw_capsule(surface, pelvis, chest, 9 * s, COLOR_BLAZER_DARK)
        draw_capsule(surface, chest, neck, 6 * s, COLOR_BLAZER_DARK)

        pygame.draw.polygon(surface, (220, 215, 210), [
            (bx - 6 * s + torso_sway, by - 58 * s),
            (bx + 2 * s + torso_sway, by - 58 * s),
            (bx - 2 * s + torso_sway, by - 50 * s),
        ])

        shoulder_l = (bx - 14 * s + torso_sway, by - 54 * s)
        shoulder_r = (bx + 8 * s + torso_sway, by - 54 * s)

        bellows_hand = (bellows_x + 2, harm_y + harm_h * 0.5)
        elbow_l = solve_2bone_ik(shoulder_l, bellows_hand, 18 * s, 16 * s, bend_forward=False)
        draw_capsule(surface, shoulder_l, elbow_l, 3.5 * s, COLOR_BLAZER_DARK)
        draw_capsule(surface, elbow_l, bellows_hand, 2.8 * s, COLOR_SKIN)
        pygame.draw.circle(surface, COLOR_SKIN, (int(bellows_hand[0]), int(bellows_hand[1])), int(3.5 * s))

        key_tap = math.sin(timing["cycle"] * 2) * (2 * s)
        key_hand = (harm_x + 18 * s + key_tap, harm_y + 7 * s)
        elbow_r = solve_2bone_ik(shoulder_r, key_hand, 18 * s, 16 * s, bend_forward=True)
        draw_capsule(surface, shoulder_r, elbow_r, 3.5 * s, COLOR_BLAZER_DARK)
        draw_capsule(surface, elbow_r, key_hand, 2.8 * s, COLOR_SKIN)
        pygame.draw.circle(surface, COLOR_SKIN, (int(key_hand[0]), int(key_hand[1])), int(3 * s))

        head_x = int(bx - 3 * s + head_sway)
        head_y = int(by - 68 * s - beat_pulse * (3.0 * s))
        pygame.draw.ellipse(surface, COLOR_SKIN, (head_x - 8 * s, head_y - 9 * s, 16 * s, 18 * s))

        mouth_open = int(1.5 + beat_pulse * 4.0)
        pygame.draw.ellipse(surface, (70, 25, 30), (head_x + 1, head_y + int(2 * s), 4 * s, mouth_open * s))
        pygame.draw.arc(surface, (20, 15, 18), (head_x - 3 * s, head_y, 8 * s, 5 * s), 0, math.pi, 2)

        pygame.draw.rect(surface, (15, 12, 15), (head_x - 4 * s, head_y - int(3 * s), 4 * s, 3 * s), 1)
        pygame.draw.rect(surface, (15, 12, 15), (head_x + 1 * s, head_y - int(3 * s), 4 * s, 3 * s), 1)
        pygame.draw.line(surface, (15, 12, 15), (head_x, head_y - int(1.5 * s)), (head_x + 1 * s, head_y - int(1.5 * s)), 1)

        topi_poly = [
            (head_x - 7 * s, head_y - 4 * s), (head_x - 6 * s, head_y - 12 * s),
            (head_x + 2 * s, head_y - 15 * s), (head_x + 7 * s, head_y - 10 * s), (head_x + 6 * s, head_y - 4 * s),
        ]
        pygame.draw.polygon(surface, (55, 25, 30), topi_poly)
        pygame.draw.line(surface, COLOR_GOLD, (head_x - 3 * s, head_y - 8 * s), (head_x + 4 * s, head_y - 8 * s), 1)

        diyo_x = bx - 48 * s
        diyo_y = by - 6 * s
        pygame.draw.ellipse(surface, COLOR_GOLD, (diyo_x - 6, diyo_y - 3, 12, 6))
        flame_h = 5 + beat_pulse * 4
        pygame.draw.polygon(surface, (255, 220, 80), [
            (diyo_x, diyo_y - 5 - flame_h), (diyo_x - 3, diyo_y - 4), (diyo_x + 3, diyo_y - 4),
        ])


# ==============================================================================
# BEAT-SYNCED CHOREOGRAPHY POSES
# ==============================================================================
def choreography_pose(step_mode, timing, scale=1.0):
    """Return kinematic targets locked to 72 BPM beats."""
    bf = timing["beat_frac"]
    bc = timing["bar_cycle"]
    phrase = timing["phrase_frac"]
    flow = smoothstep(bf)  # ease within each beat for fluid motion

    if step_mode == 0:  # Maruni — cross-step on beats 1 & 3
        step_phase = math.sin(timing["cycle"] * 0.5)
        dip = abs(math.sin(timing["cycle"] * 0.5)) * 10 * scale
        sway = step_phase * 8 * scale
        step_w = lerp(18, 28, flow) * scale
        arm_speed = 1.0
    elif step_mode == 1:  # Charya dip on downbeats
        dip = (1.0 - math.cos(timing["cycle"])) * 0.5 * 20 * scale
        sway = math.sin(bc * 0.5) * 4 * scale
        step_w = 30 * scale
        arm_speed = 0.75
    elif step_mode == 2:  # Pirouette — half-bar rotation
        spin = math.sin(timing["cycle"] * 0.25)
        dip = abs(math.sin(timing["cycle"])) * 6 * scale
        sway = spin * 16 * scale
        step_w = 14 * scale
        arm_speed = 2.0
    else:  # Anjali & taali on every other beat
        dip = abs(math.sin(timing["cycle"])) * 9 * scale
        sway = math.sin(timing["cycle"] * 0.5) * 5 * scale
        step_w = 20 * scale
        arm_speed = 1.25

    return {
        "dip": dip, "sway": sway, "step_w": step_w,
        "arm_speed": arm_speed, "flow": flow, "phrase": phrase,
    }


# ==============================================================================
# MALE LEAD FOLK DANCER
# ==============================================================================
class MaleLeadDancer:
    def __init__(self):
        self.scale = 1.65
        self.thigh_len = 34 * self.scale
        self.shin_len = 32 * self.scale
        self.spine_len = 38 * self.scale
        self.arm_len = 22 * self.scale
        self.forearm_len = 20 * self.scale
        self.fire = RealisticPalmFire()

    def draw(self, surface, x, y, timing, step_mode=0):
        scale = self.scale
        pose = choreography_pose(step_mode, timing, scale)
        cycle = timing["cycle"]

        pelvis_x = x + pose["sway"]
        pelvis_y = y - (self.thigh_len + self.shin_len - 6 * scale) + pose["dip"]

        lean = math.sin(cycle * 0.5) * 0.08
        neck_x = pelvis_x + math.sin(lean) * self.spine_len * 0.15
        neck_y = pelvis_y - math.cos(lean) * self.spine_len
        chest_y = pelvis_y - self.spine_len * 0.55

        foot_a_x = x + math.sin(cycle * 0.5) * pose["step_w"]
        foot_a_y = y - max(0.0, -math.cos(cycle * 0.5)) * (12 * scale)
        foot_b_x = x - math.sin(cycle * 0.5) * pose["step_w"]
        foot_b_y = y - max(0.0, math.cos(cycle * 0.5)) * (12 * scale)

        hip_a = (pelvis_x - 5 * scale, pelvis_y)
        hip_b = (pelvis_x + 5 * scale, pelvis_y)
        knee_a = solve_2bone_ik(hip_a, (foot_a_x, foot_a_y), self.thigh_len, self.shin_len, bend_forward=True)
        knee_b = solve_2bone_ik(hip_b, (foot_b_x, foot_b_y), self.thigh_len, self.shin_len, bend_forward=True)

        draw_capsule(surface, hip_b, knee_b, 4 * scale, COLOR_DAURA_SURUWAL)
        draw_capsule(surface, knee_b, (foot_b_x, foot_b_y), 3 * scale, COLOR_DAURA_SURUWAL)
        draw_capsule(surface, hip_a, knee_a, 4.5 * scale, COLOR_DAURA_SURUWAL)
        draw_capsule(surface, knee_a, (foot_a_x, foot_a_y), 3.5 * scale, COLOR_DAURA_SURUWAL)
        pygame.draw.ellipse(surface, (35, 30, 38), (foot_a_x - 6 * scale, foot_a_y - 3 * scale, 12 * scale, 5 * scale))
        pygame.draw.ellipse(surface, (35, 30, 38), (foot_b_x - 6 * scale, foot_b_y - 3 * scale, 12 * scale, 5 * scale))

        draw_capsule(surface, (pelvis_x, pelvis_y), (pelvis_x, chest_y), 7 * scale, COLOR_DAURA_SURUWAL)
        draw_capsule(surface, (pelvis_x, chest_y), (neck_x, neck_y), 6 * scale, COLOR_DAURA_SURUWAL)
        pygame.draw.line(surface, (160, 35, 35), (pelvis_x - 9 * scale, pelvis_y - 2), (pelvis_x + 9 * scale, pelvis_y - 2), int(6 * scale))

        head_pos = (int(neck_x), int(neck_y - 10 * scale))
        pygame.draw.ellipse(surface, COLOR_SKIN, (head_pos[0] - 8 * scale, head_pos[1] - 9 * scale, 16 * scale, 18 * scale))
        topi_poly = [
            (head_pos[0] - 8 * scale, head_pos[1] - 2 * scale), (head_pos[0] - 6 * scale, head_pos[1] - 11 * scale),
            (head_pos[0] + 3 * scale, head_pos[1] - 15 * scale), (head_pos[0] + 9 * scale, head_pos[1] - 9 * scale),
            (head_pos[0] + 8 * scale, head_pos[1] - 2 * scale),
        ]
        pygame.draw.polygon(surface, (45, 22, 26), topi_poly)
        pygame.draw.line(surface, COLOR_GOLD, (head_pos[0] - 4 * scale, head_pos[1] - 8 * scale), (head_pos[0] + 5 * scale, head_pos[1] - 8 * scale), 1)

        shoulder = (neck_x, neck_y + 4 * scale)
        hand_l_angle = math.sin(cycle * pose["arm_speed"] + math.pi) * 0.65 + 0.75
        hand_l = (shoulder[0] - math.sin(hand_l_angle) * 30 * scale, shoulder[1] + math.cos(hand_l_angle) * 24 * scale)
        elbow_l = solve_2bone_ik(shoulder, hand_l, self.arm_len, self.forearm_len, bend_forward=False)
        draw_capsule(surface, shoulder, elbow_l, 3 * scale, COLOR_DAURA_SURUWAL)
        draw_capsule(surface, elbow_l, hand_l, 2.5 * scale, COLOR_SKIN)
        pygame.draw.arc(surface, COLOR_STEEL, (hand_l[0] - 8, hand_l[1] - 14, 20, 24), 0.2, math.pi * 0.85, 3)

        fire_hand_x = shoulder[0] + (20 * scale + math.sin(cycle * pose["arm_speed"] * 0.5) * 6.0)
        fire_hand_y = shoulder[1] - (16 * scale + math.cos(cycle * pose["arm_speed"] * 0.5) * 6.0)
        elbow_r = solve_2bone_ik(shoulder, (fire_hand_x, fire_hand_y), self.arm_len, self.forearm_len, bend_forward=True)
        draw_capsule(surface, shoulder, elbow_r, 3 * scale, COLOR_DAURA_SURUWAL)
        draw_capsule(surface, elbow_r, (fire_hand_x, fire_hand_y), 2.5 * scale, COLOR_SKIN)
        pygame.draw.circle(surface, COLOR_SKIN, (int(fire_hand_x), int(fire_hand_y)), int(4 * scale))

        self.fire.update_and_draw(surface, fire_hand_x, fire_hand_y - 2, intensity=0.85 + timing["beat_pulse"] * 0.3)


# ==============================================================================
# FEMALE FOLK DANCER
# ==============================================================================
class FemaleFolkDancer:
    def __init__(self, offset_phase=0.0):
        self.scale = 1.55
        self.thigh_len = 32 * self.scale
        self.shin_len = 30 * self.scale
        self.spine_len = 36 * self.scale
        self.arm_len = 20 * self.scale
        self.forearm_len = 19 * self.scale
        self.phase = offset_phase

    def draw(self, surface, x, y, timing, step_mode=0, look_right=True):
        scale = self.scale
        facing = 1.0 if look_right else -1.0
        t_timing = {
            **timing,
            "cycle": timing["cycle"] + self.phase,
            "bar_cycle": timing["bar_cycle"] + self.phase * 0.5,
            "beat_index": timing["beat_index"] + self.phase / (math.pi * 2),
        }
        pose = choreography_pose(step_mode, t_timing, scale)
        cycle = t_timing["cycle"]

        pelvis_x = x + pose["sway"]
        pelvis_y = y - (self.thigh_len + self.shin_len - 6 * scale) + pose["dip"]
        torso_roll = math.sin(cycle * 0.5) * 0.12
        neck_x = pelvis_x + math.sin(torso_roll) * self.spine_len * 0.12
        neck_y = pelvis_y - math.cos(torso_roll) * self.spine_len
        chest_y = pelvis_y - self.spine_len * 0.5

        foot_a_x = x + math.sin(cycle * 0.5) * pose["step_w"] * facing
        foot_a_y = y - max(0.0, -math.cos(cycle * 0.5)) * (10 * scale)
        foot_b_x = x - math.sin(cycle * 0.5) * pose["step_w"] * facing
        foot_b_y = y - max(0.0, math.cos(cycle * 0.5)) * (10 * scale)

        hip_l = (pelvis_x - 4 * scale, pelvis_y)
        hip_r = (pelvis_x + 4 * scale, pelvis_y)
        knee_l = solve_2bone_ik(hip_l, (foot_a_x, foot_a_y), self.thigh_len, self.shin_len, bend_forward=True)
        knee_r = solve_2bone_ik(hip_r, (foot_b_x, foot_b_y), self.thigh_len, self.shin_len, bend_forward=True)

        patasi_poly = [
            (pelvis_x - 14 * scale, pelvis_y), (pelvis_x + 14 * scale, pelvis_y),
            (foot_b_x + 18 * scale * facing, y), (foot_a_x - 12 * scale * facing, y),
        ]
        pygame.draw.polygon(surface, COLOR_HAKU_PATASI_BLACK, patasi_poly)
        pygame.draw.line(surface, COLOR_HAKU_PATASI_RED, (foot_a_x - 12 * scale * facing, y - 4), (foot_b_x + 18 * scale * facing, y - 4), int(5 * scale))

        draw_capsule(surface, hip_l, knee_l, 3.5 * scale, COLOR_HAKU_PATASI_BLACK)
        draw_capsule(surface, knee_l, (foot_a_x, foot_a_y), 2.8 * scale, COLOR_HAKU_PATASI_BLACK)
        draw_capsule(surface, hip_r, knee_r, 3.5 * scale, COLOR_HAKU_PATASI_BLACK)
        draw_capsule(surface, knee_r, (foot_b_x, foot_b_y), 2.8 * scale, COLOR_HAKU_PATASI_BLACK)

        pygame.draw.line(surface, COLOR_PATUKA_YELLOW, (pelvis_x - 12 * scale, pelvis_y - 2), (pelvis_x + 12 * scale, pelvis_y - 2), int(7 * scale))
        draw_capsule(surface, (pelvis_x, pelvis_y), (pelvis_x, chest_y), 6.5 * scale, COLOR_CHOLO_CRIMSON)
        draw_capsule(surface, (pelvis_x, chest_y), (neck_x, neck_y), 5.5 * scale, COLOR_CHOLO_CRIMSON)

        head_pos = (int(neck_x), int(neck_y - 10 * scale))
        pygame.draw.ellipse(surface, COLOR_SKIN, (head_pos[0] - 7 * scale, head_pos[1] - 8 * scale, 14 * scale, 16 * scale))
        pygame.draw.circle(surface, (15, 12, 18), (head_pos[0] - int(6 * scale * facing), head_pos[1] - 2), int(5 * scale))
        pygame.draw.circle(surface, COLOR_MARIGOLD_ORANGE, (head_pos[0] - int(7 * scale * facing), head_pos[1] - 6), int(3.5 * scale))
        pygame.draw.line(surface, COLOR_GOLD, (head_pos[0] - 5, head_pos[1] - 6), (head_pos[0] + 5, head_pos[1] - 6), 2)

        shoulder = (neck_x, neck_y + 4 * scale)
        if step_mode == 3:
            clap = math.sin(cycle * 2) * 4 * scale
            hand1 = (neck_x + (8 * scale + clap) * facing, neck_y + 10 * scale)
            hand2 = (neck_x - (2 * scale - clap) * facing, neck_y + 10 * scale)
        else:
            arm1_ang = math.sin(cycle * pose["arm_speed"]) * 0.8 - 0.55
            hand1 = (shoulder[0] + math.cos(arm1_ang) * 34 * scale * facing, shoulder[1] + math.sin(arm1_ang) * 26 * scale - 12 * scale)
            arm2_ang = math.cos(cycle * pose["arm_speed"]) * 0.65 + 0.75
            hand2 = (shoulder[0] - math.cos(arm2_ang) * 28 * scale * facing, shoulder[1] + math.sin(arm2_ang) * 22 * scale)

        elbow1 = solve_2bone_ik(shoulder, hand1, self.arm_len, self.forearm_len, bend_forward=True)
        elbow2 = solve_2bone_ik(shoulder, hand2, self.arm_len, self.forearm_len, bend_forward=False)
        draw_capsule(surface, shoulder, elbow1, 2.8 * scale, COLOR_CHOLO_CRIMSON)
        draw_capsule(surface, elbow1, hand1, 2.2 * scale, COLOR_SKIN)
        pygame.draw.circle(surface, COLOR_GOLD, (int(hand1[0]), int(hand1[1])), int(3 * scale))
        draw_capsule(surface, shoulder, elbow2, 2.8 * scale, COLOR_CHOLO_CRIMSON)
        draw_capsule(surface, elbow2, hand2, 2.2 * scale, COLOR_SKIN)
        pygame.draw.circle(surface, COLOR_GOLD, (int(hand2[0]), int(hand2[1])), int(3 * scale))


# ==============================================================================
# MAIN DANCE ENGINE
# ==============================================================================
def render_frame(current_sec, narayan_gopal, male_lead, female_dancers):
    timing = beat_clock(current_sec)
    current_step_mode = int((timing["bar_index"] // 2) % 4)
    step_title, step_desc = DANCE_ROUTINES[current_step_mode]

    frame = pygame.Surface((WIDTH, HEIGHT))
    ground_y = HEIGHT - 80

    draw_himalayan_backdrop(frame, current_sec, timing["beat_pulse"])
    draw_nyatapola(frame, int(WIDTH * 0.38), ground_y + 10, scale=0.95, tiers=5)
    draw_nyatapola(frame, int(WIDTH * 0.82), ground_y + 10, scale=0.72, tiers=4)
    draw_marigold_garland(frame, (WIDTH * 0.26, ground_y - 120), (WIDTH * 0.52, ground_y - 120))
    draw_marigold_garland(frame, (WIDTH * 0.72, ground_y - 110), (WIDTH * 0.94, ground_y - 110))
    draw_cobblestones(frame, ground_y)

    narayan_gopal.draw(frame, timing)

    # Lead drifts gently on bar boundaries (2 bars = ~6.67s)
    lead_x = WIDTH * 0.58 + math.sin(timing["bar_cycle"] * 0.25) * 28
    male_lead.draw(frame, lead_x, ground_y, timing, step_mode=current_step_mode)

    dancer_x_bases = [WIDTH * 0.38, WIDTH * 0.76, WIDTH * 0.90]
    for i, dancer in enumerate(female_dancers):
        dx = dancer_x_bases[i] + math.sin(timing["cycle"] + dancer.phase) * 14
        dancer.draw(frame, dx, ground_y, timing, step_mode=current_step_mode, look_right=(dx < lead_x))

    return frame, timing, current_step_mode, step_title, step_desc


def main():
    args = parse_args()
    export_mode = args.export

    if export_mode and args.no_preview:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    caption = "Seek & Destroy - Narayan Gopal (Exporting…)" if export_mode else "Seek & Destroy - Narayan Gopal 72 BPM Musical Dance Ensemble"
    pygame.display.set_caption(caption)
    clock = pygame.time.Clock()

    audio_path = resolve_audio_path()
    has_audio = False
    if not export_mode and audio_path:
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
            has_audio = True
        except Exception:
            pass

    recorder = None
    if export_mode:
        random.seed(42)
        recorder = FfmpegRecorder(args.output, audio_path=audio_path)
        total_frames = int(SONG_DURATION_SEC * FPS)
        print(f"Exporting {total_frames} frames ({SONG_DURATION_SEC:.0f}s @ {FPS}fps) → {args.output}")
        if audio_path:
            print(f"Muxing audio from {audio_path.name}")

    narayan_gopal = NarayanGopalPerformer(base_x=135, base_y=HEIGHT - 75)
    male_lead = MaleLeadDancer()
    female_dancers = [
        FemaleFolkDancer(offset_phase=0.0),
        FemaleFolkDancer(offset_phase=math.pi * 0.5),
        FemaleFolkDancer(offset_phase=math.pi),
    ]

    start_ticks = pygame.time.get_ticks()
    time_offset = 0.0
    frame_index = 0
    total_frames = int(SONG_DURATION_SEC * FPS)
    running = True

    while running:
        if export_mode:
            if frame_index >= total_frames:
                break
            current_sec = frame_index / FPS
        else:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RIGHT:
                        time_offset += 10.0
                    elif event.key == pygame.K_LEFT:
                        time_offset = max(0.0, time_offset - 10.0)

            raw_sec = (pygame.mixer.music.get_pos() / 1000.0) if has_audio else ((pygame.time.get_ticks() - start_ticks) / 1000.0)
            current_sec = min(SONG_DURATION_SEC, raw_sec + time_offset)

        frame, timing, current_step_mode, step_title, step_desc = render_frame(
            current_sec, narayan_gopal, male_lead, female_dancers,
        )

        screen.fill(COLOR_BLACK)
        screen.blit(frame, (0, 0))

        bar_h = 44
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, WIDTH, bar_h))
        pygame.draw.rect(screen, (0, 0, 0), (0, HEIGHT - bar_h, WIDTH, bar_h))

        show_hud = (not export_mode) or args.hud
        if show_hud:
            mins = int(current_sec // 60)
            secs = int(current_sec % 60)
            font = pygame.font.SysFont("georgia", 13, bold=True)
            hud_text = font.render(
                f"[{mins:02d}:{secs:02d} / 05:13 | 72 BPM] NARAYAN GOPAL & NEWARI FOLK ENSEMBLE",
                True, (225, 200, 165),
            )
            screen.blit(hud_text, (24, 13))
            desc_font = pygame.font.SysFont("georgia", 12, italic=True)
            routine_text = desc_font.render(f"CHOREOGRAPHY: {step_title} — {step_desc}", True, (190, 170, 145))
            screen.blit(routine_text, (24, HEIGHT - 28))

        if export_mode:
            recorder.write_frame(screen)
            frame_index += 1
            if not args.no_preview:
                pygame.display.flip()
            if frame_index % (FPS * 5) == 0 or frame_index == total_frames:
                pct = 100.0 * frame_index / total_frames
                print(f"  {frame_index}/{total_frames} frames ({pct:.0f}%)")
        else:
            pygame.display.flip()
            clock.tick(FPS)

    if recorder:
        out = recorder.close()
        print(f"Done → {out}")

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
