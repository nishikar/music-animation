#!/usr/bin/env python3
"""
Free as a Bird — cinematic flight animation (pycairo + pygame).

Realistic vector scenery and an articulated bird synchronized to free_as_a_bird.mp3.
Interactive playback by default; use --export to render an MP4 via ffmpeg.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

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
DEFAULT_EXPORT_PATH = SCRIPT_DIR / "free_as_a_bird.mp4"

Color = Tuple[float, float, float]
ColorA = Tuple[float, float, float, float]


# ==============================================================================
# TIMELINE
# ==============================================================================
# (start, end, scene_id, bird_mode, stage_label)
SCENES = [
    (0.0, 10.0, "predawn_roost", "rest", "Intro I · Predawn Roost"),
    (10.0, 18.0, "dawn_awakening", "wake", "Intro II · Dawn Awakening"),
    (18.0, 24.5, "vertical_liftoff", "liftoff", "Intro III · Vertical Liftoff"),
    (24.5, 31.5, "emerald_canopy", "cruise", "Verse 1A · Emerald Canopy"),
    (31.5, 38.5, "alpine_ridge", "climb", "Verse 1B · Alpine Pine Ridge"),
    (38.5, 46.0, "valley_clearing", "glide", "Verse 1C · Valley Clearing"),
    (46.0, 53.0, "coastal_cliffs", "swoop", "Verse 2A · Coastal Cliff Descent"),
    (53.0, 60.0, "marine_shore", "bank_glide", "Verse 2B · Marine Shoreline"),
    (60.0, 67.5, "open_ocean", "skim", "Verse 2C · Open Ocean"),
    (67.5, 77.0, "desert_dunes", "turbulence", "Bridge 1A · Arid Desert Dunes"),
    (77.0, 83.0, "salt_flats", "fast_low", "Bridge 1B · Cracked Salt Flats"),
    (83.0, 90.0, "desert_canyon", "weave", "Bridge 1C · Desert Canyon Pass"),
    (90.0, 96.5, "dust_storm", "struggle", "Bridge 1D · Dust Storm Vortex"),
    (96.5, 104.0, "storm_breach", "burst_climb", "Bridge 1E · Coastal Storm Breach"),
    (104.0, 113.5, "sea_swells", "long_glide", "Bridge 1F · Open Sea Swells"),
    (113.5, 120.0, "tidal_mirror", "mirror", "Verse 3A · Tidal Flat Mirror"),
    (120.0, 127.0, "deep_swells", "diagonal", "Verse 3B · Deep-Sea Swells"),
    (127.0, 135.5, "sunset_islands", "slow_cruise", "Verse 3C · Sunset Coastline"),
    (135.5, 148.0, "mandala_sky", "loop", "Instrumental · Thermal Mandala"),
    (148.0, 157.0, "twilight_alps", "horizon", "Bridge Reprise 1A · Alpine Ridges"),
    (157.0, 163.0, "sunset_clouds", "cloud_cut", "Bridge Reprise 1B · Sunset Clouds"),
    (163.0, 170.0, "sanctuary", "duo", "Bridge Reprise 1C · Sanctuary"),
    (170.0, 175.0, "twilight_forest", "duo_descend", "Outro A · Twilight Forest"),
    (175.0, 180.0, "roost_return", "land", "Outro B · Roost Tree of Life"),
]


# ==============================================================================
# MATH / COLOR HELPERS
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
    return lerp(hash01(int(i)), hash01(int(i) + 1), u)


def fbm(x: float, octaves: int = 4) -> float:
    amp, freq, total, norm = 0.5, 1.0, 0.0, 0.0
    for _ in range(octaves):
        total += amp * noise1(x * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / max(norm, 1e-9)


# ==============================================================================
# FFMPEG EXPORT
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
    p = argparse.ArgumentParser(description="Free as a Bird cinematic animation")
    p.add_argument("--export", "-e", action="store_true", help="Render MP4 via ffmpeg")
    p.add_argument("--output", "-o", type=Path, default=DEFAULT_EXPORT_PATH)
    p.add_argument("--no-preview", action="store_true", help="Headless export (dummy video)")
    p.add_argument("--hud", action="store_true", help="Show HUD in exported video")
    p.add_argument("--start", type=float, default=0.0, help="Start time in seconds (preview)")
    p.add_argument("--duration", type=float, default=None, help="Limit render duration (export)")
    return p.parse_args()


# ==============================================================================
# CAIRO SURFACE BRIDGE
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
# DRAWING PRIMITIVES — scenery building blocks
# ==============================================================================
def paint_sky(ctx: cairo.Context, w: int, h: int, top: Color, mid: Color, bot: Color,
              mid_stop: float = 0.55) -> None:
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgb(0.0, *top)
    g.add_color_stop_rgb(mid_stop, *mid)
    g.add_color_stop_rgb(1.0, *bot)
    ctx.set_source(g)
    ctx.paint()


def draw_stars(ctx: cairo.Context, t: float, count: int = 90, alpha: float = 1.0,
               seed: int = 7) -> None:
    for i in range(count):
        sx = hash01(seed + i * 3) * WIDTH
        sy = hash01(seed + i * 3 + 1) * HEIGHT * 0.62
        tw = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * (1.4 + hash01(i) * 2.5) + i))
        r = 0.6 + hash01(seed + i * 5) * 1.8
        a = alpha * tw * (0.35 + 0.65 * hash01(i + 9))
        ctx.set_source_rgba(0.95, 0.97, 1.0, a)
        ctx.arc(sx, sy, r, 0, 2 * math.pi)
        ctx.fill()
        if r > 1.6:
            ctx.set_source_rgba(0.7, 0.85, 1.0, a * 0.25)
            ctx.arc(sx, sy, r * 2.4, 0, 2 * math.pi)
            ctx.fill()


def draw_sun(ctx: cairo.Context, x: float, y: float, radius: float,
             core: Color = (1.0, 0.95, 0.75), glow: ColorA = (1.0, 0.7, 0.3, 0.22)) -> None:
    for i, (mul, a) in enumerate([(4.5, glow[3] * 0.35), (2.8, glow[3] * 0.55), (1.6, glow[3])]):
        ctx.set_source_rgba(glow[0], glow[1], glow[2], a)
        ctx.arc(x, y, radius * mul, 0, 2 * math.pi)
        ctx.fill()
    ctx.set_source_rgb(*core)
    ctx.arc(x, y, radius, 0, 2 * math.pi)
    ctx.fill()


def draw_moon(ctx: cairo.Context, x: float, y: float, radius: float = 28) -> None:
    ctx.set_source_rgba(0.85, 0.9, 1.0, 0.18)
    ctx.arc(x, y, radius * 2.2, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgb(0.92, 0.94, 0.98)
    ctx.arc(x, y, radius, 0, 2 * math.pi)
    ctx.fill()
    # subtle crater shading
    ctx.set_source_rgba(0.7, 0.75, 0.85, 0.25)
    ctx.arc(x - radius * 0.25, y - radius * 0.15, radius * 0.22, 0, 2 * math.pi)
    ctx.fill()
    ctx.arc(x + radius * 0.3, y + radius * 0.2, radius * 0.14, 0, 2 * math.pi)
    ctx.fill()


def fractal_branch(ctx: cairo.Context, x: float, y: float, angle: float, length: float,
                   depth: int, t: float, sway: float = 0.0) -> None:
    if depth <= 0 or length < 3:
        return
    wind = sway * (0.02 + 0.01 * depth) * math.sin(t * 0.7 + depth * 0.4 + x * 0.01)
    a = angle + wind
    x2 = x + math.cos(a) * length
    y2 = y + math.sin(a) * length
    width = max(0.6, length * 0.085)
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(x, y)
    ctx.line_to(x2, y2)
    ctx.stroke()
    # foliage tufts near tips
    if depth <= 2:
        ctx.set_source_rgba(0.05, 0.12, 0.08, 0.55)
        ctx.arc(x2, y2, length * 0.35, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.08, 0.07, 0.06)
    spread = 0.42 + 0.08 * hash01(depth * 17 + int(x))
    fractal_branch(ctx, x2, y2, a - spread, length * 0.72, depth - 1, t, sway)
    fractal_branch(ctx, x2, y2, a + spread * 0.95, length * 0.68, depth - 1, t, sway)
    if depth > 3 and hash01(int(x) + depth * 31) > 0.55:
        fractal_branch(ctx, x2, y2, a + 0.05, length * 0.55, depth - 2, t, sway)


def draw_ancient_tree(ctx: cairo.Context, cx: float, base_y: float, scale: float,
                      t: float, trunk_rgb: Color = (0.08, 0.07, 0.06),
                      sway: float = 0.0) -> None:
    ctx.save()
    ctx.set_source_rgb(*trunk_rgb)
    # thick trunk with slight curve
    ctx.set_line_width(18 * scale)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(cx - 8 * scale, base_y)
    ctx.curve_to(cx - 4 * scale, base_y - 80 * scale,
                 cx + 6 * scale, base_y - 160 * scale,
                 cx, base_y - 220 * scale)
    ctx.stroke()
    # roots
    ctx.set_line_width(6 * scale)
    for dx, ang in [(-28, 2.6), (-12, 2.9), (14, 0.25), (30, -0.15)]:
        ctx.move_to(cx, base_y)
        ctx.line_to(cx + dx * scale, base_y + 8 * scale)
        ctx.stroke()
    # canopy branches
    fractal_branch(ctx, cx, base_y - 210 * scale, -math.pi / 2 - 0.15,
                   95 * scale, 6, t, sway)
    fractal_branch(ctx, cx, base_y - 200 * scale, -math.pi / 2 + 0.35,
                   80 * scale, 5, t, sway)
    fractal_branch(ctx, cx, base_y - 185 * scale, -math.pi / 2 - 0.55,
                   70 * scale, 5, t, sway)
    ctx.restore()


def draw_pine(ctx: cairo.Context, x: float, base_y: float, h: float,
              color: Color = (0.12, 0.22, 0.14)) -> None:
    ctx.set_source_rgb(*color)
    trunk_w = h * 0.04
    ctx.rectangle(x - trunk_w / 2, base_y - h * 0.25, trunk_w, h * 0.25)
    ctx.fill()
    for i in range(5):
        ty = base_y - h * (0.22 + i * 0.16)
        half = h * (0.28 - i * 0.04)
        ctx.move_to(x, ty - h * 0.18)
        ctx.line_to(x - half, ty + h * 0.05)
        ctx.line_to(x + half, ty + h * 0.05)
        ctx.close_path()
        shade = 0.85 + 0.03 * i
        ctx.set_source_rgb(color[0] * shade, color[1] * shade, color[2] * shade)
        ctx.fill()


def draw_canopy_layer(ctx: cairo.Context, y: float, t: float, scroll: float,
                      color: Color, density: int = 28, amp: float = 18) -> None:
    ctx.set_source_rgb(*color)
    ctx.move_to(-40, HEIGHT)
    ctx.line_to(-40, y)
    for i in range(density + 2):
        x = -40 + i * ((WIDTH + 80) / density) + (scroll % 120)
        bump = amp * (0.55 + 0.45 * math.sin(i * 0.9 + t * 0.4))
        bump += amp * 0.35 * math.sin(i * 2.1 - t * 0.25)
        ctx.curve_to(x - 20, y - bump * 0.3, x - 10, y - bump, x, y - bump)
    ctx.line_to(WIDTH + 40, HEIGHT)
    ctx.close_path()
    ctx.fill()


def draw_rolling_hills(ctx: cairo.Context, base_y: float, t: float, scroll: float,
                       layers: List[Tuple[Color, float, float]]) -> None:
    for color, amp, speed in layers:
        ctx.set_source_rgb(*color)
        ctx.move_to(-30, HEIGHT)
        ctx.line_to(-30, base_y)
        for i in range(40):
            x = i * (WIDTH + 60) / 38 - 30
            n = fbm((x + scroll * speed) * 0.004 + t * 0.05)
            y = base_y - amp * (0.35 + 0.65 * n)
            if i == 0:
                ctx.line_to(x, y)
            else:
                ctx.line_to(x, y)
        ctx.line_to(WIDTH + 30, HEIGHT)
        ctx.close_path()
        ctx.fill()


def draw_mountain_ridges(ctx: cairo.Context, t: float, scroll: float,
                         ridges: List[Tuple[Color, float, float, float]]) -> None:
    for color, base_y, amp, speed in ridges:
        ctx.set_source_rgb(*color)
        ctx.move_to(-50, HEIGHT)
        pts = []
        for i in range(24):
            x = -50 + i * ((WIDTH + 100) / 22)
            peak = amp * (0.4 + 0.6 * abs(math.sin(i * 0.7 + scroll * speed * 0.01)))
            peak += amp * 0.25 * fbm(i * 0.4 + scroll * 0.002)
            pts.append((x, base_y - peak))
        ctx.line_to(pts[0][0], pts[0][1])
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            mx = (x0 + x1) / 2
            ctx.curve_to(x0 + 20, y0, mx - 10, min(y0, y1) - 8, x1, y1)
        ctx.line_to(WIDTH + 50, HEIGHT)
        ctx.close_path()
        ctx.fill()


def draw_sunbeams(ctx: cairo.Context, ox: float, oy: float, t: float,
                  beams: int = 9, alpha: float = 0.12) -> None:
    for i in range(beams):
        ang = -1.1 + i * 0.22 + 0.03 * math.sin(t * 0.4 + i)
        spread = 0.06 + 0.02 * math.sin(t * 0.6 + i * 1.3)
        length = HEIGHT * 1.4
        ctx.set_source_rgba(1.0, 0.92, 0.55, alpha * (0.55 + 0.45 * math.sin(t + i)))
        ctx.move_to(ox, oy)
        ctx.line_to(ox + math.cos(ang - spread) * length, oy + math.sin(ang - spread) * length)
        ctx.line_to(ox + math.cos(ang + spread) * length, oy + math.sin(ang + spread) * length)
        ctx.close_path()
        ctx.fill()


def ocean_y(x: float, t: float, base: float, amp: float = 16, scroll: float = 0.0) -> float:
    return (
        base
        + amp * 0.55 * math.sin(x * 0.012 + t * 1.6 + scroll)
        + amp * 0.30 * math.sin(x * 0.028 - t * 2.1)
        + amp * 0.15 * math.sin(x * 0.055 + t * 3.4)
    )


def draw_ocean(ctx: cairo.Context, t: float, base_y: float, deep: Color, mid: Color,
               foam: Color = (0.92, 0.96, 1.0), amp: float = 18, spray: bool = True,
               scroll: float = 0.0) -> None:
    # water body
    g = cairo.LinearGradient(0, base_y - 40, 0, HEIGHT)
    g.add_color_stop_rgb(0.0, *mid)
    g.add_color_stop_rgb(1.0, *deep)
    ctx.set_source(g)
    ctx.move_to(-20, HEIGHT)
    ctx.line_to(-20, ocean_y(-20, t, base_y, amp, scroll))
    for x in range(0, WIDTH + 40, 8):
        ctx.line_to(x, ocean_y(x, t, base_y, amp, scroll))
    ctx.line_to(WIDTH + 20, HEIGHT)
    ctx.close_path()
    ctx.fill()

    # foam crest strokes
    ctx.set_line_width(2.2)
    for pass_i in range(3):
        phase = t * (1.2 + pass_i * 0.3) + pass_i
        ctx.set_source_rgba(foam[0], foam[1], foam[2], 0.35 - pass_i * 0.08)
        ctx.move_to(0, ocean_y(0, t + phase * 0.1, base_y - pass_i * 4, amp * 0.7, scroll))
        for x in range(0, WIDTH + 1, 10):
            ctx.line_to(x, ocean_y(x, t + phase * 0.1, base_y - pass_i * 4, amp * 0.7, scroll))
        ctx.stroke()

    if spray:
        for i in range(40):
            px = (hash01(i * 11) * WIDTH + t * (40 + hash01(i) * 60)) % (WIDTH + 40) - 20
            py = ocean_y(px, t, base_y, amp, scroll) - 4 - hash01(i + 3) * 18
            life = 0.5 + 0.5 * math.sin(t * 5 + i)
            ctx.set_source_rgba(1, 1, 1, 0.15 * life)
            ctx.arc(px, py, 1.2 + hash01(i + 5) * 2.5, 0, 2 * math.pi)
            ctx.fill()


def draw_beach(ctx: cairo.Context, y: float, wet: Color, dry: Color, t: float) -> None:
    g = cairo.LinearGradient(0, y - 30, 0, HEIGHT)
    g.add_color_stop_rgb(0.0, *wet)
    g.add_color_stop_rgb(0.35, *dry)
    g.add_color_stop_rgb(1.0, dry[0] * 0.9, dry[1] * 0.9, dry[2] * 0.9)
    ctx.set_source(g)
    ctx.rectangle(0, y - 20, WIDTH, HEIGHT - y + 20)
    ctx.fill()
    # wet reflection shimmer
    for i in range(18):
        x = i * 70 + 20 * math.sin(t + i)
        ctx.set_source_rgba(0.85, 0.9, 0.95, 0.08 + 0.05 * math.sin(t * 2 + i))
        ctx.rectangle(x, y - 8, 40, 6)
        ctx.fill()


def draw_cliffs(ctx: cairo.Context, t: float, scroll: float,
                stone: Color = (0.35, 0.34, 0.33),
                dark: Color = (0.18, 0.17, 0.16)) -> None:
    # Keep parallax local so walls never swallow the whole frame
    par = (scroll * 0.35) % 160.0

    # far cliff wall (right third)
    ctx.set_source_rgb(*stone)
    ctx.move_to(WIDTH * 0.55 - par * 0.15, 0)
    for i in range(18):
        y = i * (HEIGHT / 16.0)
        x = (
            WIDTH * 0.58
            + 35 * math.sin(i * 0.85 + t * 0.1)
            + 22 * fbm(i * 0.45 + par * 0.02)
            - par * 0.12
        )
        ctx.line_to(x, y)
    ctx.line_to(WIDTH + 10, HEIGHT)
    ctx.line_to(WIDTH + 10, 0)
    ctx.close_path()
    ctx.fill()

    # rock striations
    ctx.set_source_rgba(dark[0], dark[1], dark[2], 0.4)
    ctx.set_line_width(2)
    for i in range(14):
        y = 30 + i * 48 + 6 * math.sin(t * 0.2 + i)
        x0 = WIDTH * 0.6 - par * 0.12
        ctx.move_to(x0, y)
        ctx.curve_to(WIDTH * 0.72, y + 8, WIDTH * 0.85, y - 4, WIDTH, y + 6)
        ctx.stroke()

    # near jagged overhang
    ctx.set_source_rgb(*dark)
    ctx.move_to(WIDTH * 0.72 - par * 0.2, HEIGHT)
    for i in range(12):
        y = HEIGHT - i * (HEIGHT / 11.0)
        x = WIDTH * 0.74 + 22 * math.sin(i * 1.35) - par * 0.2
        ctx.line_to(x, y)
    ctx.line_to(WIDTH + 10, 0)
    ctx.line_to(WIDTH + 10, HEIGHT)
    ctx.close_path()
    ctx.fill()

    # cliff-top scrub
    ctx.set_source_rgb(0.2, 0.28, 0.14)
    for i in range(8):
        sx = WIDTH * 0.62 + i * 40 - par * 0.1
        ctx.arc(sx, 18 + 4 * math.sin(i), 5 + hash01(i) * 4, 0, 2 * math.pi)
        ctx.fill()


def draw_dunes(ctx: cairo.Context, t: float, scroll: float,
               colors: List[Color]) -> None:
    bases = [HEIGHT * 0.55, HEIGHT * 0.68, HEIGHT * 0.82]
    amps = [90, 70, 50]
    for li, (color, base, amp) in enumerate(zip(colors, bases, amps)):
        ctx.set_source_rgb(*color)
        ctx.move_to(-40, HEIGHT)
        for i in range(30):
            x = -40 + i * ((WIDTH + 80) / 28)
            n = fbm((x + scroll * (0.3 + li * 0.2)) * 0.003 + li)
            y = base - amp * n - 12 * math.sin(x * 0.008 + t * 0.3 + li)
            ctx.line_to(x, y)
        ctx.line_to(WIDTH + 40, HEIGHT)
        ctx.close_path()
        ctx.fill()
        # dune crest highlight
        hi = (min(1.0, color[0] * 1.15), min(1.0, color[1] * 1.12), min(1.0, color[2] * 1.08))
        ctx.set_source_rgba(*hi, 0.25)
        ctx.set_line_width(3)
        ctx.move_to(-40, base)
        for i in range(30):
            x = -40 + i * ((WIDTH + 80) / 28)
            n = fbm((x + scroll * (0.3 + li * 0.2)) * 0.003 + li)
            y = base - amp * n - 12 * math.sin(x * 0.008 + t * 0.3 + li)
            ctx.line_to(x, y)
        ctx.stroke()


def draw_cracked_earth(ctx: cairo.Context, t: float, scroll: float,
                       sand: Color = (0.78, 0.70, 0.52),
                       crack: Color = (0.28, 0.22, 0.16)) -> None:
    g = cairo.LinearGradient(0, HEIGHT * 0.45, 0, HEIGHT)
    g.add_color_stop_rgb(0.0, sand[0] * 1.05, sand[1] * 1.02, sand[2] * 0.95)
    g.add_color_stop_rgb(1.0, *sand)
    ctx.set_source(g)
    ctx.rectangle(0, HEIGHT * 0.42, WIDTH, HEIGHT * 0.58)
    ctx.fill()

    ctx.set_source_rgb(*crack)
    ctx.set_line_width(1.4)
    for i in range(55):
        x0 = (hash01(i * 3) * WIDTH + scroll * 0.5) % (WIDTH + 100) - 50
        y0 = HEIGHT * 0.48 + hash01(i * 3 + 1) * HEIGHT * 0.45
        ctx.move_to(x0, y0)
        segs = 3 + int(hash01(i + 8) * 4)
        x, y = x0, y0
        for s in range(segs):
            x += (hash01(i * 11 + s) - 0.5) * 50
            y += 10 + hash01(i * 13 + s) * 28
            ctx.line_to(x, y)
        ctx.stroke()

    # heat shimmer bands
    for i in range(8):
        y = HEIGHT * 0.5 + i * 22 + 4 * math.sin(t * 3 + i)
        ctx.set_source_rgba(1, 0.9, 0.7, 0.04 + 0.02 * math.sin(t * 4 + i))
        ctx.rectangle(0, y, WIDTH, 6)
        ctx.fill()


def draw_canyon(ctx: cairo.Context, t: float, scroll: float,
                wall: Color = (0.55, 0.22, 0.12),
                shadow: Color = (0.25, 0.10, 0.06)) -> None:
    par = (scroll * 0.5) % 220.0
    # left wall
    ctx.set_source_rgb(*wall)
    ctx.move_to(0, 0)
    ctx.line_to(0, HEIGHT)
    for i in range(18):
        y = HEIGHT - i * (HEIGHT / 16)
        x = 90 + 50 * math.sin(i * 0.9 + par * 0.02) + 28 * fbm(i * 0.3)
        ctx.line_to(x, y)
    ctx.line_to(0, 0)
    ctx.close_path()
    ctx.fill()

    # right wall
    ctx.move_to(WIDTH, 0)
    ctx.line_to(WIDTH, HEIGHT)
    for i in range(18):
        y = HEIGHT - i * (HEIGHT / 16)
        x = WIDTH - 100 - 48 * math.sin(i * 1.1 - par * 0.02) - 24 * fbm(i * 0.4 + 2)
        ctx.line_to(x, y)
    ctx.line_to(WIDTH, 0)
    ctx.close_path()
    ctx.fill()

    # shadow interiors
    ctx.set_source_rgb(*shadow)
    ctx.move_to(0, 0)
    for i in range(12):
        y = i * (HEIGHT / 11)
        x = 45 + 22 * math.sin(i + t * 0.2)
        ctx.line_to(x, y)
    ctx.line_to(0, HEIGHT)
    ctx.close_path()
    ctx.fill()

    # spires
    for i, sx in enumerate([170, 230, WIDTH - 210, WIDTH - 150]):
        h = 120 + 40 * math.sin(i + par * 0.01)
        bx = sx + 20 * math.sin(par * 0.02 + i)
        ctx.set_source_rgb(wall[0] * 0.85, wall[1] * 0.85, wall[2] * 0.85)
        ctx.move_to(bx, HEIGHT * 0.55)
        ctx.line_to(bx - 18, HEIGHT * 0.55 - h)
        ctx.line_to(bx + 18, HEIGHT * 0.55 - h * 0.92)
        ctx.close_path()
        ctx.fill()

    # floor
    g = cairo.LinearGradient(0, HEIGHT * 0.75, 0, HEIGHT)
    g.add_color_stop_rgb(0.0, 0.5, 0.3, 0.18)
    g.add_color_stop_rgb(1.0, 0.35, 0.2, 0.12)
    ctx.set_source(g)
    ctx.rectangle(0, HEIGHT * 0.78, WIDTH, HEIGHT * 0.22)
    ctx.fill()
    # shrubs
    ctx.set_source_rgb(0.25, 0.28, 0.12)
    for i in range(10):
        sx = (i * 130 + par) % (WIDTH + 40) - 20
        ctx.arc(sx, HEIGHT * 0.8, 6 + hash01(i) * 5, 0, 2 * math.pi)
        ctx.fill()


def draw_dust_storm(ctx: cairo.Context, t: float, intensity: float = 1.0) -> None:
    for i in range(70):
        x = (hash01(i * 2) * WIDTH + t * (30 + hash01(i) * 120) * intensity) % (WIDTH + 80) - 40
        y = hash01(i * 2 + 1) * HEIGHT
        r = 20 + hash01(i + 4) * 70
        a = (0.04 + 0.06 * hash01(i + 6)) * intensity
        ctx.set_source_rgba(0.55, 0.38, 0.22, a)
        ctx.arc(x, y, r, 0, 2 * math.pi)
        ctx.fill()
    # swirling bands
    for i in range(6):
        ctx.set_source_rgba(0.4, 0.25, 0.12, 0.08 * intensity)
        y = HEIGHT * (0.2 + i * 0.12) + 20 * math.sin(t * 2 + i)
        ctx.move_to(-20, y)
        for x in range(0, WIDTH + 1, 40):
            ctx.line_to(x, y + 25 * math.sin(x * 0.02 + t * 3 + i))
        ctx.set_line_width(40)
        ctx.stroke()


def draw_clouds(ctx: cairo.Context, t: float, scroll: float, puffs: List[Tuple],
                fill: Color, edge: Optional[Color] = None) -> None:
    for i, (bx, by, sx, sy) in enumerate(puffs):
        x = (bx + scroll * (0.15 + 0.05 * (i % 3))) % (WIDTH + 200) - 100
        y = by + 6 * math.sin(t * 0.4 + i)
        if edge:
            ctx.set_source_rgb(*edge)
            for dx, dy, s in [(-sx * 0.4, 0, 0.7), (0, -sy * 0.35, 0.85), (sx * 0.35, 0, 0.65),
                              (-sx * 0.1, sy * 0.2, 0.55), (sx * 0.15, sy * 0.15, 0.5)]:
                ctx.arc(x + dx, y + dy, max(sx, sy) * s * 1.08, 0, 2 * math.pi)
                ctx.fill()
        ctx.set_source_rgb(*fill)
        for dx, dy, s in [(-sx * 0.4, 0, 0.7), (0, -sy * 0.35, 0.85), (sx * 0.35, 0, 0.65),
                          (-sx * 0.1, sy * 0.2, 0.55), (sx * 0.15, sy * 0.15, 0.5)]:
            ctx.arc(x + dx, y + dy, max(sx, sy) * s, 0, 2 * math.pi)
            ctx.fill()


def draw_mandala(ctx: cairo.Context, cx: float, cy: float, t: float, scale: float = 1.0) -> None:
    pulse = 0.92 + 0.08 * math.sin(t * 2.2)
    # outer glow ring
    for ring in range(4):
        r = (90 + ring * 28) * scale * pulse
        ctx.set_source_rgba(1.0, 0.75, 0.25, 0.08 - ring * 0.015)
        ctx.arc(cx, cy, r, 0, 2 * math.pi)
        ctx.set_line_width(10 - ring)
        ctx.stroke()

    petals = 12
    for i in range(petals):
        ang = i * (2 * math.pi / petals) + t * 0.25
        for layer, (rr, a) in enumerate([(120, 0.18), (85, 0.28), (55, 0.4)]):
            px = cx + math.cos(ang) * rr * 0.35 * scale * pulse
            py = cy + math.sin(ang) * rr * 0.35 * scale * pulse
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(ang)
            ctx.scale(1.0, 0.45)
            ctx.set_source_rgba(1.0, 0.7 + layer * 0.08, 0.2, a)
            ctx.arc(0, 0, (42 - layer * 8) * scale, 0, 2 * math.pi)
            ctx.fill()
            ctx.restore()

    # core
    ctx.set_source_rgba(1.0, 0.95, 0.7, 0.85)
    ctx.arc(cx, cy, 22 * scale * pulse, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(1.0, 0.55, 0.2, 0.5)
    ctx.arc(cx, cy, 12 * scale, 0, 2 * math.pi)
    ctx.fill()


def draw_islands(ctx: cairo.Context, t: float, y_base: float) -> None:
    ctx.set_source_rgb(0.08, 0.06, 0.1)
    for i, (cx, w, h) in enumerate([(180, 140, 55), (420, 220, 80), (720, 160, 60), (940, 110, 40)]):
        bob = 2 * math.sin(t * 0.3 + i)
        ctx.move_to(cx - w / 2, y_base + bob)
        ctx.curve_to(cx - w * 0.2, y_base - h + bob, cx + w * 0.15, y_base - h * 1.1 + bob,
                     cx + w / 2, y_base + bob)
        ctx.line_to(cx + w / 2 + 30, y_base + 20 + bob)
        ctx.line_to(cx - w / 2 - 30, y_base + 20 + bob)
        ctx.close_path()
        ctx.fill()


def draw_forest_silhouettes(ctx: cairo.Context, y: float, t: float, scroll: float,
                            color: Color = (0.05, 0.1, 0.08)) -> None:
    ctx.set_source_rgb(*color)
    for i in range(40):
        x = (i * 55 + scroll * 0.4) % (WIDTH + 80) - 40
        h = 80 + 50 * hash01(i + 2)
        draw_pine(ctx, x, y, h, color)


# ==============================================================================
# BIRD RIG — articulated silhouette with feathered wings
# ==============================================================================
class BirdRig:
    def __init__(self, scale: float = 1.0, color: Color = (0.12, 0.12, 0.14),
                 rim: Optional[ColorA] = None):
        self.scale = scale
        self.color = color
        self.rim = rim or (0.85, 0.9, 1.0, 0.35)
        self.wing_phase = 0.0
        self.bank = 0.0
        self.pitch = 0.0
        self.spread = 0.35  # 0 folded .. 1 fully open
        self.breath = 0.0
        self.x = WIDTH * 0.5
        self.y = HEIGHT * 0.35
        self.facing = 1.0  # 1 right, -1 left

    def update(self, mode: str, local_t: float, global_t: float, scene_len: float) -> None:
        u = clamp(local_t / max(scene_len, 0.01))
        # default cruise position
        self.x = WIDTH * 0.48
        self.y = HEIGHT * 0.38
        self.bank = 0.0
        self.pitch = 0.0
        self.facing = 1.0
        flap = 6.0
        self.spread = 0.85

        if mode == "rest":
            self.x, self.y = WIDTH * 0.52, HEIGHT * 0.28
            self.spread = 0.12
            self.breath = 0.5 + 0.5 * math.sin(global_t * 1.4)
            flap = 0.0
            self.wing_phase = 0.0
        elif mode == "wake":
            self.x, self.y = WIDTH * 0.52, HEIGHT * 0.30
            self.spread = smoothstep(0.15, 0.85, u) * 0.95
            self.breath = 1.0
            flap = 2.0 + 4.0 * u
            self.pitch = -0.15 * u
        elif mode == "liftoff":
            self.x = WIDTH * 0.5
            self.y = lerp(HEIGHT * 0.45, HEIGHT * 0.22, smoothstep(0.0, 1.0, u))
            self.spread = 1.0
            flap = 10.0
            self.pitch = -0.55 * (1.0 - u * 0.4)
        elif mode == "cruise":
            self.x = WIDTH * (0.4 + 0.15 * math.sin(global_t * 0.4))
            self.y = HEIGHT * 0.34 + 8 * math.sin(global_t * 1.2)
            flap = 5.5
        elif mode == "climb":
            self.x = WIDTH * 0.45
            self.y = lerp(HEIGHT * 0.42, HEIGHT * 0.22, u)
            self.pitch = -0.4
            self.bank = 0.25
            flap = 7.0
            self.spread = 0.9
        elif mode == "glide":
            self.x = WIDTH * (0.35 + 0.35 * u)
            self.y = HEIGHT * 0.36 + 6 * math.sin(global_t)
            flap = 1.2
            self.spread = 1.0
            self.pitch = -0.05
        elif mode == "swoop":
            self.x = WIDTH * (0.3 + 0.45 * u)
            self.y = HEIGHT * (0.22 + 0.45 * smoothstep(0.0, 0.7, u))
            self.pitch = 0.55 * math.sin(u * math.pi)
            self.bank = -0.35
            flap = 8.0
        elif mode == "bank_glide":
            self.x = WIDTH * 0.5
            self.y = HEIGHT * 0.4 + 10 * math.sin(global_t * 0.8)
            self.bank = 0.4 * math.sin(global_t * 1.1)
            flap = 0.8
            self.spread = 1.0
        elif mode == "skim":
            self.x = WIDTH * (0.35 + 0.3 * math.sin(global_t * 0.5))
            self.y = HEIGHT * 0.58 + 12 * math.sin(global_t * 2.0)
            flap = 3.5
            self.spread = 0.95
            self.pitch = 0.1
        elif mode == "turbulence":
            self.x = WIDTH * 0.48 + 25 * math.sin(global_t * 7)
            self.y = HEIGHT * 0.36 + 18 * math.sin(global_t * 9.5)
            self.bank = 0.5 * math.sin(global_t * 6)
            self.pitch = 0.2 * math.sin(global_t * 5)
            flap = 9.0
        elif mode == "fast_low":
            self.x = WIDTH * (0.25 + 0.55 * u)
            self.y = HEIGHT * 0.55
            flap = 11.0
            self.pitch = 0.08
        elif mode == "weave":
            self.x = WIDTH * 0.5 + 90 * math.sin(global_t * 2.4)
            self.y = HEIGHT * 0.4 + 40 * math.sin(global_t * 1.7)
            self.bank = 0.7 * math.cos(global_t * 2.4)
            flap = 9.5
        elif mode == "struggle":
            self.x = WIDTH * 0.42 + 10 * math.sin(global_t * 8)
            self.y = HEIGHT * 0.4 + 15 * math.sin(global_t * 10)
            self.pitch = -0.2 + 0.15 * math.sin(global_t * 6)
            flap = 12.0
            self.spread = 0.75
        elif mode == "burst_climb":
            self.x = WIDTH * 0.5
            self.y = lerp(HEIGHT * 0.55, HEIGHT * 0.2, smoothstep(0.0, 1.0, u))
            self.pitch = -0.7
            flap = 11.0
        elif mode == "long_glide":
            self.x = WIDTH * (0.3 + 0.4 * u)
            self.y = lerp(HEIGHT * 0.25, HEIGHT * 0.5, u)
            flap = 0.6
            self.spread = 1.0
            self.pitch = 0.15
        elif mode == "mirror":
            self.x = WIDTH * (0.35 + 0.3 * u)
            self.y = HEIGHT * 0.32
            flap = 4.0
            self.spread = 0.95
        elif mode == "diagonal":
            self.x = lerp(WIDTH * 0.1, WIDTH * 0.85, u)
            self.y = lerp(HEIGHT * 0.65, HEIGHT * 0.2, u)
            self.pitch = -0.45
            self.bank = 0.2
            flap = 6.0
        elif mode == "slow_cruise":
            self.x = WIDTH * (0.4 + 0.2 * u)
            self.y = HEIGHT * 0.35
            flap = 3.0
            self.spread = 0.9
        elif mode == "loop":
            ang = -math.pi / 2 + u * 2 * math.pi
            radius = 130
            self.x = WIDTH * 0.5 + math.cos(ang) * radius
            self.y = HEIGHT * 0.42 + math.sin(ang) * radius * 0.7
            self.pitch = ang + math.pi / 2
            flap = 5.0
            self.spread = 1.0
        elif mode == "horizon":
            self.x = WIDTH * (0.25 + 0.5 * u)
            self.y = HEIGHT * 0.28
            flap = 4.5
        elif mode == "cloud_cut":
            self.x = WIDTH * (0.3 + 0.4 * u)
            self.y = HEIGHT * 0.4 + 20 * math.sin(global_t * 2)
            flap = 7.0
            self.bank = 0.2 * math.sin(global_t)
        elif mode in ("duo", "duo_descend"):
            self.x = WIDTH * 0.42
            self.y = HEIGHT * (0.32 if mode == "duo" else lerp(0.32, 0.55, u))
            flap = 4.0 if mode == "duo" else 3.0
            self.spread = 0.9
        elif mode == "land":
            self.x = lerp(WIDTH * 0.4, WIDTH * 0.5, u)
            self.y = lerp(HEIGHT * 0.35, HEIGHT * 0.30, u)
            self.spread = lerp(0.9, 0.12, smoothstep(0.4, 0.95, u))
            flap = lerp(4.0, 0.0, u)
            self.breath = 0.5 + 0.5 * math.sin(global_t * 1.4) * u
        else:
            flap = 5.0

        if flap > 0:
            self.wing_phase += flap * (1.0 / FPS) * 2 * math.pi
        self.breath = self.breath or (0.5 + 0.5 * math.sin(global_t * 1.5))

    def draw(self, ctx: cairo.Context, mirror: bool = False, companion_offset: float = 0.0) -> None:
        ctx.save()
        x = self.x + companion_offset
        y = self.y
        ctx.translate(x, y)
        ctx.rotate(self.pitch)
        y_scale = -self.scale if mirror else self.scale
        ctx.scale(self.facing * self.scale, y_scale)
        ctx.rotate(self.bank * 0.35)
        if self.spread < 0.28:
            self._draw_perched(ctx)
        else:
            self._draw_body(ctx)
        ctx.restore()

    def _draw_perched(self, ctx: cairo.Context) -> None:
        """Side-profile resting bird with folded wings and subtle breath."""
        breath = 1.0 + 0.05 * self.breath
        # soft nest/glow hint
        ctx.set_source_rgba(self.rim[0], self.rim[1], self.rim[2], 0.12)
        ctx.arc(0, 6, 22, 0, 2 * math.pi)
        ctx.fill()

        ctx.set_source_rgb(*self.color)
        # body
        ctx.save()
        ctx.scale(1.45 * breath, 0.95)
        ctx.arc(0, 2, 11, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        # folded wing overlay
        ctx.save()
        ctx.translate(-2, 0)
        ctx.scale(1.1, 0.7)
        ctx.set_source_rgb(self.color[0] * 0.85, self.color[1] * 0.85, self.color[2] * 0.85)
        ctx.arc(0, 1, 10, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        # tail
        ctx.set_source_rgb(*self.color)
        ctx.move_to(-12, 2)
        ctx.curve_to(-22, -2, -30, 0, -34, 4)
        ctx.curve_to(-26, 8, -18, 8, -12, 5)
        ctx.close_path()
        ctx.fill()
        # head
        ctx.arc(12, -4, 6.5, 0, 2 * math.pi)
        ctx.fill()
        # beak
        ctx.move_to(17, -4)
        ctx.line_to(25, -2.5)
        ctx.line_to(17, -1)
        ctx.close_path()
        ctx.fill()
        # eye
        ctx.set_source_rgba(0.95, 0.92, 0.8, 0.9)
        ctx.arc(13.5, -5.5, 1.2, 0, 2 * math.pi)
        ctx.fill()
        # feet on branch
        ctx.set_source_rgb(*self.color)
        ctx.set_line_width(1.6)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(-2, 12)
        ctx.line_to(-4, 18)
        ctx.move_to(2, 12)
        ctx.line_to(4, 18)
        ctx.stroke()

    def _draw_body(self, ctx: cairo.Context) -> None:
        wing = math.sin(self.wing_phase)
        up = wing * (0.55 + 0.25 * self.spread) - (1.0 - self.spread) * 0.9
        breath_scale = 1.0 + 0.03 * self.breath

        # soft rim light
        rg = cairo.RadialGradient(0, 0, 6, 0, 0, 40)
        rg.add_color_stop_rgba(0.0, self.rim[0], self.rim[1], self.rim[2], self.rim[3] * 0.55)
        rg.add_color_stop_rgba(1.0, self.rim[0], self.rim[1], self.rim[2], 0.0)
        ctx.set_source(rg)
        ctx.arc(0, 0, 40, 0, 2 * math.pi)
        ctx.fill()

        ctx.set_source_rgb(*self.color)

        # far wing under body
        self._draw_wing(ctx, side=-1.0, up=up * 0.9, shade=0.75)

        # tail fan
        ctx.save()
        ctx.translate(-20, 3)
        for i, ang in enumerate((-0.25, 0.0, 0.25)):
            ctx.save()
            ctx.rotate(ang)
            ctx.move_to(0, 0)
            ctx.curve_to(-14, -5, -28, -2, -36, 3)
            ctx.curve_to(-28, 7, -14, 8, 0, 3)
            ctx.close_path()
            s = 0.9 + i * 0.04
            ctx.set_source_rgb(self.color[0] * s, self.color[1] * s, self.color[2] * s)
            ctx.fill()
            ctx.restore()
        ctx.restore()

        # torso with slight belly highlight
        ctx.set_source_rgb(*self.color)
        ctx.save()
        ctx.scale(1.4 * breath_scale, 0.72 * breath_scale)
        ctx.arc(0, 0, 15, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        ctx.set_source_rgba(0.35, 0.35, 0.38, 0.25)
        ctx.save()
        ctx.scale(1.1, 0.5)
        ctx.arc(2, 4, 10, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # neck + head
        ctx.set_source_rgb(*self.color)
        ctx.arc(14, -2, 5, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(22, -5, 7.2, 0, 2 * math.pi)
        ctx.fill()
        # beak
        ctx.move_to(28, -5)
        ctx.line_to(38, -3)
        ctx.line_to(28, -1)
        ctx.close_path()
        ctx.fill()
        # eye
        ctx.set_source_rgba(0.95, 0.95, 0.9, 0.9)
        ctx.arc(24, -7, 1.4, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.05, 0.05, 0.06)
        ctx.arc(24.3, -7, 0.6, 0, 2 * math.pi)
        ctx.fill()

        # near wing
        ctx.set_source_rgb(*self.color)
        self._draw_wing(ctx, side=1.0, up=up, shade=1.0)

    def _draw_wing(self, ctx: cairo.Context, side: float, up: float, shade: float = 1.0) -> None:
        ctx.save()
        ctx.translate(2, -2)
        fold = (1.0 - self.spread) * 0.85
        ctx.rotate(side * (-0.12 + up * 1.05) - side * fold)
        flap_bend = up * 0.6
        tip = 44 * max(self.spread, 0.2)
        c = (self.color[0] * shade, self.color[1] * shade, self.color[2] * shade)
        ctx.set_source_rgb(*c)

        # secondary coverts
        ctx.move_to(0, 0)
        ctx.curve_to(
            8 * side, -10 - flap_bend * 18,
            18 * side, -16 - flap_bend * 24,
            tip * 0.55 * side, -6 - flap_bend * 8,
        )
        ctx.curve_to(16 * side, 8, 6 * side, 10, 0, 5)
        ctx.close_path()
        ctx.fill()

        # primary feathers as separate tapered blades
        base_x = tip * 0.4 * side
        base_y = -4 - flap_bend * 6
        for i in range(6):
            ang = side * (0.05 + i * 0.07)
            length = (18 + i * 3.5) * max(self.spread, 0.25)
            spread_y = i * 3.8 - 4
            ctx.save()
            ctx.translate(base_x, base_y + spread_y * 0.3)
            ctx.rotate(ang + side * flap_bend * 0.15)
            ctx.move_to(0, 0)
            ctx.curve_to(
                length * 0.4 * side, -2 - flap_bend * 2,
                length * 0.85 * side, spread_y * 0.2,
                length * side, spread_y * 0.35 + 2,
            )
            ctx.curve_to(
                length * 0.7 * side, spread_y * 0.35 + 5,
                length * 0.3 * side, 4,
                0, 3,
            )
            ctx.close_path()
            feather_shade = shade * (0.85 + 0.03 * i)
            ctx.set_source_rgb(
                self.color[0] * feather_shade,
                self.color[1] * feather_shade,
                self.color[2] * feather_shade,
            )
            ctx.fill()
            ctx.restore()
        ctx.restore()


# ==============================================================================
# SCENE RENDERER
# ==============================================================================
class ScenePainter:
    def __init__(self):
        self.canvas = CairoCanvas()
        self.bird = BirdRig(scale=1.15, color=(0.1, 0.1, 0.12), rim=(0.9, 0.95, 1.0, 0.4))
        self.bird2 = BirdRig(scale=1.05, color=(0.14, 0.14, 0.16), rim=(0.95, 0.9, 0.85, 0.35))

    def render_scene(self, scene_id: str, mode: str, local_t: float, global_t: float,
                     scene_len: float) -> pygame.Surface:
        ctx = self.canvas.ctx
        self.canvas.clear()
        scroll = global_t * 40

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
        drawers.get(scene_id, self._predawn)(ctx, local_t, global_t, scroll)

        # bird(s)
        self.bird.update(mode, local_t, global_t, scene_len)
        duo = mode in ("duo", "duo_descend", "land")
        if scene_id == "tidal_mirror":
            water_y = HEIGHT * 0.55
            self.bird.draw(ctx)
            # mirrored bird under the waterline
            ctx.save()
            ctx.rectangle(0, water_y, WIDTH, HEIGHT - water_y)
            ctx.clip()
            ctx.push_group()
            ctx.translate(0, 2 * water_y)
            ctx.scale(1, -1)
            self.bird.draw(ctx)
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(0.38)
            ctx.restore()
        elif duo:
            self.bird.draw(ctx)
            self.bird2.wing_phase = self.bird.wing_phase + 0.35
            self.bird2.spread = self.bird.spread
            self.bird2.pitch = self.bird.pitch
            self.bird2.bank = -self.bird.bank * 0.4
            self.bird2.x = self.bird.x + 72
            self.bird2.y = self.bird.y + 10
            self.bird2.scale = 1.05
            self.bird2.draw(ctx)
        else:
            self.bird.draw(ctx)

        # vapor trail in cloud_cut
        if mode == "cloud_cut":
            ctx.set_source_rgba(1, 1, 1, 0.15)
            for i in range(8):
                px = self.bird.x - 20 - i * 14
                py = self.bird.y + 4 * math.sin(global_t * 3 + i)
                ctx.arc(px, py, 3 + i * 0.4, 0, 2 * math.pi)
                ctx.fill()

        return self.canvas.to_pygame()

    # --- individual scenes ---
    def _predawn(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.03, 0.04, 0.1), (0.07, 0.09, 0.2), (0.1, 0.12, 0.22), 0.6)
        draw_stars(ctx, t, 120, alpha=0.95)
        draw_moon(ctx, WIDTH * 0.78, HEIGHT * 0.18, 28)
        # atmospheric perspective forest layers
        draw_forest_silhouettes(ctx, HEIGHT * 0.7, t, scroll * 0.15, (0.06, 0.08, 0.14))
        draw_forest_silhouettes(ctx, HEIGHT * 0.78, t, scroll * 0.25, (0.03, 0.05, 0.09))
        # ground with soft undulation
        ctx.set_source_rgb(0.02, 0.03, 0.06)
        ctx.move_to(0, HEIGHT)
        ctx.line_to(0, HEIGHT * 0.88)
        for i in range(20):
            x = i * (WIDTH / 18)
            ctx.line_to(x, HEIGHT * 0.88 + 8 * math.sin(i * 0.7))
        ctx.line_to(WIDTH, HEIGHT)
        ctx.close_path()
        ctx.fill()
        draw_ancient_tree(ctx, WIDTH * 0.55, HEIGHT * 0.92, 1.4, t, sway=0.15)
        # ground mist
        for i in range(6):
            y = HEIGHT * 0.82 + i * 14
            ctx.set_source_rgba(0.12, 0.14, 0.22, 0.08)
            ctx.rectangle(0, y, WIDTH, 16)
            ctx.fill()

    def _dawn(self, ctx, local_t, t, scroll):
        u = clamp(local_t / 8.0)
        top = lerp_color((0.06, 0.08, 0.18), (0.35, 0.45, 0.7), u)
        mid = lerp_color((0.12, 0.14, 0.28), (0.75, 0.55, 0.35), u)
        bot = lerp_color((0.08, 0.1, 0.16), (0.25, 0.22, 0.2), u)
        paint_sky(ctx, WIDTH, HEIGHT, top, mid, bot, 0.5)
        draw_stars(ctx, t, 60, alpha=1.0 - u)
        draw_sun(ctx, WIDTH * 0.15, HEIGHT * (0.55 - 0.25 * u), 18 + 10 * u,
                 core=(1.0, 0.85, 0.55), glow=(1.0, 0.55, 0.25, 0.2))
        sway = 0.6 + 0.8 * u
        draw_canopy_layer(ctx, HEIGHT * 0.55, t, scroll * 0.3, (0.08, 0.12, 0.1), 22, 30)
        draw_canopy_layer(ctx, HEIGHT * 0.68, t, scroll * 0.5, (0.05, 0.09, 0.07), 26, 40)
        draw_ancient_tree(ctx, WIDTH * 0.55, HEIGHT * 0.95, 1.3, t, sway=sway)

    def _liftoff(self, ctx, local_t, t, scroll):
        u = clamp(local_t / 6.5)
        paint_sky(ctx, WIDTH, HEIGHT,
                  (0.45, 0.62, 0.85), (0.55, 0.7, 0.88), (0.7, 0.8, 0.9), 0.55)
        # silver rim atmosphere
        ctx.set_source_rgba(0.9, 0.95, 1.0, 0.12)
        ctx.rectangle(0, 0, WIDTH, HEIGHT * 0.35)
        ctx.fill()
        # ground dropping away
        gy = HEIGHT * (0.75 + 0.4 * u)
        draw_canopy_layer(ctx, gy, t, scroll, (0.1, 0.22, 0.12), 30, 50)
        draw_canopy_layer(ctx, gy + 60, t, scroll * 1.2, (0.06, 0.14, 0.08), 24, 35)
        if u < 0.5:
            draw_ancient_tree(ctx, WIDTH * 0.5, gy + 80, 1.0 - u, t, sway=0.5)

    def _emerald(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.45, 0.7, 0.92), (0.55, 0.78, 0.9), (0.65, 0.82, 0.88))
        draw_canopy_layer(ctx, HEIGHT * 0.5, t, scroll * 1.5, (0.12, 0.35, 0.18), 32, 45)
        draw_canopy_layer(ctx, HEIGHT * 0.62, t, scroll * 2.2, (0.08, 0.28, 0.14), 28, 55)
        draw_canopy_layer(ctx, HEIGHT * 0.75, t, scroll * 3.0, (0.05, 0.2, 0.1), 24, 40)
        # mist in valleys
        ctx.set_source_rgba(0.7, 0.85, 0.8, 0.12)
        for i in range(5):
            y = HEIGHT * 0.55 + i * 30 + 8 * math.sin(t + i)
            ctx.rectangle(0, y, WIDTH, 18)
            ctx.fill()

    def _alpine(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.55, 0.7, 0.88), (0.7, 0.78, 0.88), (0.75, 0.8, 0.85))
        draw_mountain_ridges(ctx, t, scroll, [
            ((0.45, 0.5, 0.58), HEIGHT * 0.45, 140, 0.3),
            ((0.32, 0.36, 0.42), HEIGHT * 0.55, 160, 0.6),
            ((0.2, 0.24, 0.28), HEIGHT * 0.68, 120, 1.0),
        ])
        # pines on ridges
        for i in range(18):
            x = (i * 70 + scroll * 0.5) % (WIDTH + 60) - 30
            draw_pine(ctx, x, HEIGHT * 0.62 + 20 * math.sin(i), 50 + 30 * hash01(i),
                      (0.12, 0.25, 0.16))
        # wind currents
        ctx.set_line_width(1.5)
        for i in range(8):
            ctx.set_source_rgba(0.85, 0.9, 0.95, 0.15)
            y = 120 + i * 40
            ctx.move_to(0, y)
            for x in range(0, WIDTH, 20):
                ctx.line_to(x, y + 10 * math.sin(x * 0.03 + t * 2 + i))
            ctx.stroke()

    def _valley(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.4, 0.65, 0.9), (0.72, 0.82, 0.92), (0.55, 0.75, 0.5), 0.55)
        draw_sun(ctx, WIDTH * 0.72, HEIGHT * 0.18, 28, (1.0, 0.95, 0.7), (1.0, 0.8, 0.3, 0.25))
        draw_sunbeams(ctx, WIDTH * 0.72, HEIGHT * 0.18, t, 10, 0.12)
        draw_clouds(ctx, t, scroll * 0.2,
                    [(100, 100, 80, 40), (400, 80, 100, 45), (750, 120, 90, 38)],
                    (0.85, 0.88, 0.92), (0.95, 0.9, 0.75))
        draw_rolling_hills(ctx, HEIGHT * 0.58, t, scroll, [
            ((0.32, 0.52, 0.28), 45, 0.35),
            ((0.22, 0.42, 0.2), 65, 0.7),
            ((0.15, 0.32, 0.14), 40, 1.1),
        ])
        ctx.set_line_width(1.2)
        for i in range(40):
            x = (i * 40 + scroll * 0.8) % (WIDTH + 40) - 20
            y = HEIGHT * 0.68 + 30 * fbm(i * 0.3) + 8 * math.sin(t + i)
            ctx.set_source_rgba(0.25, 0.45, 0.2, 0.35)
            ctx.move_to(x, y)
            ctx.line_to(x + 2, y - 6 - hash01(i) * 5)
            ctx.stroke()
        ctx.set_source_rgb(0.1, 0.22, 0.1)
        for i in range(16):
            x = (i * 90 + scroll * 0.5) % (WIDTH + 60) - 30
            ctx.arc(x, HEIGHT * 0.62 + 10 * math.sin(i), 4 + hash01(i) * 5, 0, 2 * math.pi)
            ctx.fill()

    def _cliffs(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.45, 0.7, 0.92), (0.62, 0.8, 0.9), (0.78, 0.84, 0.86))
        draw_ocean(ctx, t, HEIGHT * 0.7, (0.1, 0.32, 0.5), (0.4, 0.7, 0.8), amp=14, spray=True)
        draw_beach(ctx, HEIGHT * 0.84, (0.62, 0.55, 0.42), (0.84, 0.74, 0.56), t)
        ctx.set_source_rgba(0.75, 0.85, 0.9, 0.18)
        ctx.rectangle(0, HEIGHT * 0.55, WIDTH * 0.55, 80)
        ctx.fill()
        draw_cliffs(ctx, t, scroll)

    def _shore(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.55, 0.75, 0.9), (0.7, 0.82, 0.88), (0.8, 0.85, 0.82))
        ctx.set_source_rgba(0.85, 0.9, 0.92, 0.2)
        ctx.paint()
        draw_ocean(ctx, t, HEIGHT * 0.52, (0.2, 0.55, 0.65), (0.45, 0.75, 0.78), amp=10)
        draw_beach(ctx, HEIGHT * 0.62, (0.55, 0.6, 0.58), (0.78, 0.7, 0.55), t)
        ctx.set_source_rgba(0.6, 0.75, 0.85, 0.15)
        ctx.rectangle(0, HEIGHT * 0.58, WIDTH, 30)
        ctx.fill()

    def _ocean(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.35, 0.58, 0.82), (0.5, 0.72, 0.9), (0.4, 0.62, 0.82), 0.45)
        ctx.set_source_rgba(0.85, 0.9, 0.95, 0.15)
        ctx.rectangle(0, HEIGHT * 0.35, WIDTH, 50)
        ctx.fill()
        draw_ocean(ctx, t, HEIGHT * 0.48, (0.04, 0.18, 0.38), (0.18, 0.45, 0.68),
                   amp=30, spray=True, scroll=scroll * 0.05)
        for i in range(6):
            y = HEIGHT * 0.5 + i * 32
            ctx.set_source_rgba(0.9, 0.95, 1.0, 0.18)
            ctx.set_line_width(2.5)
            ctx.move_to(0, y)
            for x in range(0, WIDTH, 10):
                ctx.line_to(x, ocean_y(x, t + i * 0.2, y, 16, scroll * 0.05))
            ctx.stroke()

    def _dunes(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.75, 0.55, 0.35), (0.85, 0.55, 0.3), (0.7, 0.4, 0.22))
        draw_dunes(ctx, t, scroll * 1.5, [
            (0.72, 0.38, 0.22),
            (0.82, 0.48, 0.25),
            (0.9, 0.55, 0.28),
        ])
        # dust wisps
        draw_dust_storm(ctx, t, 0.35)

    def _salt(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.7, 0.6, 0.4), (0.85, 0.7, 0.45), (0.9, 0.78, 0.55))
        draw_cracked_earth(ctx, t, scroll * 3.5)
        # distant horizon haze
        ctx.set_source_rgba(0.95, 0.85, 0.6, 0.25)
        ctx.rectangle(0, HEIGHT * 0.35, WIDTH, 80)
        ctx.fill()

    def _canyon(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.55, 0.7, 0.9), (0.9, 0.65, 0.35), (0.7, 0.4, 0.2), 0.45)
        draw_sun(ctx, WIDTH * 0.5, HEIGHT * 0.15, 22, (1.0, 0.95, 0.7), (1.0, 0.7, 0.2, 0.3))
        draw_canyon(ctx, t, scroll * 2.0)

    def _dust(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.35, 0.25, 0.15), (0.45, 0.3, 0.18), (0.3, 0.2, 0.12))
        draw_dunes(ctx, t, scroll, [(0.4, 0.25, 0.15), (0.5, 0.32, 0.18), (0.55, 0.35, 0.2)])
        draw_dust_storm(ctx, t, 1.2)
        # visibility fog
        ctx.set_source_rgba(0.4, 0.28, 0.15, 0.35)
        ctx.paint()

    def _breach(self, ctx, local_t, t, scroll):
        u = clamp(local_t / 7.5)
        top = lerp_color((0.4, 0.28, 0.15), (0.4, 0.7, 0.9), u)
        mid = lerp_color((0.45, 0.3, 0.18), (0.55, 0.8, 0.85), u)
        bot = lerp_color((0.3, 0.2, 0.12), (0.15, 0.55, 0.65), u)
        paint_sky(ctx, WIDTH, HEIGHT, top, mid, bot)
        draw_ocean(ctx, t, HEIGHT * 0.55, (0.05, 0.35, 0.5), (0.2, 0.7, 0.75), amp=30, spray=True)
        if u < 0.7:
            draw_dust_storm(ctx, t, 1.0 - u)
        draw_sun(ctx, WIDTH * 0.8, HEIGHT * 0.2, 20 + 15 * u)

    def _swells(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.25, 0.2, 0.4), (0.45, 0.35, 0.6), (0.15, 0.2, 0.4), 0.5)
        draw_ocean(ctx, t, HEIGHT * 0.5, (0.05, 0.1, 0.3), (0.15, 0.25, 0.5),
                   foam=(0.7, 0.75, 0.9), amp=35, spray=False)
        # evening glow on horizon
        ctx.set_source_rgba(0.6, 0.4, 0.7, 0.15)
        ctx.rectangle(0, HEIGHT * 0.35, WIDTH, 60)
        ctx.fill()

    def _mirror(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.25, 0.18, 0.35), (0.45, 0.3, 0.5), (0.55, 0.4, 0.55), 0.55)
        draw_stars(ctx, t, 40, alpha=0.5)
        # mirror water
        water_y = HEIGHT * 0.55
        g = cairo.LinearGradient(0, water_y, 0, HEIGHT)
        g.add_color_stop_rgb(0.0, 0.35, 0.25, 0.45)
        g.add_color_stop_rgb(1.0, 0.15, 0.12, 0.25)
        ctx.set_source(g)
        ctx.rectangle(0, water_y, WIDTH, HEIGHT - water_y)
        ctx.fill()
        # sky reflection tint
        ctx.set_source_rgba(0.45, 0.3, 0.5, 0.35)
        ctx.rectangle(0, water_y, WIDTH, HEIGHT * 0.2)
        ctx.fill()
        # soft ripple lines
        ctx.set_source_rgba(0.8, 0.7, 0.9, 0.08)
        for i in range(10):
            y = water_y + 10 + i * 18
            ctx.move_to(0, y)
            for x in range(0, WIDTH, 16):
                ctx.line_to(x, y + 2 * math.sin(x * 0.04 + t + i))
            ctx.stroke()

    def _deep(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.2, 0.15, 0.35), (0.55, 0.35, 0.4), (0.1, 0.12, 0.3), 0.45)
        draw_ocean(ctx, t, HEIGHT * 0.4, (0.05, 0.08, 0.25), (0.12, 0.18, 0.4), amp=45, spray=True)

    def _islands(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.35, 0.2, 0.35), (0.9, 0.4, 0.2), (0.85, 0.25, 0.15), 0.5)
        draw_sun(ctx, WIDTH * 0.7, HEIGHT * 0.42, 40, (1.0, 0.85, 0.4), (1.0, 0.4, 0.15, 0.35))
        draw_ocean(ctx, t, HEIGHT * 0.55, (0.15, 0.12, 0.25), (0.4, 0.25, 0.3), amp=12, spray=False)
        draw_islands(ctx, t, HEIGHT * 0.55)

    def _mandala(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.35, 0.15, 0.35), (0.7, 0.3, 0.35), (0.9, 0.45, 0.2), 0.5)
        draw_mandala(ctx, WIDTH * 0.5, HEIGHT * 0.42, t, 1.15)
        # ambient particles
        for i in range(30):
            ang = t * 0.5 + i * 0.5
            r = 160 + 40 * math.sin(t + i)
            x = WIDTH * 0.5 + math.cos(ang) * r
            y = HEIGHT * 0.42 + math.sin(ang) * r * 0.7
            ctx.set_source_rgba(1.0, 0.85, 0.4, 0.25)
            ctx.arc(x, y, 2, 0, 2 * math.pi)
            ctx.fill()

    def _twilight_alps(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.2, 0.1, 0.3), (0.5, 0.2, 0.35), (0.7, 0.35, 0.2), 0.55)
        draw_mountain_ridges(ctx, t, scroll, [
            ((0.25, 0.12, 0.28), HEIGHT * 0.4, 130, 0.2),
            ((0.18, 0.08, 0.2), HEIGHT * 0.52, 150, 0.4),
            ((0.1, 0.05, 0.12), HEIGHT * 0.65, 110, 0.7),
        ])
        # rim light on peaks
        ctx.set_source_rgba(1.0, 0.5, 0.2, 0.15)
        ctx.set_line_width(3)
        ctx.move_to(-20, HEIGHT * 0.4)
        for i in range(20):
            x = i * (WIDTH / 18)
            ctx.line_to(x, HEIGHT * 0.4 - 80 * abs(math.sin(i * 0.7)))
        ctx.stroke()

    def _sunset_clouds(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.25, 0.15, 0.35), (0.7, 0.4, 0.45), (0.9, 0.55, 0.35), 0.5)
        draw_clouds(ctx, t, scroll * 0.8,
                    [(80, 200, 110, 50), (320, 260, 140, 60), (560, 180, 120, 55),
                     (780, 240, 130, 58), (200, 360, 100, 45), (650, 380, 150, 65)],
                    (0.55, 0.35, 0.4), (0.95, 0.65, 0.45))
        draw_clouds(ctx, t, scroll * 1.2,
                    [(150, 300, 90, 40), (500, 320, 100, 42), (900, 280, 95, 38)],
                    (0.35, 0.25, 0.35), (0.9, 0.55, 0.4))

    def _sanctuary(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.25, 0.15, 0.35), (0.55, 0.3, 0.4), (0.85, 0.55, 0.4), 0.55)
        draw_rolling_hills(ctx, HEIGHT * 0.7, t, scroll, [
            ((0.2, 0.15, 0.25), 40, 0.3),
            ((0.12, 0.1, 0.16), 55, 0.6),
        ])
        # silver atmosphere
        ctx.set_source_rgba(0.85, 0.9, 1.0, 0.08)
        ctx.paint()

    def _twilight_forest(self, ctx, local_t, t, scroll):
        paint_sky(ctx, WIDTH, HEIGHT, (0.2, 0.15, 0.3), (0.4, 0.3, 0.45), (0.15, 0.18, 0.2), 0.5)
        draw_forest_silhouettes(ctx, HEIGHT * 0.75, t, scroll * 0.8, (0.04, 0.08, 0.06))
        draw_canopy_layer(ctx, HEIGHT * 0.65, t, scroll, (0.06, 0.1, 0.08), 20, 35)
        ctx.set_source_rgba(0.5, 0.4, 0.6, 0.12)
        ctx.rectangle(0, HEIGHT * 0.5, WIDTH, 80)
        ctx.fill()

    def _roost_return(self, ctx, local_t, t, scroll):
        u = clamp(local_t / 5.0)
        top = lerp_color((0.15, 0.12, 0.28), (0.02, 0.03, 0.08), u)
        mid = lerp_color((0.2, 0.15, 0.3), (0.04, 0.05, 0.1), u)
        bot = lerp_color((0.1, 0.1, 0.16), (0.02, 0.02, 0.05), u)
        paint_sky(ctx, WIDTH, HEIGHT, top, mid, bot)
        draw_stars(ctx, t, int(40 + 80 * u), alpha=0.4 + 0.6 * u)
        draw_moon(ctx, WIDTH * 0.8, HEIGHT * 0.2, 24)
        draw_forest_silhouettes(ctx, HEIGHT * 0.78, t, 0, (0.02, 0.04, 0.05))
        draw_ancient_tree(ctx, WIDTH * 0.52, HEIGHT * 0.95, 1.4, t, sway=0.15)
        # soft glow on roost branch
        ctx.set_source_rgba(0.7, 0.8, 1.0, 0.08)
        ctx.arc(WIDTH * 0.52, HEIGHT * 0.32, 40, 0, 2 * math.pi)
        ctx.fill()


# ==============================================================================
# TIMELINE HELPERS
# ==============================================================================
def scene_at(t: float):
    t = clamp(t, 0.0, SONG_DURATION - 0.001)
    for i, (start, end, sid, mode, label) in enumerate(SCENES):
        if start <= t < end or (i == len(SCENES) - 1 and t <= end):
            return i, start, end, sid, mode, label
    return len(SCENES) - 1, *SCENES[-1]


def crossfade_weight(t: float) -> Tuple[int, int, float]:
    """Return (scene_index_a, scene_index_b, blend_to_b)."""
    idx, start, end, *_ = scene_at(t)
    remaining = end - t
    if remaining < CROSSFADE and idx < len(SCENES) - 1:
        blend = 1.0 - remaining / CROSSFADE
        return idx, idx + 1, smoothstep(0.0, 1.0, blend)
    return idx, idx, 0.0


# ==============================================================================
# MAIN
# ==============================================================================
def blend_frames(dst: pygame.Surface, a: pygame.Surface, b: pygame.Surface, t: float) -> None:
    """Alpha-blend frame b over a onto dst (t=0 → a, t=1 → b)."""
    t = clamp(t)
    if t <= 0.001:
        dst.blit(a, (0, 0))
        return
    if t >= 0.999:
        dst.blit(b, (0, 0))
        return
    # per-surface alpha blit
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
    pygame.display.set_caption("Free as a Bird")
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
        print(f"[AUDIO] Missing {AUDIO_PATH.name} — running silent with timeline clock.")

    recorder = None
    if export_mode:
        recorder = FfmpegRecorder(
            args.output,
            audio_path=AUDIO_PATH if AUDIO_PATH.is_file() else None,
        )
        print(f"Exporting to {args.output} ...")

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
                        if paused:
                            pygame.mixer.music.pause()
                        else:
                            pygame.mixer.music.unpause()
                elif event.key == pygame.K_h:
                    show_hud = not show_hud
                elif event.key == pygame.K_RIGHT and not export_mode:
                    seek_base = min(SONG_DURATION - 0.05, (manual_t if not audio_ok else seek_base) + 5.0)
                    if audio_ok:
                        pos_ms = pygame.mixer.music.get_pos()
                        cur = seek_base if pos_ms < 0 else seek_base  # reset below
                        # jump forward from current
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
                if pos_ms >= 0:
                    current_sec = seek_base + pos_ms / 1000.0
                else:
                    current_sec = manual_t
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
        frame_a = painter.render_scene(
            sa[2], sa[3], current_sec - sa[0], current_sec, sa[1] - sa[0]
        )
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
            mins = int(current_sec // 60)
            secs = int(current_sec % 60)
            hud = f"{mins:02d}:{secs:02d} / 03:00  ·  {label}"
            if not export_mode:
                hud += "   [Space · ←/→ · H · Esc]"
            screen.blit(font.render(hud, True, (180, 175, 170)), (18, 10))

        if export_mode:
            recorder.write_frame(screen)
            frame_index += 1
            if not args.no_preview:
                pygame.display.flip()
            if frame_index % (FPS * 5) == 0 or frame_index >= total_frames:
                pct = 100.0 * frame_index / total_frames
                print(f"  {frame_index}/{total_frames} frames ({pct:.0f}%)")
        else:
            pygame.display.flip()
            clock.tick(FPS)
            frame_index += 1

    if recorder:
        out = recorder.close()
        print(f"Done → {out}")

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
