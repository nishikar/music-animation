#!/usr/bin/env python3
"""
Free as a Bird — Van Gogh style (pycairo + pygame).

Same timed flight narrative as free_as_a_bird.py, but scenery is painted with
Post-Impressionist techniques inspired by research on generative Van Gogh /

Impressionist rendering:

  • Hertzmann-style layered curved brush strokes (SIGGRAPH painterly rendering)
  • Perlin / value-noise flow fields directing stroke orientation
  • Curl-like swirling fields for Starry Night skies (tangential vortices + noise)
  • Color jitter, round line caps, and overlapping translucent strokes for impasto

References (techniques adapted, not copied):
  - Aaron Hertzmann, "Painterly Rendering with Curved Brush Strokes of Multiple Sizes"
  - Matt DesLauriers / generative impressionism (noise flow-field particles)
  - Curl-noise / Starry Night flow-field generative art
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cairo
import pygame

# ==============================================================================
# CONFIGURATION
# ==============================================================================
WIDTH, HEIGHT = 1080, 720
FPS = 60
SONG_DURATION = 180.0
CROSSFADE = 0.85

SCRIPT_DIR = Path(__file__).resolve().parent
AUDIO_PATH = SCRIPT_DIR / "free_as_a_bird.mp3"
DEFAULT_EXPORT_PATH = SCRIPT_DIR / "free_as_a_bird_vg.mp4"

Color = Tuple[float, float, float]
ColorA = Tuple[float, float, float, float]

# Van Gogh–inspired pigment set (normalized RGB)
ULTRA = (0.10, 0.18, 0.55)
COBALT = (0.18, 0.35, 0.72)
NIGHT = (0.05, 0.08, 0.22)
YELLOW = (0.96, 0.82, 0.18)
CHROME = (0.98, 0.72, 0.08)
OCHRE = (0.78, 0.55, 0.18)
SIENNA = (0.62, 0.28, 0.12)
VIRIDIAN = (0.12, 0.42, 0.28)
OLIVE = (0.28, 0.38, 0.14)
CYPRESS = (0.08, 0.18, 0.12)
CREAM = (0.95, 0.90, 0.70)
VERMILION = (0.85, 0.22, 0.12)
VIOLET = (0.35, 0.18, 0.48)
WHITE = (0.96, 0.95, 0.88)
TURQ = (0.25, 0.55, 0.58)
FOAM = (0.90, 0.93, 0.95)


SCENES = [
    (0.0, 10.0, "predawn_roost", "rest", "VG Intro I · Starry Roost"),
    (10.0, 18.0, "dawn_awakening", "wake", "VG Intro II · Amber Dawn"),
    (18.0, 24.5, "vertical_liftoff", "liftoff", "VG Intro III · Liftoff Swirl"),
    (24.5, 31.5, "emerald_canopy", "cruise", "VG Verse 1A · Olive Canopy"),
    (31.5, 38.5, "alpine_ridge", "climb", "VG Verse 1B · Cypress Ridges"),
    (38.5, 46.0, "valley_clearing", "glide", "VG Verse 1C · Wheat Valley"),
    (46.0, 53.0, "coastal_cliffs", "swoop", "VG Verse 2A · Cliff Descent"),
    (53.0, 60.0, "marine_shore", "bank_glide", "VG Verse 2B · Shore Strokes"),
    (60.0, 67.5, "open_ocean", "skim", "VG Verse 2C · Swirling Sea"),
    (67.5, 77.0, "desert_dunes", "turbulence", "VG Bridge 1A · Ochre Dunes"),
    (77.0, 83.0, "salt_flats", "fast_low", "VG Bridge 1B · Bleached Flats"),
    (83.0, 90.0, "desert_canyon", "weave", "VG Bridge 1C · Sienna Canyon"),
    (90.0, 96.5, "dust_storm", "struggle", "VG Bridge 1D · Dust Vortex"),
    (96.5, 104.0, "storm_breach", "burst_climb", "VG Bridge 1E · Storm Breach"),
    (104.0, 113.5, "sea_swells", "long_glide", "VG Bridge 1F · Violet Swells"),
    (113.5, 120.0, "tidal_mirror", "mirror", "VG Verse 3A · Mirror Night"),
    (120.0, 127.0, "deep_swells", "diagonal", "VG Verse 3B · Indigo Sweep"),
    (127.0, 135.5, "sunset_islands", "slow_cruise", "VG Verse 3C · Crimson Coast"),
    (135.5, 148.0, "mandala_sky", "loop", "VG Instrumental · Solar Mandala"),
    (148.0, 157.0, "twilight_alps", "horizon", "VG Reprise 1A · Violet Alps"),
    (157.0, 163.0, "sunset_clouds", "cloud_cut", "VG Reprise 1B · Cloud Impasto"),
    (163.0, 170.0, "sanctuary", "duo", "VG Reprise 1C · Twin Flight"),
    (170.0, 175.0, "twilight_forest", "duo_descend", "VG Outro A · Cypress Grove"),
    (175.0, 180.0, "roost_return", "land", "VG Outro B · Starry Tree"),
]


# ==============================================================================
# MATH
# ==============================================================================
def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * clamp(t)


def lerp_color(c1: Color, c2: Color, t: float) -> Color:
    t = clamp(t)
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = clamp((x - edge0) / (edge1 - edge0 + 1e-9))
    return t * t * (3.0 - 2.0 * t)


def hash01(i: int) -> float:
    x = math.sin(i * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


def noise1(x: float) -> float:
    i = math.floor(x)
    f = x - i
    u = f * f * (3.0 - 2.0 * f)
    return lerp(hash01(int(i) & 0x7FFFFFFF), hash01((int(i) + 1) & 0x7FFFFFFF), u)


def noise2(x: float, y: float) -> float:
    """Value noise — harmonic enough for Van Gogh flow fields."""
    return noise1(x + y * 57.0) * 0.5 + noise1(x * 1.7 + y * 1.3 + 19.0) * 0.5


def fbm2(x: float, y: float, octaves: int = 4) -> float:
    amp, freq, total, norm = 0.5, 1.0, 0.0, 0.0
    for _ in range(octaves):
        total += amp * noise2(x * freq, y * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.05
    return total / max(norm, 1e-9)


def jitter_color(c: Color, amount: float, seed: int) -> Color:
    return (
        clamp(c[0] + (hash01(seed) - 0.5) * amount),
        clamp(c[1] + (hash01(seed + 17) - 0.5) * amount),
        clamp(c[2] + (hash01(seed + 31) - 0.5) * amount),
    )


def pick_palette(colors: Sequence[Color], seed: int) -> Color:
    return colors[int(hash01(seed) * len(colors)) % len(colors)]


# ==============================================================================
# FFMPEG / CLI
# ==============================================================================
class FfmpegRecorder:
    def __init__(self, output_path: Path, fps=FPS, width=WIDTH, height=HEIGHT, audio_path=None):
        self.output_path = Path(output_path)
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
            cmd.extend(["-t", str(SONG_DURATION)])
        cmd.append(str(self.output_path))
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )

    def write_frame(self, surface: pygame.Surface) -> None:
        if self._proc is None or self._proc.stdin is None:
            return
        self._proc.stdin.write(pygame.image.tostring(surface, "RGB"))
        self.frames_written += 1

    def close(self) -> Path:
        if self._proc is None:
            return self.output_path
        if self._proc.stdin:
            self._proc.stdin.close()
        stderr = self._proc.stderr.read().decode("utf-8", errors="replace") if self._proc.stderr else ""
        rc = self._proc.wait()
        self._proc = None
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed (exit {rc}):\n{stderr[-2000:]}")
        return self.output_path


def parse_args():
    p = argparse.ArgumentParser(description="Free as a Bird — Van Gogh style animation")
    p.add_argument("--export", "-e", action="store_true")
    p.add_argument("--output", "-o", type=Path, default=DEFAULT_EXPORT_PATH)
    p.add_argument("--no-preview", action="store_true")
    p.add_argument("--hud", action="store_true")
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--duration", type=float, default=None)
    return p.parse_args()


# ==============================================================================
# CAIRO CANVAS
# ==============================================================================
class CairoCanvas:
    def __init__(self, w: int = WIDTH, h: int = HEIGHT):
        self.w, self.h = w, h
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        self.ctx = cairo.Context(self.surface)

    def clear(self) -> None:
        self.ctx.set_operator(cairo.OPERATOR_CLEAR)
        self.ctx.paint()
        self.ctx.set_operator(cairo.OPERATOR_OVER)

    def to_pygame(self) -> pygame.Surface:
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


# ==============================================================================
# VAN GOGH BRUSH ENGINE
# ==============================================================================
class VanGoghBrush:
    """
    Procedural impasto painter.

    Flow field: angle = 2π * fbm(x,y,t)  (DesLauriers / generative impressionism)
    Curl swirl: tangential angle around vortex centers (Starry Night)
    Strokes: short curved segments, LINE_CAP_ROUND, color jitter (Hertzmann-like)
    """

    def __init__(self):
        self._stroke_cache_seed = 0

    def underpaint(self, ctx: cairo.Context, top: Color, bot: Color, mid: Optional[Color] = None) -> None:
        g = cairo.LinearGradient(0, 0, 0, HEIGHT)
        g.add_color_stop_rgb(0.0, *top)
        if mid:
            g.add_color_stop_rgb(0.5, *mid)
        g.add_color_stop_rgb(1.0, *bot)
        ctx.set_source(g)
        ctx.paint()

    def flow_angle(self, x: float, y: float, t: float, scale: float = 0.007) -> float:
        n = fbm2(x * scale + t * 0.08, y * scale * 0.9 - t * 0.05)
        return n * math.pi * 2.0

    def swirl_angle(self, x: float, y: float, cx: float, cy: float, t: float,
                    strength: float = 1.0) -> float:
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy) + 1e-3
        tangential = math.atan2(dy, dx) + math.pi * 0.5
        noise = self.flow_angle(x, y, t, 0.01) * 0.35
        falloff = strength * math.exp(-r / 220.0)
        base = self.flow_angle(x, y, t, 0.006)
        return lerp(base, tangential + noise, clamp(falloff))

    def stroke_curve(self, ctx: cairo.Context, x: float, y: float, angle: float,
                     length: float, width: float, color: Color, alpha: float = 0.85) -> None:
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(width)
        ctx.set_source_rgba(color[0], color[1], color[2], alpha)
        # Fast bent segment: two straight legs (cheaper than cubic, still organic)
        mid = length * 0.55
        nx, ny = -math.sin(angle) * length * 0.12, math.cos(angle) * length * 0.12
        x1 = x + math.cos(angle) * mid + nx
        y1 = y + math.sin(angle) * mid + ny
        x2 = x + math.cos(angle) * length
        y2 = y + math.sin(angle) * length
        ctx.move_to(x, y)
        ctx.line_to(x1, y1)
        ctx.line_to(x2, y2)
        ctx.stroke()

    def paint_flow_field(
        self,
        ctx: cairo.Context,
        t: float,
        y0: float,
        y1: float,
        palette: Sequence[Color],
        spacing: float = 18.0,
        length: float = 22.0,
        width: float = 5.5,
        alpha: float = 0.72,
        scale: float = 0.007,
        vortices: Optional[Sequence[Tuple[float, float, float]]] = None,
        x0: float = 0.0,
        x1: float = float(WIDTH),
        jitter: float = 0.12,
        phase: float = 0.0,
    ) -> None:
        """Fill a band with directed impasto strokes (flow-field / curl guided)."""
        vortices = vortices or ()
        n_pal = len(palette)
        rows = max(1, int((y1 - y0) / spacing) + 1)
        cols = max(1, int((x1 - x0) / spacing) + 1)
        # batch by approximating: one path-less stroke loop
        for j in range(rows):
            ox = 0.5 * spacing if (j & 1) else 0.0
            base_y = y0 + j * spacing
            for i in range(cols):
                seed = i * 131 + j * 97 + int(y0 * 0.1)
                x = x0 + i * spacing + ox + (hash01(seed) - 0.5) * spacing * 0.3
                y = base_y + (hash01(seed + 1) - 0.5) * spacing * 0.3
                if x < x0 - 8 or x > x1 + 8 or y < y0 - 8 or y > y1 + 8:
                    continue

                # cheaper 1-octave flow + optional swirl blend
                n = noise2(x * scale + t * 0.08, y * scale * 0.9)
                ang = n * math.pi * 2.0
                if vortices:
                    for cx, cy, s in vortices:
                        dx, dy = x - cx, y - cy
                        r = math.hypot(dx, dy) + 1e-3
                        fall = s * math.exp(-r / 220.0)
                        if fall > 0.05:
                            tang = math.atan2(dy, dx) + math.pi * 0.5
                            ang = lerp(ang, tang, clamp(fall))

                col = palette[int(hash01(seed + 2) * n_pal) % n_pal]
                if jitter > 0:
                    col = jitter_color(col, jitter, seed)
                ln = length * (0.75 + 0.5 * hash01(seed + 3))
                wd = width * (0.8 + 0.4 * hash01(seed + 9))
                a = alpha * (0.7 + 0.3 * hash01(seed + 21))
                self.stroke_curve(ctx, x, y, ang, ln, wd, col, a)

    def paint_stars(self, ctx: cairo.Context, t: float, count: int = 28) -> None:
        for i in range(count):
            sx = hash01(200 + i * 3) * WIDTH
            sy = hash01(201 + i * 3) * HEIGHT * 0.55
            pulse = 0.75 + 0.25 * math.sin(t * 2.2 + i)
            r = 4 + hash01(i + 9) * 10
            # glowing yellow orbs like Starry Night
            for k, (mul, a) in enumerate([(2.8, 0.12), (1.7, 0.28), (1.0, 0.9)]):
                col = YELLOW if i % 3 else CHROME
                ctx.set_source_rgba(col[0], col[1], col[2], a * pulse)
                ctx.arc(sx, sy, r * mul * pulse, 0, 2 * math.pi)
                ctx.fill()
            # radial dash strokes around star
            for k in range(8):
                ang = k * (math.pi / 4) + t * 0.15 + i
                ctx.set_line_cap(cairo.LINE_CAP_ROUND)
                ctx.set_line_width(2.2)
                ctx.set_source_rgba(YELLOW[0], YELLOW[1], YELLOW[2], 0.35 * pulse)
                ctx.move_to(sx + math.cos(ang) * r * 0.8, sy + math.sin(ang) * r * 0.8)
                ctx.line_to(sx + math.cos(ang) * r * 2.2, sy + math.sin(ang) * r * 2.2)
                ctx.stroke()

    def paint_moon(self, ctx: cairo.Context, x: float, y: float, r: float, t: float) -> None:
        for mul, a in [(2.6, 0.15), (1.7, 0.3), (1.0, 1.0)]:
            ctx.set_source_rgba(CREAM[0], CREAM[1], 0.55 if mul > 1 else CREAM[2], a)
            if mul == 1.0:
                ctx.set_source_rgb(*YELLOW)
            ctx.arc(x, y, r * mul, 0, 2 * math.pi)
            ctx.fill()
        # crescent hint / crater strokes
        self.paint_flow_field(
            ctx, t, y - r, y + r,
            [YELLOW, CHROME, CREAM, OCHRE],
            spacing=7, length=10, width=3.5, alpha=0.55,
            x0=x - r, x1=x + r, vortices=[(x, y, 1.2)], jitter=0.08,
        )

    def paint_cypress(self, ctx: cairo.Context, x: float, base_y: float, h: float,
                      t: float, sway: float = 0.0) -> None:
        """Flame-like cypress silhouette filled with vertical swirling strokes."""
        wind = sway * math.sin(t * 0.7 + x * 0.01)
        top_x = x + wind * 18
        # dark under shape
        ctx.set_source_rgb(*CYPRESS)
        ctx.move_to(x - 18, base_y)
        ctx.curve_to(x - 28, base_y - h * 0.35, top_x - 16, base_y - h * 0.75, top_x, base_y - h)
        ctx.curve_to(top_x + 14, base_y - h * 0.7, x + 26, base_y - h * 0.3, x + 16, base_y)
        ctx.close_path()
        ctx.fill()
        # vertical flame strokes
        palette = [CYPRESS, OLIVE, VIRIDIAN, (0.05, 0.12, 0.08), (0.15, 0.28, 0.12)]
        for i in range(18):
            px = x + (hash01(i + int(x)) - 0.5) * 30
            py = base_y - hash01(i + 4) * h * 0.95
            ang = -math.pi / 2 + wind * 0.2 + (hash01(i + 8) - 0.5) * 0.5
            col = jitter_color(pick_palette(palette, i), 0.08, i)
            self.stroke_curve(ctx, px, py, ang, 16 + hash01(i) * 18, 4.5, col, 0.8)

    def paint_tree_of_life(self, ctx: cairo.Context, cx: float, base_y: float,
                           scale: float, t: float) -> None:
        trunk = (0.25, 0.14, 0.08)
        ctx.set_source_rgb(*trunk)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(16 * scale)
        ctx.move_to(cx, base_y)
        ctx.curve_to(cx - 6 * scale, base_y - 90 * scale,
                     cx + 10 * scale, base_y - 170 * scale,
                     cx, base_y - 230 * scale)
        ctx.stroke()
        # branch strokes
        palette = [OLIVE, VIRIDIAN, CYPRESS, (0.2, 0.35, 0.12), (0.35, 0.4, 0.1)]
        for i in range(24):
            ang0 = -math.pi / 2 + (hash01(i) - 0.5) * 1.8
            bx = cx + math.cos(ang0) * 20 * scale
            by = base_y - (80 + hash01(i + 2) * 150) * scale
            ang = ang0 + 0.3 * math.sin(t + i)
            col = jitter_color(pick_palette(palette, i), 0.1, i)
            self.stroke_curve(ctx, bx, by, ang, 25 * scale + 10, 4 * scale, col, 0.85)
        # canopy dash clusters
        self.paint_flow_field(
            ctx, t, base_y - 280 * scale, base_y - 80 * scale,
            palette, spacing=16, length=16, width=5, alpha=0.7,
            x0=cx - 140 * scale, x1=cx + 140 * scale,
            vortices=[(cx, base_y - 200 * scale, 0.7)], jitter=0.1,
        )

    def paint_hills(self, ctx: cairo.Context, t: float, base_y: float,
                    palette: Sequence[Color], amp: float = 60) -> None:
        # silhouette underpaint
        ctx.set_source_rgb(*palette[0])
        ctx.move_to(-20, HEIGHT)
        ctx.line_to(-20, base_y)
        for i in range(30):
            x = i * (WIDTH + 40) / 28 - 20
            y = base_y - amp * fbm2(x * 0.004 + t * 0.02, i * 0.1)
            ctx.line_to(x, y)
        ctx.line_to(WIDTH + 20, HEIGHT)
        ctx.close_path()
        ctx.fill()
        self.paint_flow_field(
            ctx, t, base_y - amp - 20, HEIGHT,
            palette, spacing=16, length=20, width=6, alpha=0.75,
            scale=0.009, jitter=0.14,
        )

    def paint_ocean(self, ctx: cairo.Context, t: float, y0: float,
                    palette: Sequence[Color], foam: Sequence[Color] = (FOAM, CREAM, WHITE)) -> None:
        ctx.set_source_rgb(*palette[0])
        ctx.rectangle(0, y0, WIDTH, HEIGHT - y0)
        ctx.fill()
        # horizontal wave-following strokes
        self.paint_flow_field(
            ctx, t, y0, HEIGHT, palette,
            spacing=16, length=28, width=6.5, alpha=0.7,
            scale=0.004, jitter=0.1, phase=t * 8,
        )
        # foam crest dashes
        for i in range(28):
            x = (hash01(i * 3) * WIDTH + t * 30) % WIDTH
            y = y0 + 20 + hash01(i + 5) * (HEIGHT - y0 - 40)
            ang = 0.15 * math.sin(x * 0.02 + t * 2) + self.flow_angle(x, y, t, 0.02) * 0.2
            col = jitter_color(pick_palette(foam, i), 0.05, i)
            self.stroke_curve(ctx, x, y, ang, 18, 3.5, col, 0.55)

    def paint_wheat(self, ctx: cairo.Context, t: float, y0: float) -> None:
        palette = [OCHRE, CHROME, YELLOW, (0.7, 0.5, 0.15), (0.85, 0.65, 0.2)]
        ctx.set_source_rgb(*OCHRE)
        ctx.rectangle(0, y0, WIDTH, HEIGHT - y0)
        ctx.fill()
        self.paint_flow_field(
            ctx, t, y0, HEIGHT, palette,
            spacing=15, length=26, width=5, alpha=0.8,
            scale=0.01, jitter=0.12, phase=t * 5,
        )

    def paint_dunes(self, ctx: cairo.Context, t: float) -> None:
        for i, (y0, pal) in enumerate([
            (HEIGHT * 0.42, [SIENNA, OCHRE, (0.7, 0.35, 0.15)]),
            (HEIGHT * 0.58, [OCHRE, CHROME, (0.85, 0.5, 0.2)]),
            (HEIGHT * 0.72, [YELLOW, OCHRE, CREAM]),
        ]):
            ctx.set_source_rgb(*pal[0])
            ctx.move_to(0, HEIGHT)
            ctx.line_to(0, y0)
            for k in range(24):
                x = k * WIDTH / 22
                y = y0 - 50 * fbm2(x * 0.003 + i, t * 0.05) - 20 * math.sin(x * 0.01 + i)
                ctx.line_to(x, y)
            ctx.line_to(WIDTH, HEIGHT)
            ctx.close_path()
            ctx.fill()
            self.paint_flow_field(
                ctx, t, y0 - 40, HEIGHT, pal,
                spacing=16, length=24, width=6, alpha=0.7,
                scale=0.006, jitter=0.1,
            )

    def paint_canyon(self, ctx: cairo.Context, t: float) -> None:
        # sky already painted; walls with vertical strokes
        left_pal = [SIENNA, VERMILION, (0.5, 0.2, 0.1), OCHRE]
        right_pal = [SIENNA, (0.4, 0.15, 0.08), (0.55, 0.25, 0.12)]
        ctx.set_source_rgb(*SIENNA)
        ctx.move_to(0, 0)
        ctx.line_to(0, HEIGHT)
        for i in range(14):
            y = i * HEIGHT / 12
            ctx.line_to(90 + 40 * math.sin(i * 0.8 + t * 0.2), y)
        ctx.close_path()
        ctx.fill()
        ctx.move_to(WIDTH, 0)
        ctx.line_to(WIDTH, HEIGHT)
        for i in range(14):
            y = i * HEIGHT / 12
            ctx.line_to(WIDTH - 100 - 35 * math.sin(i * 1.1 - t * 0.2), y)
        ctx.close_path()
        ctx.fill()
        self.paint_flow_field(
            ctx, t, 0, HEIGHT, left_pal,
            spacing=16, length=22, width=6, alpha=0.75,
            x0=0, x1=160, scale=0.012, jitter=0.12,
        )
        self.paint_flow_field(
            ctx, t, 0, HEIGHT, right_pal,
            spacing=16, length=22, width=6, alpha=0.75,
            x0=WIDTH - 180, x1=WIDTH, scale=0.012, jitter=0.12,
        )
        # floor
        self.paint_flow_field(
            ctx, t, HEIGHT * 0.75, HEIGHT,
            [OCHRE, SIENNA, (0.45, 0.28, 0.14)],
            spacing=18, length=20, width=5, alpha=0.7,
        )

    def paint_mandala(self, ctx: cairo.Context, cx: float, cy: float, t: float) -> None:
        pulse = 0.92 + 0.08 * math.sin(t * 2.0)
        for ring in range(5):
            r = (50 + ring * 32) * pulse
            ctx.set_source_rgba(YELLOW[0], YELLOW[1], YELLOW[2], 0.1)
            ctx.arc(cx, cy, r, 0, 2 * math.pi)
            ctx.set_line_width(8)
            ctx.stroke()
        # petal strokes radiating
        for i in range(36):
            ang = i * (math.pi * 2 / 36) + t * 0.2
            for layer in range(3):
                rr = (40 + layer * 35) * pulse
                x = cx + math.cos(ang) * rr * 0.4
                y = cy + math.sin(ang) * rr * 0.4
                col = pick_palette([YELLOW, CHROME, OCHRE, VERMILION, CREAM], i + layer * 10)
                self.stroke_curve(ctx, x, y, ang, 30 - layer * 6, 7 - layer, col, 0.55)
        ctx.set_source_rgb(*YELLOW)
        ctx.arc(cx, cy, 22 * pulse, 0, 2 * math.pi)
        ctx.fill()


# ==============================================================================
# BIRD RIG (stylized with thick outline / pigment fill)
# ==============================================================================
class BirdRig:
    def __init__(self, scale: float = 1.2, fill: Color = (0.08, 0.1, 0.22),
                 outline: Color = (0.02, 0.03, 0.08)):
        self.scale = scale
        self.fill = fill
        self.outline = outline
        self.wing_phase = 0.0
        self.bank = 0.0
        self.pitch = 0.0
        self.spread = 0.35
        self.breath = 0.0
        self.x = WIDTH * 0.5
        self.y = HEIGHT * 0.35
        self.facing = 1.0

    def update(self, mode: str, local_t: float, global_t: float, scene_len: float) -> None:
        u = clamp(local_t / max(scene_len, 0.01))
        self.x, self.y = WIDTH * 0.48, HEIGHT * 0.38
        self.bank = self.pitch = 0.0
        self.facing = 1.0
        flap = 6.0
        self.spread = 0.85

        if mode == "rest":
            self.x, self.y = WIDTH * 0.52, HEIGHT * 0.48
            self.spread, flap = 0.12, 0.0
            self.breath = 0.5 + 0.5 * math.sin(global_t * 1.4)
            self.wing_phase = 0.0
        elif mode == "wake":
            self.x, self.y = WIDTH * 0.52, HEIGHT * 0.46
            self.spread = smoothstep(0.15, 0.85, u) * 0.95
            flap = 2.0 + 4.0 * u
            self.pitch = -0.15 * u
        elif mode == "liftoff":
            self.y = lerp(HEIGHT * 0.48, HEIGHT * 0.22, smoothstep(0, 1, u))
            self.spread, flap, self.pitch = 1.0, 10.0, -0.55
        elif mode == "cruise":
            self.x = WIDTH * (0.4 + 0.15 * math.sin(global_t * 0.4))
            self.y = HEIGHT * 0.34 + 8 * math.sin(global_t * 1.2)
            flap = 5.5
        elif mode == "climb":
            self.y = lerp(HEIGHT * 0.42, HEIGHT * 0.22, u)
            self.pitch, self.bank, flap = -0.4, 0.25, 7.0
        elif mode == "glide":
            self.x = WIDTH * (0.35 + 0.35 * u)
            self.y = HEIGHT * 0.36 + 6 * math.sin(global_t)
            flap, self.spread = 1.2, 1.0
        elif mode == "swoop":
            self.x = WIDTH * (0.3 + 0.45 * u)
            self.y = HEIGHT * (0.22 + 0.45 * smoothstep(0, 0.7, u))
            self.pitch = 0.55 * math.sin(u * math.pi)
            self.bank, flap = -0.35, 8.0
        elif mode == "bank_glide":
            self.y = HEIGHT * 0.4 + 10 * math.sin(global_t * 0.8)
            self.bank = 0.4 * math.sin(global_t * 1.1)
            flap, self.spread = 0.8, 1.0
        elif mode == "skim":
            self.x = WIDTH * (0.35 + 0.3 * math.sin(global_t * 0.5))
            self.y = HEIGHT * 0.55 + 12 * math.sin(global_t * 2.0)
            flap, self.spread = 3.5, 0.95
        elif mode == "turbulence":
            self.x = WIDTH * 0.48 + 25 * math.sin(global_t * 7)
            self.y = HEIGHT * 0.36 + 18 * math.sin(global_t * 9.5)
            self.bank = 0.5 * math.sin(global_t * 6)
            flap = 9.0
        elif mode == "fast_low":
            self.x = WIDTH * (0.25 + 0.55 * u)
            self.y, flap = HEIGHT * 0.55, 11.0
        elif mode == "weave":
            self.x = WIDTH * 0.5 + 90 * math.sin(global_t * 2.4)
            self.y = HEIGHT * 0.4 + 40 * math.sin(global_t * 1.7)
            self.bank = 0.7 * math.cos(global_t * 2.4)
            flap = 9.5
        elif mode == "struggle":
            self.x = WIDTH * 0.42 + 10 * math.sin(global_t * 8)
            self.y = HEIGHT * 0.4 + 15 * math.sin(global_t * 10)
            flap, self.spread = 12.0, 0.75
        elif mode == "burst_climb":
            self.y = lerp(HEIGHT * 0.55, HEIGHT * 0.2, smoothstep(0, 1, u))
            self.pitch, flap = -0.7, 11.0
        elif mode == "long_glide":
            self.x = WIDTH * (0.3 + 0.4 * u)
            self.y = lerp(HEIGHT * 0.25, HEIGHT * 0.5, u)
            flap, self.spread, self.pitch = 0.6, 1.0, 0.15
        elif mode == "mirror":
            self.x = WIDTH * (0.35 + 0.3 * u)
            self.y, flap, self.spread = HEIGHT * 0.32, 4.0, 0.95
        elif mode == "diagonal":
            self.x = lerp(WIDTH * 0.1, WIDTH * 0.85, u)
            self.y = lerp(HEIGHT * 0.65, HEIGHT * 0.2, u)
            self.pitch, self.bank, flap = -0.45, 0.2, 6.0
        elif mode == "slow_cruise":
            self.x = WIDTH * (0.4 + 0.2 * u)
            self.y, flap = HEIGHT * 0.35, 3.0
        elif mode == "loop":
            ang = -math.pi / 2 + u * 2 * math.pi
            self.x = WIDTH * 0.5 + math.cos(ang) * 130
            self.y = HEIGHT * 0.42 + math.sin(ang) * 90
            self.pitch, flap, self.spread = ang + math.pi / 2, 5.0, 1.0
        elif mode == "horizon":
            self.x = WIDTH * (0.25 + 0.5 * u)
            self.y, flap = HEIGHT * 0.28, 4.5
        elif mode == "cloud_cut":
            self.x = WIDTH * (0.3 + 0.4 * u)
            self.y = HEIGHT * 0.4 + 20 * math.sin(global_t * 2)
            flap = 7.0
        elif mode in ("duo", "duo_descend"):
            self.x = WIDTH * 0.42
            self.y = HEIGHT * (0.32 if mode == "duo" else lerp(0.32, 0.55, u))
            flap = 4.0 if mode == "duo" else 3.0
        elif mode == "land":
            self.x = lerp(WIDTH * 0.4, WIDTH * 0.52, u)
            self.y = lerp(HEIGHT * 0.35, HEIGHT * 0.48, u)
            self.spread = lerp(0.9, 0.12, smoothstep(0.4, 0.95, u))
            flap = lerp(4.0, 0.0, u)
            self.breath = 0.5 + 0.5 * math.sin(global_t * 1.4) * u

        if flap > 0:
            self.wing_phase += flap * (1.0 / FPS) * 2 * math.pi

    def draw(self, ctx: cairo.Context) -> None:
        ctx.save()
        ctx.translate(self.x, self.y)
        ctx.rotate(self.pitch)
        ctx.scale(self.facing * self.scale, self.scale)
        ctx.rotate(self.bank * 0.35)
        if self.spread < 0.28:
            self._perched(ctx)
        else:
            self._flying(ctx)
        ctx.restore()

    def _paint_path(self, ctx: cairo.Context) -> None:
        ctx.set_source_rgb(*self.fill)
        ctx.fill_preserve()
        ctx.set_source_rgb(*self.outline)
        ctx.set_line_width(2.2)
        ctx.stroke()

    def _perched(self, ctx: cairo.Context) -> None:
        b = 1.0 + 0.05 * self.breath
        # soft yellow halo
        ctx.set_source_rgba(*YELLOW, 0.15)
        ctx.arc(0, 4, 20, 0, 2 * math.pi)
        ctx.fill()
        ctx.save()
        ctx.scale(1.4 * b, 0.95)
        ctx.arc(0, 2, 11, 0, 2 * math.pi)
        ctx.restore()
        self._paint_path(ctx)
        ctx.arc(12, -4, 6.5, 0, 2 * math.pi)
        self._paint_path(ctx)
        ctx.move_to(17, -4)
        ctx.line_to(25, -2)
        ctx.line_to(17, -1)
        ctx.close_path()
        self._paint_path(ctx)

    def _flying(self, ctx: cairo.Context) -> None:
        wing = math.sin(self.wing_phase)
        up = wing * (0.55 + 0.25 * self.spread) - (1.0 - self.spread) * 0.9
        # halo
        ctx.set_source_rgba(*YELLOW, 0.12)
        ctx.arc(0, 0, 34, 0, 2 * math.pi)
        ctx.fill()

        self._wing(ctx, -1.0, up * 0.9)
        # body
        ctx.save()
        ctx.scale(1.35, 0.72)
        ctx.arc(0, 0, 14, 0, 2 * math.pi)
        ctx.restore()
        self._paint_path(ctx)
        # head
        ctx.arc(20, -4, 7, 0, 2 * math.pi)
        self._paint_path(ctx)
        ctx.move_to(26, -4)
        ctx.line_to(36, -2)
        ctx.line_to(26, 0)
        ctx.close_path()
        self._paint_path(ctx)
        # eye
        ctx.set_source_rgb(*YELLOW)
        ctx.arc(22, -6, 1.5, 0, 2 * math.pi)
        ctx.fill()
        self._wing(ctx, 1.0, up)
        # tail
        ctx.move_to(-18, 2)
        ctx.curve_to(-30, -4, -40, 0, -44, 4)
        ctx.curve_to(-34, 8, -24, 8, -18, 4)
        ctx.close_path()
        self._paint_path(ctx)

    def _wing(self, ctx: cairo.Context, side: float, up: float) -> None:
        ctx.save()
        ctx.translate(2, -2)
        fold = (1.0 - self.spread) * 0.85
        ctx.rotate(side * (-0.12 + up * 1.0) - side * fold)
        tip = 42 * max(self.spread, 0.2)
        flap = up * 0.55
        ctx.move_to(0, 0)
        ctx.curve_to(10 * side, -12 - flap * 20, 24 * side, -18 - flap * 26, tip * side, -6 - flap * 10)
        ctx.curve_to(28 * side, 6, 10 * side, 10, 0, 5)
        ctx.close_path()
        self._paint_path(ctx)
        # feather ticks
        ctx.set_source_rgb(*self.outline)
        ctx.set_line_width(1.6)
        for i in range(5):
            fx = tip * side * 0.55 + side * (4 + i * 4)
            fy = -4 - flap * 6 + i * 3
            ctx.move_to(tip * side * 0.3, -2)
            ctx.line_to(fx, fy)
            ctx.stroke()
        ctx.restore()


# ==============================================================================
# SCENE PAINTER
# ==============================================================================
class ScenePainter:
    def __init__(self):
        self.canvas = CairoCanvas()
        self.brush = VanGoghBrush()
        self.bird = BirdRig()
        self.bird2 = BirdRig(scale=1.1, fill=(0.12, 0.14, 0.28))

    def render_scene(self, scene_id: str, mode: str, local_t: float,
                     global_t: float, scene_len: float) -> pygame.Surface:
        ctx = self.canvas.ctx
        self.canvas.clear()
        drawers = {
            "predawn_roost": self._predawn,
            "dawn_awakening": self._dawn,
            "vertical_liftoff": self._liftoff,
            "emerald_canopy": self._emerald,
            "alpine_ridge": self._alpine,
            "valley_clearing": self._valley,
            "coastal_cliffs": self._cliffs,
            "marine_shore": self._shore,
            "open_ocean": self._ocean,
            "desert_dunes": self._dunes,
            "salt_flats": self._salt,
            "desert_canyon": self._canyon,
            "dust_storm": self._dust,
            "storm_breach": self._breach,
            "sea_swells": self._swells,
            "tidal_mirror": self._mirror,
            "deep_swells": self._deep,
            "sunset_islands": self._islands,
            "mandala_sky": self._mandala,
            "twilight_alps": self._twilight_alps,
            "sunset_clouds": self._sunset_clouds,
            "sanctuary": self._sanctuary,
            "twilight_forest": self._twilight_forest,
            "roost_return": self._roost_return,
        }
        drawers.get(scene_id, self._predawn)(ctx, local_t, global_t)

        self.bird.update(mode, local_t, global_t, scene_len)
        if scene_id == "tidal_mirror":
            water_y = HEIGHT * 0.55
            self.bird.draw(ctx)
            ctx.save()
            ctx.rectangle(0, water_y, WIDTH, HEIGHT - water_y)
            ctx.clip()
            ctx.push_group()
            ctx.translate(0, 2 * water_y)
            ctx.scale(1, -1)
            self.bird.draw(ctx)
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(0.4)
            ctx.restore()
        elif mode in ("duo", "duo_descend", "land"):
            self.bird.draw(ctx)
            self.bird2.wing_phase = self.bird.wing_phase + 0.35
            self.bird2.spread = self.bird.spread
            self.bird2.pitch = self.bird.pitch
            self.bird2.bank = -self.bird.bank * 0.4
            self.bird2.x = self.bird.x + 72
            self.bird2.y = self.bird.y + 10
            self.bird2.draw(ctx)
        else:
            self.bird.draw(ctx)

        if mode == "cloud_cut":
            for i in range(10):
                px = self.bird.x - 18 - i * 12
                py = self.bird.y + 3 * math.sin(global_t * 3 + i)
                self.brush.stroke_curve(ctx, px, py, math.pi, 10, 3, CREAM, 0.25)

        return self.canvas.to_pygame()

    def _starry_sky(self, ctx, t, vortices=None):
        self.brush.underpaint(ctx, NIGHT, ULTRA, COBALT)
        v = vortices or [(WIDTH * 0.7, HEIGHT * 0.28, 1.3), (WIDTH * 0.3, HEIGHT * 0.2, 0.9)]
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.7,
            [NIGHT, ULTRA, COBALT, VIOLET, (0.15, 0.25, 0.6)],
            spacing=17, length=26, width=6.5, alpha=0.7,
            vortices=v, jitter=0.1,
        )
        self.brush.paint_stars(ctx, t, 26)

    def _predawn(self, ctx, local_t, t):
        self._starry_sky(ctx, t)
        self.brush.paint_moon(ctx, WIDTH * 0.78, HEIGHT * 0.18, 34, t)
        self.brush.paint_hills(ctx, t, HEIGHT * 0.72, [CYPRESS, OLIVE, (0.06, 0.12, 0.1)], 40)
        for i, x in enumerate([120, 280, 860, 980]):
            self.brush.paint_cypress(ctx, x, HEIGHT * 0.78, 140 + i * 20, t, 0.4)
        self.brush.paint_tree_of_life(ctx, WIDTH * 0.55, HEIGHT * 0.92, 1.25, t)

    def _dawn(self, ctx, local_t, t):
        u = clamp(local_t / 8.0)
        top = lerp_color(NIGHT, COBALT, u)
        mid = lerp_color(ULTRA, OCHRE, u)
        bot = lerp_color(VIOLET, VERMILION, u * 0.7)
        self.brush.underpaint(ctx, top, bot, mid)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.65,
            [top, mid, bot, YELLOW, VIOLET],
            spacing=17, length=24, width=6, alpha=0.65,
            vortices=[(WIDTH * 0.2, HEIGHT * 0.45, 0.8)],
        )
        # rising sun
        sx, sy = WIDTH * 0.18, HEIGHT * (0.55 - 0.2 * u)
        for mul, a in [(3.0, 0.15), (1.8, 0.35), (1.0, 1.0)]:
            ctx.set_source_rgba(*YELLOW, a)
            ctx.arc(sx, sy, (16 + 14 * u) * mul, 0, 2 * math.pi)
            ctx.fill()
        self.brush.paint_hills(ctx, t, HEIGHT * 0.7, [OLIVE, CYPRESS, VIRIDIAN], 50)
        self.brush.paint_tree_of_life(ctx, WIDTH * 0.55, HEIGHT * 0.95, 1.2, t)

    def _liftoff(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, CREAM, (0.55, 0.7, 0.9))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT,
            [COBALT, ULTRA, CREAM, (0.6, 0.75, 0.95), YELLOW],
            spacing=18, length=28, width=6, alpha=0.6,
            vortices=[(WIDTH * 0.5, HEIGHT * 0.35, 1.1)],
        )
        u = clamp(local_t / 6.5)
        self.brush.paint_hills(ctx, t, HEIGHT * (0.7 + 0.35 * u), [VIRIDIAN, OLIVE, CYPRESS], 70)

    def _emerald(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, VIRIDIAN, (0.4, 0.65, 0.85))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.45,
            [COBALT, (0.45, 0.7, 0.9), CREAM],
            spacing=18, length=22, width=5.5, alpha=0.6,
        )
        self.brush.paint_hills(ctx, t, HEIGHT * 0.48, [VIRIDIAN, OLIVE, CYPRESS, (0.1, 0.35, 0.2)], 80)
        self.brush.paint_flow_field(
            ctx, t, HEIGHT * 0.45, HEIGHT,
            [VIRIDIAN, OLIVE, (0.15, 0.4, 0.22), CYPRESS],
            spacing=16, length=20, width=6, alpha=0.75, scale=0.012,
        )

    def _alpine(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, CREAM, (0.65, 0.75, 0.88))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.5,
            [COBALT, ULTRA, CREAM, (0.5, 0.6, 0.75)],
            spacing=18, length=24, width=6, alpha=0.6,
            vortices=[(WIDTH * 0.6, HEIGHT * 0.25, 0.7)],
        )
        self.brush.paint_hills(ctx, t, HEIGHT * 0.5, [(0.35, 0.4, 0.5), (0.25, 0.3, 0.4), CYPRESS], 120)
        for i in range(8):
            x = 80 + i * 130
            self.brush.paint_cypress(ctx, x, HEIGHT * 0.7, 100 + 40 * hash01(i), t, 0.5)

    def _valley(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, YELLOW, (0.55, 0.75, 0.9))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.55,
            [COBALT, CREAM, YELLOW, (0.7, 0.8, 0.95)],
            spacing=17, length=24, width=6, alpha=0.55,
            vortices=[(WIDTH * 0.75, HEIGHT * 0.2, 0.9)],
        )
        # sunbeams as long yellow strokes
        for i in range(12):
            ang = 0.9 + i * 0.12
            self.brush.stroke_curve(
                ctx, WIDTH * 0.75, HEIGHT * 0.15, ang, 380, 10,
                jitter_color(YELLOW, 0.1, i), 0.18,
            )
        self.brush.paint_wheat(ctx, t, HEIGHT * 0.55)

    def _cliffs(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, TURQ, (0.55, 0.75, 0.9))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.55,
            [COBALT, CREAM, (0.5, 0.7, 0.9)],
            spacing=18, length=22, width=5.5, alpha=0.55,
        )
        self.brush.paint_ocean(ctx, t, HEIGHT * 0.62, [TURQ, ULTRA, COBALT, (0.2, 0.45, 0.55)])
        # cliff mass on right
        ctx.set_source_rgb(0.35, 0.32, 0.28)
        ctx.move_to(WIDTH * 0.58, 0)
        ctx.line_to(WIDTH, 0)
        ctx.line_to(WIDTH, HEIGHT)
        ctx.line_to(WIDTH * 0.55, HEIGHT)
        for i in range(12):
            y = HEIGHT - i * HEIGHT / 11
            ctx.line_to(WIDTH * 0.58 + 30 * math.sin(i), y)
        ctx.close_path()
        ctx.fill()
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT,
            [(0.4, 0.35, 0.28), SIENNA, (0.25, 0.22, 0.2), OCHRE],
            spacing=16, length=20, width=6, alpha=0.75,
            x0=WIDTH * 0.55, x1=WIDTH, scale=0.015,
        )

    def _shore(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, CREAM, (0.65, 0.8, 0.88))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.5,
            [COBALT, CREAM, (0.7, 0.82, 0.9)],
            spacing=18, length=22, width=5, alpha=0.5,
        )
        self.brush.paint_ocean(ctx, t, HEIGHT * 0.48, [TURQ, (0.4, 0.7, 0.72), COBALT])
        self.brush.paint_flow_field(
            ctx, t, HEIGHT * 0.62, HEIGHT,
            [OCHRE, CREAM, (0.75, 0.65, 0.45), (0.55, 0.5, 0.4)],
            spacing=16, length=18, width=5, alpha=0.7,
        )

    def _ocean(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, ULTRA, (0.35, 0.55, 0.8))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.4,
            [COBALT, ULTRA, CREAM],
            spacing=18, length=24, width=6, alpha=0.55,
            vortices=[(WIDTH * 0.4, HEIGHT * 0.2, 0.6)],
        )
        self.brush.paint_ocean(
            ctx, t, HEIGHT * 0.38,
            [ULTRA, TURQ, COBALT, NIGHT, (0.15, 0.35, 0.55)],
        )

    def _dunes(self, ctx, local_t, t):
        self.brush.underpaint(ctx, OCHRE, VERMILION, (0.85, 0.55, 0.25))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.45,
            [OCHRE, CHROME, VERMILION, YELLOW],
            spacing=17, length=26, width=6, alpha=0.6,
            vortices=[(WIDTH * 0.5, HEIGHT * 0.25, 0.8)],
        )
        self.brush.paint_dunes(ctx, t)

    def _salt(self, ctx, local_t, t):
        self.brush.underpaint(ctx, CREAM, OCHRE, (0.9, 0.8, 0.55))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.45,
            [CREAM, OCHRE, YELLOW, (0.85, 0.75, 0.5)],
            spacing=18, length=22, width=5, alpha=0.55,
        )
        self.brush.paint_flow_field(
            ctx, t, HEIGHT * 0.4, HEIGHT,
            [CREAM, (0.8, 0.72, 0.55), OCHRE, (0.35, 0.28, 0.2)],
            spacing=16, length=18, width=4.5, alpha=0.7, scale=0.02,
        )
        # crack strokes
        for i in range(24):
            x = hash01(i * 3) * WIDTH
            y = HEIGHT * 0.5 + hash01(i * 3 + 1) * HEIGHT * 0.4
            ang = self.brush.flow_angle(x, y, t, 0.03)
            self.brush.stroke_curve(ctx, x, y, ang, 30, 2.2, (0.3, 0.22, 0.15), 0.7)

    def _canyon(self, ctx, local_t, t):
        self.brush.underpaint(ctx, COBALT, OCHRE, VERMILION)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.5,
            [COBALT, YELLOW, VERMILION, OCHRE],
            spacing=18, length=24, width=6, alpha=0.55,
        )
        self.brush.paint_canyon(ctx, t)

    def _dust(self, ctx, local_t, t):
        self.brush.underpaint(ctx, SIENNA, (0.35, 0.22, 0.12), OCHRE)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT,
            [SIENNA, OCHRE, (0.4, 0.25, 0.12), VERMILION, (0.55, 0.35, 0.18)],
            spacing=16, length=30, width=7, alpha=0.65,
            vortices=[(WIDTH * 0.5, HEIGHT * 0.45, 1.6)],
            jitter=0.15,
        )

    def _breach(self, ctx, local_t, t):
        u = clamp(local_t / 7.5)
        top = lerp_color(SIENNA, COBALT, u)
        bot = lerp_color(OCHRE, TURQ, u)
        self.brush.underpaint(ctx, top, bot, lerp_color(OCHRE, CREAM, u))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.5,
            [top, bot, YELLOW, COBALT],
            spacing=17, length=26, width=6, alpha=0.6,
            vortices=[(WIDTH * 0.5, HEIGHT * 0.3, 1.0)],
        )
        self.brush.paint_ocean(ctx, t, HEIGHT * 0.5, [TURQ, ULTRA, COBALT, FOAM])
        if u < 0.6:
            self.brush.paint_flow_field(
                ctx, t, 0, HEIGHT,
                [SIENNA, OCHRE], spacing=18, length=28, width=8,
                alpha=0.35 * (1 - u), vortices=[(WIDTH * 0.4, HEIGHT * 0.4, 1.2)],
            )

    def _swells(self, ctx, local_t, t):
        self.brush.underpaint(ctx, NIGHT, VIOLET, ULTRA)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.45,
            [NIGHT, VIOLET, ULTRA, (0.45, 0.3, 0.55)],
            spacing=17, length=26, width=6, alpha=0.65,
            vortices=[(WIDTH * 0.6, HEIGHT * 0.25, 1.0)],
        )
        self.brush.paint_ocean(
            ctx, t, HEIGHT * 0.42,
            [NIGHT, ULTRA, VIOLET, (0.15, 0.2, 0.4)],
            foam=(CREAM, (0.7, 0.7, 0.85), WHITE),
        )

    def _mirror(self, ctx, local_t, t):
        self._starry_sky(ctx, t, [(WIDTH * 0.5, HEIGHT * 0.3, 1.0)])
        self.brush.paint_moon(ctx, WIDTH * 0.7, HEIGHT * 0.22, 28, t)
        # reflective water with horizontal strokes
        self.brush.paint_flow_field(
            ctx, t, HEIGHT * 0.55, HEIGHT,
            [VIOLET, ULTRA, NIGHT, CREAM, (0.4, 0.3, 0.5)],
            spacing=15, length=30, width=5, alpha=0.7, scale=0.003,
        )

    def _deep(self, ctx, local_t, t):
        self.brush.underpaint(ctx, NIGHT, VERMILION, VIOLET)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.4,
            [NIGHT, VIOLET, VERMILION, (0.5, 0.25, 0.35)],
            spacing=17, length=26, width=6, alpha=0.6,
        )
        self.brush.paint_ocean(ctx, t, HEIGHT * 0.35, [NIGHT, ULTRA, (0.1, 0.15, 0.35), VIOLET])

    def _islands(self, ctx, local_t, t):
        self.brush.underpaint(ctx, VIOLET, VERMILION, YELLOW)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.55,
            [VIOLET, VERMILION, YELLOW, OCHRE, CHROME],
            spacing=16, length=26, width=6.5, alpha=0.65,
            vortices=[(WIDTH * 0.7, HEIGHT * 0.4, 1.1)],
        )
        # sun
        ctx.set_source_rgb(*YELLOW)
        ctx.arc(WIDTH * 0.7, HEIGHT * 0.42, 36, 0, 2 * math.pi)
        ctx.fill()
        self.brush.paint_ocean(ctx, t, HEIGHT * 0.55, [VIOLET, NIGHT, VERMILION, ULTRA])
        # island silhouettes
        for cx, w, h in [(200, 140, 50), (480, 200, 70), (780, 150, 55)]:
            ctx.set_source_rgb(*CYPRESS)
            ctx.move_to(cx - w / 2, HEIGHT * 0.55)
            ctx.curve_to(cx - 20, HEIGHT * 0.55 - h, cx + 20, HEIGHT * 0.55 - h * 1.1, cx + w / 2, HEIGHT * 0.55)
            ctx.close_path()
            ctx.fill()

    def _mandala(self, ctx, local_t, t):
        self.brush.underpaint(ctx, VIOLET, VERMILION, YELLOW)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT,
            [VIOLET, VERMILION, YELLOW, OCHRE, CHROME, ULTRA],
            spacing=16, length=28, width=6.5, alpha=0.55,
            vortices=[(WIDTH * 0.5, HEIGHT * 0.42, 1.8)],
        )
        self.brush.paint_mandala(ctx, WIDTH * 0.5, HEIGHT * 0.42, t)

    def _twilight_alps(self, ctx, local_t, t):
        self.brush.underpaint(ctx, NIGHT, VERMILION, VIOLET)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.5,
            [NIGHT, VIOLET, VERMILION, OCHRE],
            spacing=17, length=24, width=6, alpha=0.6,
        )
        self.brush.paint_hills(ctx, t, HEIGHT * 0.45, [VIOLET, NIGHT, (0.2, 0.1, 0.25), CYPRESS], 140)

    def _sunset_clouds(self, ctx, local_t, t):
        self.brush.underpaint(ctx, VIOLET, VERMILION, YELLOW)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT,
            [VIOLET, VERMILION, YELLOW, OCHRE, CREAM, (0.5, 0.3, 0.4)],
            spacing=16, length=30, width=8, alpha=0.6,
            vortices=[
                (WIDTH * 0.3, HEIGHT * 0.35, 1.0),
                (WIDTH * 0.7, HEIGHT * 0.45, 1.2),
            ],
            jitter=0.14,
        )

    def _sanctuary(self, ctx, local_t, t):
        self.brush.underpaint(ctx, VIOLET, VERMILION, (0.85, 0.55, 0.4))
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.7,
            [VIOLET, (0.55, 0.3, 0.45), VERMILION, CREAM],
            spacing=17, length=24, width=6, alpha=0.6,
        )
        self.brush.paint_hills(ctx, t, HEIGHT * 0.7, [NIGHT, VIOLET, CYPRESS], 50)

    def _twilight_forest(self, ctx, local_t, t):
        self.brush.underpaint(ctx, NIGHT, VIOLET, ULTRA)
        self.brush.paint_flow_field(
            ctx, t, 0, HEIGHT * 0.6,
            [NIGHT, VIOLET, ULTRA],
            spacing=18, length=24, width=6, alpha=0.6,
        )
        self.brush.paint_hills(ctx, t, HEIGHT * 0.65, [CYPRESS, OLIVE, NIGHT], 40)
        for i in range(10):
            self.brush.paint_cypress(ctx, 60 + i * 110, HEIGHT * 0.82, 120 + 50 * hash01(i), t, 0.5)

    def _roost_return(self, ctx, local_t, t):
        u = clamp(local_t / 5.0)
        self._starry_sky(ctx, t)
        self.brush.paint_moon(ctx, WIDTH * 0.8, HEIGHT * 0.2, 30, t)
        self.brush.paint_hills(ctx, t, HEIGHT * 0.75, [CYPRESS, NIGHT, OLIVE], 35)
        self.brush.paint_tree_of_life(ctx, WIDTH * 0.52, HEIGHT * 0.95, 1.35, t)
        # fade toward black
        if u > 0.3:
            ctx.set_source_rgba(0, 0, 0, (u - 0.3) * 0.5)
            ctx.paint()


# ==============================================================================
# TIMELINE / MAIN
# ==============================================================================
def scene_at(t: float):
    t = clamp(t, 0.0, SONG_DURATION - 0.001)
    for i, (start, end, sid, mode, label) in enumerate(SCENES):
        if start <= t < end or (i == len(SCENES) - 1 and t <= end):
            return i, start, end, sid, mode, label
    return len(SCENES) - 1, *SCENES[-1]


def crossfade_weight(t: float) -> Tuple[int, int, float]:
    idx, start, end, *_ = scene_at(t)
    remaining = end - t
    if remaining < CROSSFADE and idx < len(SCENES) - 1:
        return idx, idx + 1, smoothstep(0.0, 1.0, 1.0 - remaining / CROSSFADE)
    return idx, idx, 0.0


def blend_frames(dst: pygame.Surface, a: pygame.Surface, b: pygame.Surface, t: float) -> None:
    t = clamp(t)
    if t <= 0.001:
        dst.blit(a, (0, 0))
        return
    if t >= 0.999:
        dst.blit(b, (0, 0))
        return
    tmp = a.copy()
    overlay = b.copy()
    overlay.set_alpha(int(255 * t))
    tmp.blit(overlay, (0, 0))
    dst.blit(tmp, (0, 0))


def main():
    args = parse_args()
    if args.no_preview:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
    except pygame.error as e:
        print(f"[AUDIO] mixer init failed: {e}")

    export_mode = bool(args.export)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Free as a Bird — Van Gogh")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("dejavusans", 16)

    painter = ScenePainter()
    painter_b = ScenePainter()

    seek_base = max(0.0, args.start)
    audio_ok = AUDIO_PATH.is_file()
    if audio_ok and not export_mode:
        try:
            pygame.mixer.music.load(str(AUDIO_PATH))
            pygame.mixer.music.play(start=seek_base)
        except pygame.error as e:
            print(f"[AUDIO] {e}")
            audio_ok = False
    elif not audio_ok:
        print(f"[AUDIO] Missing {AUDIO_PATH.name} — silent timeline.")

    recorder = None
    if export_mode:
        recorder = FfmpegRecorder(
            args.output, audio_path=AUDIO_PATH if AUDIO_PATH.is_file() else None
        )
        print(f"Exporting Van Gogh style to {args.output} ...")

    start_t = seek_base
    duration = args.duration if args.duration is not None else (SONG_DURATION - start_t)
    end_t = min(SONG_DURATION, start_t + duration)
    total_frames = max(1, int((end_t - start_t) * FPS))
    frame_index = 0
    running = True
    paused = False
    manual_t = start_t
    show_hud = (not export_mode) or args.hud

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE and not export_mode:
                    paused = not paused
                    if audio_ok:
                        (pygame.mixer.music.pause if paused else pygame.mixer.music.unpause)()
                elif event.key == pygame.K_h:
                    show_hud = not show_hud
                elif event.key == pygame.K_RIGHT and not export_mode:
                    if audio_ok:
                        pos_ms = pygame.mixer.music.get_pos()
                        cur = seek_base + max(0, pos_ms) / 1000.0
                        seek_base = min(SONG_DURATION - 0.05, cur + 5.0)
                        pygame.mixer.music.play(start=seek_base)
                    else:
                        manual_t = min(SONG_DURATION - 0.05, manual_t + 5.0)
                elif event.key == pygame.K_LEFT and not export_mode:
                    if audio_ok:
                        pos_ms = pygame.mixer.music.get_pos()
                        cur = seek_base + max(0, pos_ms) / 1000.0
                        seek_base = max(0.0, cur - 5.0)
                        pygame.mixer.music.play(start=seek_base)
                    else:
                        manual_t = max(0.0, manual_t - 5.0)

        if export_mode:
            current_sec = start_t + frame_index / float(FPS)
            if frame_index >= total_frames:
                running = False
                continue
        else:
            if audio_ok and not paused:
                pos_ms = pygame.mixer.music.get_pos()
                current_sec = seek_base + max(0, pos_ms) / 1000.0 if pos_ms >= 0 else manual_t
                manual_t = current_sec
            elif not paused:
                manual_t += 1.0 / FPS
                current_sec = manual_t
            else:
                current_sec = manual_t
            if current_sec >= SONG_DURATION:
                running = False
                continue

        ia, ib, blend = crossfade_weight(current_sec)
        sa = SCENES[ia]
        frame_a = painter.render_scene(sa[2], sa[3], current_sec - sa[0], current_sec, sa[1] - sa[0])
        if blend > 0.001:
            sb = SCENES[ib]
            frame_b = painter_b.render_scene(
                sb[2], sb[3], max(0.0, current_sec - sb[0]), current_sec, sb[1] - sb[0]
            )
            blend_frames(screen, frame_a, frame_b, blend)
        else:
            screen.blit(frame_a, (0, 0))

        pygame.draw.rect(screen, (0, 0, 0), (0, 0, WIDTH, 36))
        pygame.draw.rect(screen, (0, 0, 0), (0, HEIGHT - 36, WIDTH, 36))

        if show_hud:
            _, _, _, _, _, label = scene_at(current_sec)
            mins, secs = int(current_sec // 60), int(current_sec % 60)
            hud = f"{mins:02d}:{secs:02d} / 03:00  ·  {label}"
            if not export_mode:
                hud += "   [Space · ←/→ · H · Esc]"
            screen.blit(font.render(hud, True, (220, 200, 120)), (18, 10))

        if export_mode:
            recorder.write_frame(screen)
            frame_index += 1
            if not args.no_preview:
                pygame.display.flip()
            if frame_index % (FPS * 5) == 0 or frame_index >= total_frames:
                print(f"  {frame_index}/{total_frames} frames ({100 * frame_index / total_frames:.0f}%)")
        else:
            pygame.display.flip()
            clock.tick(FPS)
            frame_index += 1

    if recorder:
        print(f"Done → {recorder.close()}")
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
