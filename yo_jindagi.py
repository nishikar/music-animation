#!/usr/bin/env python3
"""
Yo Jindagi — Cinematic Vector Noir music video (4:43).
PyCairo: precision vectors, gradients, Bézier geometry, Voronoi shards.
Pygame: 60 FPS clock, particles, compositing, cinematic post-FX.

Usage:
  python yo_jindagi.py                  # windowed preview (audio optional)
  python yo_jindagi.py --export         # ffmpeg MP4 export
  python yo_jindagi.py -e --no-preview  # headless export
"""

from __future__ import annotations

import argparse
import math
import os
import random
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cairo
import numpy as np
import pygame

# =============================================================================
# CONFIG
# =============================================================================
WIDTH, HEIGHT = 1080, 720
FPS = 60
SONG_DURATION = 283.0  # 4:43
AUDIO_FILE = "yo_jindagi.mp3"

# Scene timeline (seconds)
S1_END = 48.0
S2_END = 108.0   # 1:48
S3_END = 185.0   # 3:05
S4_END = 258.0   # 4:18
# S5 → SONG_DURATION

# Scene 3 / 4 sub-beats
S3_BARREL_ZOOM = 140.0
S3_RAZOR = 160.0
S4_STRAP = 220.0
S4_SHATTER = 198.0  # bangle shatter moment

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EXPORT = SCRIPT_DIR / "yo_jindagi.mp4"

# Palette — desaturated slate / charcoal / bronze / tungsten / amber / blood
SLATE = (0.22, 0.26, 0.32)
CHARCOAL = (0.08, 0.09, 0.11)
BRONZE = (0.42, 0.32, 0.18)
TUNGSTEN = (0.35, 0.55, 0.72)
AMBER = (0.92, 0.62, 0.18)
BLOOD = (0.72, 0.08, 0.10)
COLD_WHITE = (0.78, 0.84, 0.90)
STEEL = (0.55, 0.60, 0.66)
GLASS = (0.55, 0.72, 0.82)


# =============================================================================
# MATH / COLOR HELPERS
# =============================================================================
def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = clamp((x - edge0) / (edge1 - edge0 + 1e-9))
    return t * t * (3.0 - 2.0 * t)


def rgb255(c: Tuple[float, float, float], a: float = 1.0) -> Tuple[int, int, int, int]:
    return (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255), int(a * 255))


def set_rgb(ctx: cairo.Context, c: Tuple[float, float, float], a: float = 1.0) -> None:
    ctx.set_source_rgba(c[0], c[1], c[2], a)


# =============================================================================
# VORONOI FRACTURE (half-plane clip — no SciPy)
# Best practice for brittle glass shatter: seed near impact, clip cell polygons,
# then impart radial velocity + spin from impact point.
# =============================================================================
Point = Tuple[float, float]
Poly = List[Point]


def _seg_intersect(a: Point, b: Point, p: Point, n: Point) -> Optional[Point]:
    """Intersect segment ab with line through p with normal n (half-plane boundary)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    den = dx * n[0] + dy * n[1]
    if abs(den) < 1e-12:
        return None
    t = ((p[0] - ax) * n[0] + (p[1] - ay) * n[1]) / den
    if 0.0 <= t <= 1.0:
        return (ax + t * dx, ay + t * dy)
    return None


def clip_halfplane(poly: Poly, keep: Point, other: Point) -> Poly:
    """Keep points closer to `keep` than to `other` (Voronoi half-plane)."""
    mx = (keep[0] + other[0]) * 0.5
    my = (keep[1] + other[1]) * 0.5
    nx = keep[0] - other[0]
    ny = keep[1] - other[1]
    # Normalize for stability
    ln = math.hypot(nx, ny) or 1.0
    nx, ny = nx / ln, ny / ln
    p = (mx, my)
    n = (nx, ny)

    def inside(q: Point) -> bool:
        return (q[0] - p[0]) * n[0] + (q[1] - p[1]) * n[1] >= -1e-9

    out: Poly = []
    if not poly:
        return out
    prev = poly[-1]
    prev_in = inside(prev)
    for cur in poly:
        cur_in = inside(cur)
        if cur_in:
            if not prev_in:
                hit = _seg_intersect(prev, cur, p, n)
                if hit:
                    out.append(hit)
            out.append(cur)
        elif prev_in:
            hit = _seg_intersect(prev, cur, p, n)
            if hit:
                out.append(hit)
        prev, prev_in = cur, cur_in
    return out


def voronoi_shards(
    outline: Poly,
    seeds: Sequence[Point],
    impact: Point,
) -> List[dict]:
    """Fracture outline into Voronoi cells; return shard dicts with physics."""
    shards = []
    for i, seed in enumerate(seeds):
        cell = list(outline)
        for j, other in enumerate(seeds):
            if i == j:
                continue
            cell = clip_halfplane(cell, seed, other)
            if len(cell) < 3:
                break
        if len(cell) < 3:
            continue
        cx = sum(p[0] for p in cell) / len(cell)
        cy = sum(p[1] for p in cell) / len(cell)
        dx, dy = cx - impact[0], cy - impact[1]
        dist = math.hypot(dx, dy) + 1.0
        speed = 180.0 / dist * 28.0 + random.uniform(40, 120)
        ang = math.atan2(dy, dx) + random.uniform(-0.25, 0.25)
        shards.append(
            {
                "poly": cell,
                "cx": cx,
                "cy": cy,
                "vx": math.cos(ang) * speed,
                "vy": math.sin(ang) * speed - random.uniform(20, 80),
                "spin": random.uniform(-4.0, 4.0),
                "rot": 0.0,
                "alpha": 1.0,
                "life": random.uniform(2.2, 3.6),
            }
        )
    return shards


def regular_polygon(cx: float, cy: float, r: float, n: int = 48) -> Poly:
    return [
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def ring_annulus_outline(cx: float, cy: float, r_out: float, r_in: float, n: int = 64) -> Poly:
    """Closed annulus as single outer→inner path for clip (approx as outer disc)."""
    # Shatter treats outer disc; hole drawn visually before shatter.
    return regular_polygon(cx, cy, r_out, n)


# =============================================================================
# FFMPEG EXPORT
# =============================================================================
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
        err = self._proc.stderr.read().decode("utf-8", errors="replace") if self._proc.stderr else ""
        rc = self._proc.wait()
        self._proc = None
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed ({rc}):\n{err[-2000:]}")
        return self.output_path


# =============================================================================
# CAMERA & POST-PROCESSING
# =============================================================================
class Camera:
    def __init__(self):
        self.shake = 0.0
        self.ox = 0.0
        self.oy = 0.0
        self.zoom = 1.0
        self.target_zoom = 1.0

    def impulse(self, amount: float) -> None:
        self.shake = max(self.shake, amount)

    def update(self, dt: float) -> None:
        self.shake *= max(0.0, 1.0 - dt * 6.0)
        self.ox = random.uniform(-1, 1) * self.shake
        self.oy = random.uniform(-1, 1) * self.shake
        self.zoom = lerp(self.zoom, self.target_zoom, clamp(dt * 2.5))

    def offset(self) -> Tuple[int, int]:
        return int(self.ox), int(self.oy)


class PostFX:
    """Vignette, film grain, light chromatic aberration — applied in pygame."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self._vignette = self._make_vignette()
        self._grain = np.random.randint(0, 40, (h, w), dtype=np.uint8)
        self._grain_frame = 0

    def _make_vignette(self) -> pygame.Surface:
        surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        cx, cy = self.w * 0.5, self.h * 0.5
        max_r = math.hypot(cx, cy)
        # Radial darkening via concentric alpha rings (cheap, cinematic)
        for i in range(28, 0, -1):
            t = i / 28.0
            a = int(220 * (t ** 2.2))
            r = int(max_r * (0.55 + 0.55 * (1.0 - t)))
            pygame.draw.circle(surf, (0, 0, 0, a), (int(cx), int(cy)), r)
        # Clear center so mid-frame stays readable
        clear = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.circle(clear, (0, 0, 0, 255), (int(cx), int(cy)), int(max_r * 0.42))
        surf.blit(clear, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        return surf

    def apply(
        self,
        screen: pygame.Surface,
        frame: pygame.Surface,
        camera: Camera,
        aberrate: float = 0.0,
        grain_amt: float = 0.35,
    ) -> None:
        ox, oy = camera.offset()
        if camera.zoom != 1.0:
            zw = max(2, int(self.w * camera.zoom))
            zh = max(2, int(self.h * camera.zoom))
            scaled = pygame.transform.smoothscale(frame, (zw, zh))
            blit_x = (self.w - zw) // 2 + ox
            blit_y = (self.h - zh) // 2 + oy
            screen.fill((4, 5, 7))
            screen.blit(scaled, (blit_x, blit_y))
        else:
            screen.fill((4, 5, 7))
            screen.blit(frame, (ox, oy))

        # Chromatic aberration: slight R/B channel offset
        if aberrate > 0.05:
            shift = max(1, int(aberrate * 3))
            arr = pygame.surfarray.pixels3d(screen)
            # Shift red left, blue right (in-place-ish via copy slices)
            r = arr[:, :, 0].copy()
            b = arr[:, :, 2].copy()
            arr[shift:, :, 0] = r[:-shift]
            arr[:-shift, :, 2] = b[shift:]
            del arr

        screen.blit(self._vignette, (0, 0))

        # Film grain — recycle rolling noise strip
        if grain_amt > 0.01:
            self._grain_frame = (self._grain_frame + 7) % self.h
            g = self._grain
            roll = np.roll(g, self._grain_frame, axis=0)
            grain_surf = pygame.surfarray.make_surface(
                np.stack([roll, roll, roll], axis=-1).transpose(1, 0, 2)
            )
            grain_surf.set_alpha(int(28 * grain_amt))
            screen.blit(grain_surf, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        # Letterbox
        bar = 36
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, self.w, bar))
        pygame.draw.rect(screen, (0, 0, 0), (0, self.h - bar, self.w, bar))


# =============================================================================
# PARTICLES (pygame physics)
# =============================================================================
@dataclass
class RainDrop:
    x: float
    y: float
    vx: float
    vy: float
    length: float
    alpha: float


@dataclass
class DustMote:
    x: float
    y: float
    vx: float
    vy: float
    r: float
    life: float
    max_life: float
    color: Tuple[float, float, float] = field(default_factory=lambda: COLD_WHITE)


@dataclass
class SmokePuff:
    x: float
    y: float
    vx: float
    vy: float
    r: float
    life: float
    max_life: float


class ParticleWorld:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.rain: List[RainDrop] = []
        self.dust: List[DustMote] = []
        self.smoke: List[SmokePuff] = []
        self.shards: List[dict] = []
        self.fiber_bits: List[dict] = []

    def spawn_rain(self, n: int = 4, wind: float = -1.2) -> None:
        for _ in range(n):
            self.rain.append(
                RainDrop(
                    x=random.uniform(-40, self.w + 40),
                    y=random.uniform(-80, -10),
                    vx=wind + random.uniform(-0.4, 0.2),
                    vy=random.uniform(14, 22),
                    length=random.uniform(10, 22),
                    alpha=random.uniform(0.25, 0.55),
                )
            )

    def spawn_dust_burst(self, x: float, y: float, n: int = 80) -> None:
        for _ in range(n):
            ang = random.uniform(-math.pi, 0)
            spd = random.uniform(20, 110)
            life = random.uniform(1.5, 4.0)
            self.dust.append(
                DustMote(
                    x=x + random.uniform(-12, 12),
                    y=y + random.uniform(-40, 40),
                    vx=math.cos(ang) * spd * 0.4 + random.uniform(8, 40),
                    vy=math.sin(ang) * spd * 0.3 - random.uniform(10, 40),
                    r=random.uniform(0.8, 2.4),
                    life=life,
                    max_life=life,
                    color=random.choice([COLD_WHITE, STEEL, SLATE, AMBER]),
                )
            )

    def spawn_smoke(self, x: float, y: float) -> None:
        self.smoke.append(
            SmokePuff(
                x=x,
                y=y,
                vx=random.uniform(-8, 8),
                vy=random.uniform(-18, -6),
                r=random.uniform(8, 22),
                life=random.uniform(1.2, 2.4),
                max_life=2.4,
            )
        )

    def update(self, dt: float) -> None:
        # Rain
        alive_rain = []
        for d in self.rain:
            d.x += d.vx * 60 * dt
            d.y += d.vy * 60 * dt
            if d.y < self.h + 40:
                alive_rain.append(d)
        self.rain = alive_rain

        # Dust
        alive_dust = []
        for m in self.dust:
            m.x += m.vx * dt
            m.y += m.vy * dt
            m.vx += 12 * dt  # wind
            m.vy -= 4 * dt
            m.life -= dt
            if m.life > 0:
                alive_dust.append(m)
        self.dust = alive_dust

        # Smoke
        alive_smoke = []
        for s in self.smoke:
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.r += 18 * dt
            s.life -= dt
            if s.life > 0:
                alive_smoke.append(s)
        self.smoke = alive_smoke

        # Shards
        alive_shards = []
        for sh in self.shards:
            sh["cx"] += sh["vx"] * dt
            sh["cy"] += sh["vy"] * dt
            sh["vy"] += 220 * dt  # gravity
            sh["rot"] += sh["spin"] * dt
            sh["life"] -= dt
            sh["alpha"] = clamp(sh["life"] / 1.2)
            if sh["life"] > 0 and sh["cy"] < self.h + 200:
                alive_shards.append(sh)
        self.shards = alive_shards

        # Fiber recoils
        alive_f = []
        for f in self.fiber_bits:
            f["x"] += f["vx"] * dt
            f["y"] += f["vy"] * dt
            f["vy"] += 300 * dt
            f["rot"] += f["spin"] * dt
            f["life"] -= dt
            if f["life"] > 0:
                alive_f.append(f)
        self.fiber_bits = alive_f

    def draw_pygame_overlay(self, surf: pygame.Surface) -> None:
        for d in self.rain:
            col = rgb255(TUNGSTEN, d.alpha * 0.7)[:3]
            pygame.draw.line(
                surf,
                col,
                (int(d.x), int(d.y)),
                (int(d.x + d.vx * 2), int(d.y + d.length)),
                1,
            )
        for m in self.dust:
            a = clamp(m.life / m.max_life)
            c = rgb255(m.color, a)[:3]
            pygame.draw.circle(surf, c, (int(m.x), int(m.y)), max(1, int(m.r)))
        for s in self.smoke:
            a = clamp(s.life / s.max_life) * 0.25
            layer = pygame.Surface((int(s.r * 2 + 4), int(s.r * 2 + 4)), pygame.SRCALPHA)
            pygame.draw.circle(
                layer,
                (40, 42, 48, int(255 * a)),
                (int(s.r + 2), int(s.r + 2)),
                int(s.r),
            )
            surf.blit(layer, (int(s.x - s.r), int(s.y - s.r)))


# =============================================================================
# CAIRO RENDERER
# =============================================================================
class CairoCanvas:
    """Reusable ARGB32 surface → pygame BGRA bridge (pycairo docs best practice)."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        self.ctx = cairo.Context(self.surface)

    def clear(self, rgb: Tuple[float, float, float] = CHARCOAL) -> None:
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgb(*rgb)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

    def to_pygame(self) -> pygame.Surface:
        buf = self.surface.get_data()
        return pygame.image.frombuffer(buf, (self.w, self.h), "BGRA").convert()


# =============================================================================
# SCENE DRAWING PRIMITIVES
# =============================================================================
def draw_noir_sky(ctx: cairo.Context, w: int, h: int, t: float, dusk: float = 1.0) -> None:
    grad = cairo.LinearGradient(0, 0, 0, h)
    # Overcast dusk — slate → charcoal
    top = (0.10 * dusk, 0.12 * dusk, 0.16 * dusk)
    mid = (0.14 * dusk, 0.15 * dusk, 0.18 * dusk)
    bot = (0.06, 0.07, 0.09)
    grad.add_color_stop_rgb(0.0, *top)
    grad.add_color_stop_rgb(0.55, *mid)
    grad.add_color_stop_rgb(1.0, *bot)
    ctx.set_source(grad)
    ctx.paint()

    # Atmospheric haze bands
    for i in range(5):
        y = h * (0.15 + i * 0.08)
        haze = cairo.LinearGradient(0, y - 20, 0, y + 40)
        a = 0.04 + 0.02 * math.sin(t * 0.3 + i)
        haze.add_color_stop_rgba(0, *SLATE, 0)
        haze.add_color_stop_rgba(0.5, *SLATE, a)
        haze.add_color_stop_rgba(1, *SLATE, 0)
        ctx.set_source(haze)
        ctx.rectangle(0, y - 20, w, 60)
        ctx.fill()


def draw_city_skyline(ctx: cairo.Context, w: int, h: int, t: float, cam_x: float = 0.0) -> None:
    ground_y = h * 0.72
    buildings = [
        (-80, 180, 70), (20, 220, 90), (130, 160, 55), (200, 280, 110),
        (330, 200, 75), (420, 310, 95), (540, 170, 60), (620, 250, 85),
        (730, 190, 70), (820, 270, 100), (940, 150, 55), (1020, 230, 80),
        (1120, 200, 90),
    ]
    ctx.save()
    ctx.translate(-cam_x * 0.35, 0)

    # Far ridge
    set_rgb(ctx, (0.05, 0.055, 0.07), 1)
    ctx.move_to(-100, ground_y)
    for i, (bx, bh, bw) in enumerate(buildings):
        ctx.line_to(bx, ground_y - bh * 0.45)
        ctx.line_to(bx + bw * 0.5, ground_y - bh * 0.55)
        ctx.line_to(bx + bw, ground_y - bh * 0.4)
    ctx.line_to(1300, ground_y)
    ctx.close_path()
    ctx.fill()

    for i, (bx, bh, bw) in enumerate(buildings):
        # Building body with vertical gradient (wet concrete)
        g = cairo.LinearGradient(bx, ground_y - bh, bx + bw, ground_y)
        shade = 0.07 + (i % 3) * 0.015
        g.add_color_stop_rgb(0, shade + 0.04, shade + 0.045, shade + 0.055)
        g.add_color_stop_rgb(1, shade, shade, shade + 0.01)
        ctx.set_source(g)
        ctx.rectangle(bx, ground_y - bh, bw, bh)
        ctx.fill()

        # Window grid — sparse amber / tungsten flicker
        rows, cols = max(3, bh // 28), max(2, bw // 18)
        for r in range(rows):
            for c in range(cols):
                flicker = 0.5 + 0.5 * math.sin(t * 2.1 + i * 1.7 + r * 0.4 + c)
                if flicker < 0.55:
                    continue
                lit = AMBER if (i + r + c) % 5 == 0 else TUNGSTEN
                set_rgb(ctx, lit, 0.15 + 0.25 * flicker)
                wx = bx + 6 + c * (bw - 12) / cols
                wy = ground_y - bh + 10 + r * (bh - 20) / rows
                ctx.rectangle(wx, wy, 4, 5)
                ctx.fill()

        # Wet specular edge
        set_rgb(ctx, COLD_WHITE, 0.06)
        ctx.set_line_width(1.0)
        ctx.move_to(bx + 1, ground_y - bh)
        ctx.line_to(bx + 1, ground_y)
        ctx.stroke()

    # Street plane
    street = cairo.LinearGradient(0, ground_y, 0, h)
    street.add_color_stop_rgb(0, 0.05, 0.055, 0.065)
    street.add_color_stop_rgb(1, 0.03, 0.03, 0.04)
    ctx.set_source(street)
    ctx.rectangle(-100, ground_y, w + 400, h - ground_y + 20)
    ctx.fill()

    # Reflective wet streaks
    for i in range(18):
        x = -50 + i * 75 + math.sin(t * 0.4 + i) * 8
        set_rgb(ctx, TUNGSTEN, 0.04)
        ctx.set_line_width(1.5)
        ctx.move_to(x, ground_y + 8)
        ctx.line_to(x + 40, h)
        ctx.stroke()

    ctx.restore()
    return ground_y


def draw_streetlamp(
    ctx: cairo.Context, x: float, ground_y: float, t: float, flicker_phase: float
) -> None:
    flicker = 0.75 + 0.25 * math.sin(t * 11.0 + flicker_phase) * (
        0.5 + 0.5 * math.sin(t * 3.3 + flicker_phase * 2)
    )
    # Pole
    set_rgb(ctx, (0.12, 0.12, 0.14))
    ctx.set_line_width(5)
    ctx.move_to(x, ground_y)
    ctx.line_to(x, ground_y - 210)
    ctx.stroke()
    # Arm
    ctx.set_line_width(3)
    ctx.move_to(x, ground_y - 200)
    ctx.line_to(x + 48, ground_y - 195)
    ctx.stroke()
    # Lamp housing
    set_rgb(ctx, BRONZE, 0.9)
    ctx.rectangle(x + 40, ground_y - 202, 22, 10)
    ctx.fill()
    # Volumetric glow
    glow = cairo.RadialGradient(x + 51, ground_y - 190, 2, x + 51, ground_y - 160, 160)
    glow.add_color_stop_rgba(0.0, AMBER[0], AMBER[1], AMBER[2], 0.55 * flicker)
    glow.add_color_stop_rgba(0.25, AMBER[0], AMBER[1] * 0.7, 0.05, 0.18 * flicker)
    glow.add_color_stop_rgba(1.0, AMBER[0], AMBER[1], AMBER[2], 0.0)
    ctx.set_source(glow)
    ctx.arc(x + 51, ground_y - 170, 160, 0, 2 * math.pi)
    ctx.fill()
    # Cone on street
    cone = cairo.LinearGradient(x + 51, ground_y - 190, x + 51, ground_y + 20)
    cone.add_color_stop_rgba(0, AMBER[0], AMBER[1], AMBER[2], 0.12 * flicker)
    cone.add_color_stop_rgba(1, AMBER[0], AMBER[1], AMBER[2], 0.0)
    ctx.set_source(cone)
    ctx.move_to(x + 40, ground_y - 190)
    ctx.line_to(x + 62, ground_y - 190)
    ctx.line_to(x + 140, ground_y + 10)
    ctx.line_to(x - 30, ground_y + 10)
    ctx.close_path()
    ctx.fill()


def draw_hollow_silhouette(
    ctx: cairo.Context,
    x: float,
    ground_y: float,
    scale: float,
    t: float,
    walk_phase: float,
    xray: float,
) -> None:
    """Anonymous commuter; xray reveals empty cavity + wireframe ribs."""
    ctx.save()
    ctx.translate(x, ground_y)
    ctx.scale(scale, scale)

    # Walk cycle
    stride = math.sin(walk_phase) * 0.35
    bob = abs(math.sin(walk_phase)) * 3

    ctx.translate(0, -bob)

    # Legs
    set_rgb(ctx, (0.02, 0.02, 0.03), 1.0 - 0.4 * xray)
    ctx.set_line_width(7)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(-4, -55)
    ctx.line_to(-8 - stride * 18, -5)
    ctx.stroke()
    ctx.move_to(4, -55)
    ctx.line_to(8 + stride * 18, -5)
    ctx.stroke()

    # Torso silhouette
    set_rgb(ctx, (0.02, 0.025, 0.03), 0.95 - 0.55 * xray)
    ctx.move_to(-16, -58)
    ctx.curve_to(-18, -95, -12, -118, 0, -122)
    ctx.curve_to(12, -118, 18, -95, 16, -58)
    ctx.close_path()
    ctx.fill()

    # Head
    set_rgb(ctx, (0.02, 0.02, 0.03), 0.95 - 0.5 * xray)
    ctx.arc(0, -138, 14, 0, 2 * math.pi)
    ctx.fill()

    # Arms
    set_rgb(ctx, (0.02, 0.02, 0.03), 0.9 - 0.4 * xray)
    ctx.set_line_width(5)
    ctx.move_to(-14, -100)
    ctx.line_to(-22 - stride * 8, -70)
    ctx.stroke()
    ctx.move_to(14, -100)
    ctx.line_to(20 + stride * 8, -72)
    ctx.stroke()

    if xray > 0.05:
        # Hollow cavity glow
        cav = cairo.RadialGradient(0, -95, 2, 0, -95, 28)
        cav.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.35 * xray)
        cav.add_color_stop_rgba(0.6, BLOOD[0], BLOOD[1], BLOOD[2], 0.12 * xray)
        cav.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(cav)
        ctx.save()
        ctx.scale(1.0, 1.35)
        ctx.arc(0, -95 / 1.35, 18, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Empty head cavity
        set_rgb(ctx, TUNGSTEN, 0.25 * xray)
        ctx.arc(0, -138, 9, 0, 2 * math.pi)
        ctx.fill()
        set_rgb(ctx, CHARCOAL, 0.8 * xray)
        ctx.arc(0, -138, 6, 0, 2 * math.pi)
        ctx.fill()

        # Wireframe ribcage
        set_rgb(ctx, COLD_WHITE, 0.55 * xray)
        ctx.set_line_width(0.9)
        for i in range(6):
            yy = -108 + i * 7
            spread = 10 + i * 0.8
            ctx.move_to(-spread, yy)
            ctx.curve_to(-spread * 0.3, yy - 4, spread * 0.3, yy - 4, spread, yy)
            ctx.stroke()
        # Sternum
        ctx.move_to(0, -112)
        ctx.line_to(0, -72)
        ctx.stroke()
        # Spine glow
        set_rgb(ctx, AMBER, 0.35 * xray)
        ctx.set_line_width(1.2)
        ctx.move_to(0, -120)
        ctx.line_to(0, -60)
        ctx.stroke()

    ctx.restore()


def draw_atom_loom(ctx: cairo.Context, w: int, h: int, t: float, local_t: float) -> None:
    """Orbital atom → radar / oscilloscope hybrid."""
    cx, cy = w * 0.5, h * 0.42
    pulse = 0.5 + 0.5 * math.sin(t * 2.4)

    # Overcast sky base already painted; add geometric loom glow
    bloom = cairo.RadialGradient(cx, cy, 10, cx, cy, 320)
    bloom.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.18 + 0.1 * pulse)
    bloom.add_color_stop_rgba(0.5, BLOOD[0] * 0.4, 0.02, 0.05, 0.08)
    bloom.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.set_source(bloom)
    ctx.paint()

    # Transition weight: atom → radar
    radar = smoothstep(8.0, 28.0, local_t)

    # Concentric rings
    for i in range(1, 8):
        r = 28 + i * 32 + pulse * 4 * (1 if i % 2 else -1)
        set_rgb(ctx, STEEL if i % 2 else TUNGSTEN, 0.15 + 0.1 * pulse - i * 0.01)
        ctx.set_line_width(1.2 + (0.8 if i == 3 else 0))
        ctx.arc(cx, cy, r, 0, 2 * math.pi)
        ctx.stroke()
        # Vibration ticks
        vib = math.sin(t * (6 + i) + i) * 2.5
        ctx.set_line_width(0.6)
        set_rgb(ctx, AMBER, 0.25 * pulse)
        ctx.arc(cx, cy, r + vib, 0, 2 * math.pi)
        ctx.stroke()

    # Electron orbitals (fade as radar takes over)
    for k in range(3):
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(t * (0.4 + k * 0.15) + k)
        ctx.scale(1.0, 0.35 + k * 0.08)
        set_rgb(ctx, COLD_WHITE, (0.55 - radar * 0.4) * (0.7 + 0.3 * pulse))
        ctx.set_line_width(1.4)
        ctx.arc(0, 0, 90 + k * 40, 0, 2 * math.pi)
        ctx.stroke()
        # Electron bead
        ang = t * (2.0 + k) + k * 2
        ex, ey = math.cos(ang) * (90 + k * 40), math.sin(ang) * (90 + k * 40)
        set_rgb(ctx, AMBER, 0.9 * (1 - radar * 0.5))
        ctx.arc(ex, ey, 4, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

    # Nucleus
    nuc = cairo.RadialGradient(cx - 4, cy - 4, 1, cx, cy, 22)
    nuc.add_color_stop_rgb(0, 0.95, 0.85, 0.55)
    nuc.add_color_stop_rgb(0.5, BLOOD[0], BLOOD[1], BLOOD[2])
    nuc.add_color_stop_rgb(1, 0.15, 0.02, 0.02)
    ctx.set_source(nuc)
    ctx.arc(cx, cy, 16 + pulse * 3, 0, 2 * math.pi)
    ctx.fill()

    # Radar sweep
    if radar > 0.05:
        sweep = (t * 1.8) % (2 * math.pi)
        ctx.save()
        ctx.translate(cx, cy)
        fan = cairo.RadialGradient(0, 0, 0, 0, 0, 260)
        fan.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.35 * radar)
        fan.add_color_stop_rgba(1, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0)
        ctx.set_source(fan)
        ctx.move_to(0, 0)
        ctx.arc(0, 0, 260, sweep - 0.45, sweep)
        ctx.close_path()
        ctx.fill()
        set_rgb(ctx, AMBER, 0.7 * radar)
        ctx.set_line_width(1.5)
        ctx.move_to(0, 0)
        ctx.line_to(math.cos(sweep) * 260, math.sin(sweep) * 260)
        ctx.stroke()
        # Blips
        for i in range(5):
            br = 60 + i * 35
            ba = sweep - 0.2 - i * 0.3
            bx, by = math.cos(ba) * br, math.sin(ba) * br
            set_rgb(ctx, AMBER, (0.4 + 0.4 * math.sin(t * 5 + i)) * radar)
            ctx.arc(bx, by, 3, 0, 2 * math.pi)
            ctx.fill()
        ctx.restore()

    # Oscilloscope waveforms across lower third
    ctx.set_line_width(1.3)
    for ch in range(3):
        y0 = h * 0.78 + ch * 28
        set_rgb(ctx, [TUNGSTEN, AMBER, BLOOD][ch], 0.55 + 0.2 * pulse)
        ctx.move_to(40, y0)
        amp = 12 + 18 * pulse + ch * 4
        freq = 0.04 + ch * 0.01 + local_t * 0.0008
        for x in range(40, w - 40, 3):
            phase = x * freq + t * (3 + ch) + ch
            # Impending explosion: increasing noise
            threat = smoothstep(35.0, 58.0, local_t)
            noise = (random.random() - 0.5) * 10 * threat if threat > 0 else 0
            y = y0 + math.sin(phase) * amp * (1 + threat) + math.sin(phase * 3.7) * 4 + noise
            ctx.line_to(x, y)
        ctx.stroke()

    # Crosshair ticks
    set_rgb(ctx, STEEL, 0.35)
    ctx.set_line_width(1)
    for d in (-220, -110, 110, 220):
        ctx.move_to(cx + d, cy - 8)
        ctx.line_to(cx + d, cy + 8)
        ctx.stroke()
        ctx.move_to(cx - 8, cy + d)
        ctx.line_to(cx + 8, cy + d)
        ctx.stroke()


def draw_gun_pillow_scene(
    ctx: cairo.Context, w: int, h: int, t: float, local_t: float, zoom_t: float
) -> None:
    """Solitary figure resting on giant rifled gun barrel."""
    # Dark room
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgb(0, 0.04, 0.045, 0.06)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.025)
    ctx.set_source(g)
    ctx.paint()

    # Window cold light strip
    win = cairo.LinearGradient(0, 80, w, 200)
    win.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.0)
    win.add_color_stop_rgba(0.4, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.12)
    win.add_color_stop_rgba(1, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.0)
    ctx.set_source(win)
    ctx.rectangle(0, 60, w, 140)
    ctx.fill()

    # Zoom into barrel
    z = 1.0 + zoom_t * 3.8
    ctx.save()
    cx, cy = w * 0.55, h * 0.55
    ctx.translate(cx, cy)
    ctx.scale(z, z)
    ctx.translate(-cx, -cy)

    # Barrel body protruding from wall
    bx0, by0 = -80, h * 0.48
    bw, bh = w * 0.85, 95
    barrel = cairo.LinearGradient(bx0, by0, bx0, by0 + bh)
    barrel.add_color_stop_rgb(0, 0.18, 0.20, 0.22)
    barrel.add_color_stop_rgb(0.35, 0.45, 0.48, 0.52)
    barrel.add_color_stop_rgb(0.5, 0.65, 0.68, 0.72)
    barrel.add_color_stop_rgb(0.65, 0.35, 0.37, 0.40)
    barrel.add_color_stop_rgb(1, 0.10, 0.11, 0.12)
    ctx.set_source(barrel)
    # Rounded tube
    ctx.rectangle(bx0, by0, bw, bh)
    ctx.fill()
    # Specular highlight strip
    set_rgb(ctx, COLD_WHITE, 0.35)
    ctx.rectangle(bx0, by0 + 18, bw, 6)
    ctx.fill()
    set_rgb(ctx, CHARCOAL, 0.5)
    ctx.rectangle(bx0, by0 + bh - 22, bw, 10)
    ctx.fill()

    # Muzzle face (ellipse) with rifling spiral
    mx, my = bx0 + bw - 10, by0 + bh * 0.5
    face = cairo.RadialGradient(mx - 10, my - 8, 5, mx, my, 55)
    face.add_color_stop_rgb(0, 0.25, 0.26, 0.28)
    face.add_color_stop_rgb(0.7, 0.08, 0.08, 0.09)
    face.add_color_stop_rgb(1, 0.02, 0.02, 0.02)
    ctx.set_source(face)
    ctx.save()
    ctx.translate(mx, my)
    ctx.scale(0.55, 1.0)
    ctx.arc(0, 0, 52, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()

    # Rifling grooves — hypnotic spiral into void
    set_rgb(ctx, (0.01, 0.01, 0.015), 1)
    ctx.save()
    ctx.translate(mx, my)
    ctx.scale(0.55, 1.0)
    ctx.arc(0, 0, 22, 0, 2 * math.pi)
    ctx.fill()
    for groove in range(8):
        set_rgb(ctx, STEEL, 0.35)
        ctx.set_line_width(1.2)
        ctx.new_path()
        for s in range(40):
            u = s / 40.0
            ang = groove * (math.pi / 4) + u * 4.5 * math.pi + t * 0.3
            rr = 48 * (1 - u * 0.72)
            px, py = math.cos(ang) * rr, math.sin(ang) * rr
            if s == 0:
                ctx.move_to(px, py)
            else:
                ctx.line_to(px, py)
        ctx.stroke()
    # Absolute black void
    void = cairo.RadialGradient(0, 0, 0, 0, 0, 18)
    void.add_color_stop_rgb(0, 0, 0, 0)
    void.add_color_stop_rgb(1, 0.02, 0.02, 0.03)
    ctx.set_source(void)
    ctx.arc(0, 0, 18, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()

    # Figure resting head on muzzle (fade out as we zoom deep)
    fig_a = 1.0 - smoothstep(0.25, 0.75, zoom_t)
    if fig_a > 0.02:
        ctx.save()
        ctx.translate(mx - 160, by0 + 8)
        ctx.rotate(-0.08)
        # Rim light so silhouette reads against steel
        set_rgb(ctx, AMBER, 0.22 * fig_a)
        ctx.set_line_width(10)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(-40, 0)
        ctx.curve_to(20, -36, 90, -40, 145, -18)
        ctx.stroke()
        # Reclining torso
        set_rgb(ctx, (0.01, 0.01, 0.015), 0.98 * fig_a)
        ctx.move_to(-50, 6)
        ctx.curve_to(10, -34, 90, -38, 150, -14)
        ctx.curve_to(155, 8, 40, 32, -45, 28)
        ctx.close_path()
        ctx.fill()
        # Head on muzzle
        set_rgb(ctx, (0.01, 0.01, 0.015), 0.98 * fig_a)
        ctx.arc(155, -20, 28, 0, 2 * math.pi)
        ctx.fill()
        set_rgb(ctx, AMBER, 0.35 * fig_a)
        ctx.set_line_width(1.5)
        ctx.arc(155, -20, 28, 0, 2 * math.pi)
        ctx.stroke()
        # Hollow cranial cavity
        cav = cairo.RadialGradient(155, -20, 2, 155, -20, 18)
        cav.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.55 * fig_a)
        cav.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(cav)
        ctx.arc(155, -20, 16, 0, 2 * math.pi)
        ctx.fill()
        set_rgb(ctx, CHARCOAL, 0.9 * fig_a)
        ctx.arc(155, -20, 9, 0, 2 * math.pi)
        ctx.fill()
        # Arm draped along barrel
        set_rgb(ctx, (0.01, 0.01, 0.015), 0.95 * fig_a)
        ctx.set_line_width(9)
        ctx.move_to(70, 4)
        ctx.curve_to(20, 28, -40, 34, -90, 16)
        ctx.stroke()
        ctx.restore()

    ctx.restore()

    # Dust motes in light beam
    set_rgb(ctx, COLD_WHITE, 0.15)
    for i in range(20):
        px = (math.sin(t * 0.3 + i * 1.7) * 0.5 + 0.5) * w
        py = 90 + (i * 37 + t * 12) % 200
        ctx.arc(px, py, 1.2, 0, 2 * math.pi)
        ctx.fill()


def draw_razor_wire_scene(ctx: cairo.Context, w: int, h: int, t: float, local_t: float) -> None:
    """Macro blade edge + tensed wire with tiny silhouette."""
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgb(0, 0.12, 0.16, 0.22)
    g.add_color_stop_rgb(0.45, 0.06, 0.07, 0.09)
    g.add_color_stop_rgb(1, 0.03, 0.03, 0.04)
    ctx.set_source(g)
    ctx.paint()

    # Blade — extreme macro horizontal gleam (dominates upper half)
    blade_y = h * 0.34
    blade = cairo.LinearGradient(0, blade_y - 30, 0, blade_y + 110)
    blade.add_color_stop_rgb(0, 0.22, 0.24, 0.27)
    blade.add_color_stop_rgb(0.28, 0.62, 0.66, 0.70)
    blade.add_color_stop_rgb(0.42, 0.95, 0.96, 0.97)
    blade.add_color_stop_rgb(0.48, 0.75, 0.78, 0.82)
    blade.add_color_stop_rgb(0.62, 0.32, 0.34, 0.38)
    blade.add_color_stop_rgb(1, 0.06, 0.06, 0.07)
    ctx.set_source(blade)
    ctx.move_to(-30, blade_y)
    ctx.line_to(w + 30, blade_y - 14)
    ctx.line_to(w + 30, blade_y + 120)
    ctx.line_to(-30, blade_y + 140)
    ctx.close_path()
    ctx.fill()

    # Knife-edge specular (cold sky reflection)
    set_rgb(ctx, COLD_WHITE, 0.95)
    ctx.set_line_width(2.4)
    ctx.move_to(-30, blade_y)
    ctx.line_to(w + 30, blade_y - 14)
    ctx.stroke()
    # Bevel facet
    set_rgb(ctx, TUNGSTEN, 0.45)
    ctx.set_line_width(5)
    ctx.move_to(0, blade_y + 18)
    ctx.line_to(w, blade_y + 8)
    ctx.stroke()
    # Micro scratches along steel
    set_rgb(ctx, COLD_WHITE, 0.12)
    ctx.set_line_width(0.7)
    for i in range(12):
        yy = blade_y + 28 + i * 7
        ctx.move_to(40 + i * 30, yy)
        ctx.line_to(200 + i * 55, yy - 3)
        ctx.stroke()

    # Microscopic wire under tension
    wire_y = h * 0.72
    # Tension vibration
    vib = math.sin(t * 40) * (0.8 + 1.5 * abs(math.sin(t * 2.2)))
    set_rgb(ctx, STEEL, 0.9)
    ctx.set_line_width(1.1)
    ctx.move_to(40, wire_y)
    for x in range(40, w - 40, 4):
        # Footsteps cause sharp local vibration
        walker_x = 80 + ((t * 35) % (w - 160))
        dist = abs(x - walker_x)
        local_vib = vib * math.exp(-dist * 0.04) * 8
        ctx.line_to(x, wire_y + local_vib + math.sin(x * 0.05 + t) * 0.5)
    ctx.line_to(w - 40, wire_y)
    ctx.stroke()

    # Anchor posts
    set_rgb(ctx, BRONZE, 0.8)
    ctx.rectangle(30, wire_y - 30, 12, 60)
    ctx.rectangle(w - 42, wire_y - 30, 12, 60)
    ctx.fill()

    # Tiny faceless silhouette on wire (readable at macro scale)
    walker_x = 80 + ((t * 35) % (w - 160))
    dist_phase = (t * 35) % 20
    step_vib = 6 if dist_phase < 2 else 0
    wx, wy = walker_x, wire_y - 28 - step_vib * 0.3
    # Soft contact shadow on wire
    set_rgb(ctx, AMBER, 0.3)
    ctx.arc(wx, wire_y + 1, 8, 0, 2 * math.pi)
    ctx.fill()
    # Body
    set_rgb(ctx, (0.02, 0.02, 0.03), 1)
    ctx.set_line_width(4.5)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(wx - 7, wy + 24)
    ctx.line_to(wx, wy + 4)
    ctx.line_to(wx + 7, wy + 24)
    ctx.stroke()
    # Torso block
    ctx.set_line_width(7)
    ctx.move_to(wx, wy + 4)
    ctx.line_to(wx, wy - 8)
    ctx.stroke()
    # Head
    ctx.arc(wx, wy - 14, 7, 0, 2 * math.pi)
    ctx.fill()
    set_rgb(ctx, COLD_WHITE, 0.25)
    ctx.set_line_width(1)
    ctx.arc(wx, wy - 14, 7, 0, 2 * math.pi)
    ctx.stroke()
    # Hollow head cavity micro-hint
    set_rgb(ctx, TUNGSTEN, 0.4)
    ctx.arc(wx, wy - 14, 3.2, 0, 2 * math.pi)
    ctx.fill()
    # Arms for balance
    set_rgb(ctx, (0.02, 0.02, 0.03), 1)
    ctx.set_line_width(2.6)
    ctx.move_to(wx, wy - 4)
    ctx.line_to(wx - 20, wy - 10)
    ctx.move_to(wx, wy - 4)
    ctx.line_to(wx + 20, wy - 6)
    ctx.stroke()

    # Extreme tension sparks (amber ticks)
    if abs(vib) > 1.5:
        set_rgb(ctx, AMBER, 0.5)
        for i in range(3):
            sx = walker_x + random.uniform(-20, 20)
            ctx.arc(sx, wire_y + random.uniform(-2, 2), 1, 0, 2 * math.pi)
            ctx.fill()


def draw_bangle(
    ctx: cairo.Context, cx: float, cy: float, rot: float, intact: bool = True
) -> None:
    """Delicate translucent glass ring in spotlight."""
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)

    # Spotlight on ground
    spot = cairo.RadialGradient(0, 80, 10, 0, 90, 180)
    spot.add_color_stop_rgba(0, COLD_WHITE[0], COLD_WHITE[1], COLD_WHITE[2], 0.2)
    spot.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.set_source(spot)
    ctx.arc(0, 90, 180, 0, 2 * math.pi)
    ctx.fill()

    if not intact:
        ctx.restore()
        return

    r_out, r_in = 70, 52
    # Glass body with refractive gradient
    for i in range(24):
        a0 = i * 2 * math.pi / 24
        a1 = (i + 1) * 2 * math.pi / 24
        mid = (a0 + a1) * 0.5
        # Thickness variation / caustic
        shade = 0.35 + 0.45 * abs(math.cos(mid + rot * 2))
        set_rgb(ctx, GLASS, 0.25 + shade * 0.35)
        ctx.move_to(math.cos(a0) * r_in, math.sin(a0) * r_in)
        ctx.line_to(math.cos(a0) * r_out, math.sin(a0) * r_out)
        ctx.line_to(math.cos(a1) * r_out, math.sin(a1) * r_out)
        ctx.line_to(math.cos(a1) * r_in, math.sin(a1) * r_in)
        ctx.close_path()
        ctx.fill()

    # Specular rim
    set_rgb(ctx, COLD_WHITE, 0.75)
    ctx.set_line_width(2.2)
    ctx.arc(0, 0, r_out, -0.8, 0.6)
    ctx.stroke()
    set_rgb(ctx, TUNGSTEN, 0.5)
    ctx.set_line_width(1.4)
    ctx.arc(0, 0, r_in, 1.2, 2.8)
    ctx.stroke()

    # Inner void
    set_rgb(ctx, CHARCOAL, 0.3)
    ctx.arc(0, 0, r_in - 1, 0, 2 * math.pi)
    ctx.fill()

    ctx.restore()


def draw_shards_cairo(ctx: cairo.Context, shards: List[dict]) -> None:
    for sh in shards:
        if sh["alpha"] <= 0.01:
            continue
        ctx.save()
        ctx.translate(sh["cx"], sh["cy"])
        ctx.rotate(sh["rot"])
        ctx.translate(-sh["cx"], -sh["cy"])
        poly = sh["poly"]
        # Offset poly to follow centroid motion: rebuild relative
        # poly is in original coords; we moved by delta from original centroid
        # Actually we update cx,cy but poly is absolute original — re-base:
        ctx.restore()
        ctx.save()
        ox = sum(p[0] for p in poly) / len(poly)
        oy = sum(p[1] for p in poly) / len(poly)
        ctx.translate(sh["cx"], sh["cy"])
        ctx.rotate(sh["rot"])
        ctx.translate(-ox, -oy)
        # Glass shard fill
        g = cairo.LinearGradient(poly[0][0], poly[0][1], poly[len(poly) // 2][0], poly[len(poly) // 2][1])
        g.add_color_stop_rgba(0, GLASS[0], GLASS[1], GLASS[2], 0.55 * sh["alpha"])
        g.add_color_stop_rgba(1, COLD_WHITE[0], COLD_WHITE[1], COLD_WHITE[2], 0.35 * sh["alpha"])
        ctx.set_source(g)
        ctx.move_to(poly[0][0], poly[0][1])
        for p in poly[1:]:
            ctx.line_to(p[0], p[1])
        ctx.close_path()
        ctx.fill_preserve()
        set_rgb(ctx, COLD_WHITE, 0.7 * sh["alpha"])
        ctx.set_line_width(0.8)
        ctx.stroke()
        ctx.restore()


def draw_strap_scene(
    ctx: cairo.Context, w: int, h: int, t: float, local_t: float, snap_t: float, fibers_left: int
) -> None:
    """Worn sandal strap stretched to limit; fibers fray then snap."""
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgb(0, 0.08, 0.07, 0.06)
    g.add_color_stop_rgb(1, 0.03, 0.03, 0.035)
    ctx.set_source(g)
    ctx.paint()

    # Soft key light
    spot = cairo.RadialGradient(w * 0.5, h * 0.35, 20, w * 0.5, h * 0.45, 380)
    spot.add_color_stop_rgba(0, BRONZE[0], BRONZE[1], BRONZE[2], 0.2)
    spot.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.set_source(spot)
    ctx.paint()

    y = h * 0.5
    left, right = 100, w - 100
    stretch = 1.0 + 0.08 * math.sin(t * 3) + snap_t * 0.15

    # Leather body
    set_rgb(ctx, (0.28, 0.18, 0.10), 0.95)
    ctx.set_line_width(18)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    mid_sag = 12 * stretch
    ctx.move_to(left, y)
    ctx.curve_to(w * 0.35, y + mid_sag, w * 0.65, y + mid_sag, right, y)
    ctx.stroke()

    # Wear scratches
    set_rgb(ctx, (0.15, 0.10, 0.06), 0.5)
    ctx.set_line_width(1)
    for i in range(8):
        xx = left + 40 + i * 90
        ctx.move_to(xx, y - 6 + mid_sag * 0.5)
        ctx.line_to(xx + 30, y + 4 + mid_sag * 0.5)
        ctx.stroke()

    # Vector fibers under tension
    n_fibers = 12
    for i in range(n_fibers):
        if i >= fibers_left:
            continue
        fy = y - 8 + i * 1.5
        tension_noise = math.sin(t * 25 + i) * (2 + snap_t * 6)
        # Fray near center as snap approaches
        fray = smoothstep(0.0, 1.0, snap_t)
        gap = 20 * fray if i % 3 == 0 else 0
        set_rgb(ctx, (0.55, 0.42, 0.28), 0.7)
        ctx.set_line_width(1.0)
        cxm = w * 0.5
        ctx.move_to(left + 20, fy)
        ctx.line_to(cxm - gap - 5, fy + tension_noise + mid_sag * 0.4)
        if gap > 0:
            # Broken gap — frayed ends
            set_rgb(ctx, AMBER, 0.4)
            ctx.move_to(cxm + gap + 5, fy + tension_noise + mid_sag * 0.4)
            ctx.line_to(right - 20, fy)
        else:
            ctx.line_to(right - 20, fy)
        ctx.stroke()

    # Metal buckle posts
    for px in (left, right):
        set_rgb(ctx, STEEL, 0.9)
        ctx.rectangle(px - 8, y - 24, 16, 48)
        ctx.fill()
        highlight = cairo.LinearGradient(px - 8, y - 24, px + 8, y + 24)
        highlight.add_color_stop_rgba(0, 1, 1, 1, 0.35)
        highlight.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(highlight)
        ctx.rectangle(px - 8, y - 24, 16, 48)
        ctx.fill()

    if snap_t > 0.98:
        # Empty space after snap — residual vibration marks
        set_rgb(ctx, BLOOD, 0.15)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        # no text — just residual spring arcs
        for i in range(6):
            set_rgb(ctx, BRONZE, 0.25)
            ctx.set_line_width(1.2)
            ctx.arc(w * 0.35 + i * 40, y, 15 + i * 3, 0.2, math.pi - 0.2)
            ctx.stroke()


# =============================================================================
# DIRECTOR
# =============================================================================
class Director:
    def __init__(self):
        self.canvas = CairoCanvas(WIDTH, HEIGHT)
        self.particles = ParticleWorld(WIDTH, HEIGHT)
        self.camera = Camera()
        self.post = PostFX(WIDTH, HEIGHT)
        self._bangle_shattered = False
        self._strap_snapped = False
        self._disintegrating = False
        self._fibers_left = 12
        self._commuters = [
            {"x": random.uniform(-100, WIDTH + 100), "speed": random.uniform(28, 55),
             "phase": random.uniform(0, 10), "scale": random.uniform(0.85, 1.15),
             "lamp": i}
            for i in range(7)
        ]
        self._rng_state = random.Random(42)

    def scene_name(self, t: float) -> str:
        if t < S1_END:
            return "THE HOLLOW SHELLS"
        if t < S2_END:
            return "THE ATOMIC LOOM"
        if t < S3_END:
            return "RAZOR'S EDGE / GUN BARREL"
        if t < S4_END:
            return "THE SUDDEN SHATTER"
        return "DISINTEGRATION"

    def render(self, t: float, dt: float) -> pygame.Surface:
        ctx = self.canvas.ctx
        parts = self.particles
        cam = self.camera

        # Reset one-shot flags on loop
        if t < 0.1:
            self._bangle_shattered = False
            self._strap_snapped = False
            self._disintegrating = False
            self._fibers_left = 12
            parts.shards.clear()
            parts.dust.clear()
            parts.fiber_bits.clear()
            cam.target_zoom = 1.0
            cam.zoom = 1.0

        aberrate = 0.0
        grain = 0.4

        if t < S1_END:
            parts.shards.clear()
            self._scene1(ctx, t, dt)
            grain = 0.45
        elif t < S2_END:
            parts.shards.clear()
            self._scene2(ctx, t, dt)
            aberrate = 0.3 + 0.4 * smoothstep(S2_END - 12, S2_END, t)
            grain = 0.35
        elif t < S3_END:
            parts.shards.clear()
            self._scene3(ctx, t, dt)
            grain = 0.3
        elif t < S4_END:
            self._scene4(ctx, t, dt)
            grain = 0.5
            if self._bangle_shattered and t < S4_SHATTER + 1.5:
                cam.impulse(10)
                aberrate = 1.2
            if self._strap_snapped and t < S4_STRAP + 1.0:
                cam.impulse(14)
                aberrate = 1.5
        else:
            # City return — no leftover shatter geometry
            parts.shards.clear()
            parts.fiber_bits.clear()
            self._scene5(ctx, t, dt)
            grain = 0.55

        frame = self.canvas.to_pygame()
        parts.update(dt)
        parts.draw_pygame_overlay(frame)
        cam.update(dt)

        # Composite to working surface for post
        out = pygame.Surface((WIDTH, HEIGHT))
        self.post.apply(out, frame, cam, aberrate=aberrate, grain_amt=grain)
        return out

    def _scene1(self, ctx: cairo.Context, t: float, dt: float) -> None:
        self.canvas.clear()
        draw_noir_sky(ctx, WIDTH, HEIGHT, t, dusk=0.85)
        cam_x = t * 12  # slow tracking
        ground_y = draw_city_skyline(ctx, WIDTH, HEIGHT, t, cam_x)

        # Lamps
        for i, lx in enumerate([160, 420, 700, 960]):
            draw_streetlamp(ctx, lx - cam_x * 0.35, ground_y, t, i * 1.7)

        # X-ray pass ramps mid-scene
        xray = smoothstep(12.0, 28.0, t) * (1.0 - 0.3 * smoothstep(40.0, 48.0, t))

        for c in self._commuters:
            c["x"] += c["speed"] * dt
            if c["x"] > WIDTH + 80:
                c["x"] = -80
                c["scale"] = random.uniform(0.85, 1.15)
                c["speed"] = random.uniform(28, 55)
            phase = t * 3.2 + c["phase"]
            draw_hollow_silhouette(
                ctx, c["x"] - cam_x * 0.15, ground_y, c["scale"], t, phase, xray
            )

        # Rain
        self.particles.spawn_rain(5, wind=-1.5)
        if random.random() < 0.08:
            self.particles.spawn_smoke(random.uniform(0, WIDTH), ground_y - 20)

    def _scene2(self, ctx: cairo.Context, t: float, dt: float) -> None:
        local = t - S1_END
        self.canvas.clear()
        # Pan up: show dwindling skyline then atom
        pan = smoothstep(0, 8, local)
        draw_noir_sky(ctx, WIDTH, HEIGHT, t, dusk=0.7)
        if pan < 0.95:
            ctx.save()
            ctx.translate(0, pan * HEIGHT * 0.55)
            draw_city_skyline(ctx, WIDTH, HEIGHT, t, local * 5)
            ctx.restore()
        draw_atom_loom(ctx, WIDTH, HEIGHT, t, local)
        # Soft particles as static
        if random.random() < 0.2:
            self.particles.dust.append(
                DustMote(
                    x=random.uniform(0, WIDTH),
                    y=random.uniform(0, HEIGHT * 0.6),
                    vx=random.uniform(-5, 5),
                    vy=random.uniform(-8, -1),
                    r=random.uniform(0.5, 1.5),
                    life=1.5,
                    max_life=1.5,
                    color=TUNGSTEN,
                )
            )

    def _scene3(self, ctx: cairo.Context, t: float, dt: float) -> None:
        local = t - S2_END
        self.canvas.clear(CHARCOAL)
        if t < S3_RAZOR:
            zoom_t = smoothstep(S3_BARREL_ZOOM - S2_END, S3_RAZOR - S2_END, local)
            draw_gun_pillow_scene(ctx, WIDTH, HEIGHT, t, local, zoom_t)
        else:
            # Crossfade into razor
            blend = smoothstep(S3_RAZOR, S3_RAZOR + 2.0, t)
            if blend < 1:
                zoom_t = 1.0
                draw_gun_pillow_scene(ctx, WIDTH, HEIGHT, t, local, zoom_t)
                # Darken
                set_rgb(ctx, CHARCOAL, blend * 0.85)
                ctx.paint()
            draw_razor_wire_scene(ctx, WIDTH, HEIGHT, t, t - S3_RAZOR)

    def _scene4(self, ctx: cairo.Context, t: float, dt: float) -> None:
        local = t - S3_END
        self.canvas.clear((0.04, 0.04, 0.05))

        if t < S4_STRAP:
            # Bangle spotlight
            set_rgb(ctx, CHARCOAL)
            ctx.paint()
            # Ambient dark room
            spot = cairo.RadialGradient(WIDTH / 2, HEIGHT / 2, 20, WIDTH / 2, HEIGHT / 2, 400)
            spot.add_color_stop_rgba(0, 0.12, 0.13, 0.16, 1)
            spot.add_color_stop_rgba(1, 0.02, 0.02, 0.03, 1)
            ctx.set_source(spot)
            ctx.paint()

            rot = t * 0.7
            intact = not self._bangle_shattered
            if t >= S4_SHATTER and not self._bangle_shattered:
                self._bangle_shattered = True
                cx, cy = WIDTH / 2, HEIGHT / 2 - 20
                outline = ring_annulus_outline(cx, cy, 72, 50, 48)
                seeds = []
                for _ in range(42):
                    ang = random.uniform(0, 2 * math.pi)
                    rr = random.uniform(8, 70)
                    # Bias toward impact at top-right
                    if random.random() < 0.4:
                        ang = random.uniform(-0.5, 0.8)
                        rr = random.uniform(5, 40)
                    seeds.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
                self.particles.shards = voronoi_shards(outline, seeds, (cx + 30, cy - 20))
                # Boost outward speeds for readable slow-mo scatter
                for sh in self.particles.shards:
                    sh["vx"] *= 1.35
                    sh["vy"] *= 1.35
                    sh["life"] = random.uniform(3.0, 5.0)
                self.camera.impulse(12)
                for _ in range(3):
                    self.particles.spawn_smoke(cx, cy)

            draw_bangle(ctx, WIDTH / 2, HEIGHT / 2 - 20, rot, intact=intact)
            if self._bangle_shattered:
                draw_shards_cairo(ctx, self.particles.shards)
        else:
            # Strap — drop glass debris from previous beat
            self.particles.shards.clear()
            snap_progress = smoothstep(S4_STRAP, S4_STRAP + 8.0, t)
            # Fray fibers one by one
            target_left = max(0, int(12 * (1.0 - snap_progress * 0.95)))
            if target_left < self._fibers_left:
                # Spawn recoiling fiber bits
                for i in range(self._fibers_left - target_left):
                    self.particles.fiber_bits.append(
                        {
                            "x": WIDTH * 0.5 + random.uniform(-30, 30),
                            "y": HEIGHT * 0.5,
                            "vx": random.choice([-1, 1]) * random.uniform(120, 280),
                            "vy": random.uniform(-80, -20),
                            "spin": random.uniform(-10, 10),
                            "rot": 0,
                            "life": random.uniform(0.8, 1.6),
                            "len": random.uniform(20, 50),
                        }
                    )
                self._fibers_left = target_left

            if t >= S4_STRAP + 10.0 and not self._strap_snapped:
                self._strap_snapped = True
                self._fibers_left = 0
                self.camera.impulse(16)
                for _ in range(20):
                    self.particles.fiber_bits.append(
                        {
                            "x": WIDTH * 0.5,
                            "y": HEIGHT * 0.5,
                            "vx": random.choice([-1, 1]) * random.uniform(200, 420),
                            "vy": random.uniform(-200, 40),
                            "spin": random.uniform(-15, 15),
                            "rot": 0,
                            "life": random.uniform(1.0, 2.2),
                            "len": random.uniform(30, 70),
                        }
                    )

            snap_t = 1.0 if self._strap_snapped else snap_progress
            draw_strap_scene(ctx, WIDTH, HEIGHT, t, local, snap_t, self._fibers_left)

            # Draw recoiling fibers
            for f in self.particles.fiber_bits:
                set_rgb(ctx, BRONZE, clamp(f["life"]))
                ctx.set_line_width(1.5)
                ctx.save()
                ctx.translate(f["x"], f["y"])
                ctx.rotate(f["rot"])
                ctx.move_to(-f["len"] * 0.5, 0)
                ctx.line_to(f["len"] * 0.5, 0)
                ctx.stroke()
                ctx.restore()

    def _scene5(self, ctx: cairo.Context, t: float, dt: float) -> None:
        local = t - S4_END
        self.canvas.clear()
        draw_noir_sky(ctx, WIDTH, HEIGHT, t, dusk=0.75)
        ground_y = draw_city_skyline(ctx, WIDTH, HEIGHT, t, 0)
        draw_streetlamp(ctx, WIDTH * 0.5 - 40, ground_y, t, 0.5)

        # Solitary silhouette at intersection → dust motes
        dis_t = smoothstep(3.0, 14.0, local)
        if not self._disintegrating and dis_t > 0.1:
            self._disintegrating = True

        sx = WIDTH * 0.5
        if dis_t < 0.92:
            # Progressive clip-dissolve from crown downward
            ctx.save()
            remain = 1.0 - dis_t
            ctx.rectangle(sx - 60, ground_y - 200 * remain, 120, 220)
            ctx.clip()
            draw_hollow_silhouette(ctx, sx, ground_y, 1.35, t, 0.0, 0.25 + dis_t * 0.6)
            ctx.restore()
            # Dissolving edge glow
            if 0.05 < dis_t < 0.9:
                edge_y = ground_y - 200 * (1.0 - dis_t)
                set_rgb(ctx, COLD_WHITE, 0.35 * (1.0 - dis_t))
                for i in range(14):
                    ctx.arc(
                        sx + random.uniform(-22, 22),
                        edge_y + random.uniform(-4, 4),
                        random.uniform(0.8, 2.2),
                        0,
                        2 * math.pi,
                    )
                    ctx.fill()

        # Continuous dust stream carried by wind
        if dis_t > 0.02:
            rate = 0.55 + dis_t * 1.4
            if random.random() < rate:
                self.particles.spawn_dust_burst(
                    sx + random.uniform(-14, 14),
                    ground_y - random.uniform(10, 170 * (1.0 - dis_t * 0.5)),
                    n=int(5 + dis_t * 14),
                )

        self.particles.spawn_rain(5, wind=-1.4)
        if random.random() < 0.06:
            self.particles.spawn_smoke(sx + random.uniform(-80, 80), ground_y - 10)


# =============================================================================
# CLI / MAIN
# =============================================================================
def parse_args():
    p = argparse.ArgumentParser(description="Yo Jindagi — Cinematic Vector Noir MV")
    p.add_argument("--export", "-e", action="store_true", help="Export MP4 via ffmpeg")
    p.add_argument("--output", "-o", type=Path, default=DEFAULT_EXPORT, help="Output MP4 path")
    p.add_argument("--no-preview", action="store_true", help="Headless export (SDL dummy)")
    p.add_argument("--hud", action="store_true", help="Show HUD in export")
    p.add_argument("--start", type=float, default=0.0, help="Start time (seconds)")
    return p.parse_args()


def main():
    args = parse_args()
    export_mode = args.export

    if export_mode and args.no_preview:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass

    flags = 0
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    pygame.display.set_caption("Yo Jindagi — Cinematic Vector Noir")
    clock = pygame.time.Clock()

    audio_path = SCRIPT_DIR / AUDIO_FILE
    if not export_mode and audio_path.is_file():
        try:
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
            if args.start > 0:
                pygame.mixer.music.set_pos(args.start)
        except pygame.error as e:
            print(f"[AUDIO] {e}")
    elif not audio_path.is_file():
        print(f"[AUDIO] {AUDIO_FILE} not found — silent preview (add file later).")

    director = Director()
    recorder = None
    if export_mode:
        recorder = FfmpegRecorder(
            args.output,
            audio_path=audio_path if audio_path.is_file() else None,
        )
        print(f"Exporting → {args.output}")

    anim_t = float(args.start)
    frame_index = int(anim_t * FPS)
    total_frames = int(SONG_DURATION * FPS)
    running = True
    font = None

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and not export_mode:
                    anim_t = min(SONG_DURATION - 0.1, anim_t + 15.0)
                elif event.key == pygame.K_RIGHT and not export_mode:
                    anim_t = min(SONG_DURATION - 0.1, anim_t + 5.0)
                elif event.key == pygame.K_LEFT and not export_mode:
                    anim_t = max(0.0, anim_t - 5.0)

        if export_mode:
            dt = 1.0 / FPS
            anim_t = frame_index / FPS
            if frame_index >= total_frames:
                running = False
                continue
        else:
            dt = clock.tick(FPS) / 1000.0
            anim_t += dt
            if anim_t >= SONG_DURATION:
                anim_t = 0.0
                director = Director()  # reset one-shots
                if audio_path.is_file() and pygame.mixer.get_init():
                    try:
                        pygame.mixer.music.play()
                    except pygame.error:
                        pass

        frame = director.render(anim_t, dt)
        screen.blit(frame, (0, 0))

        show_hud = (not export_mode) or args.hud
        if show_hud:
            if font is None:
                font = pygame.font.SysFont("monospace", 14, bold=True)
            mins, secs = int(anim_t) // 60, int(anim_t) % 60
            label = (
                f"[{mins:02d}:{secs:02d} / 04:43] {director.scene_name(anim_t)}"
                + ("  [←/→ seek · SPACE +15s · ESC quit]" if not export_mode else "")
            )
            hud = font.render(label, True, (160, 150, 130))
            screen.blit(hud, (20, 12))

        if export_mode:
            recorder.write_frame(screen)
            frame_index += 1
            if not args.no_preview:
                pygame.display.flip()
            if frame_index % (FPS * 5) == 0 or frame_index == total_frames:
                print(f"  {frame_index}/{total_frames} ({100 * frame_index / total_frames:.0f}%)")
        else:
            pygame.display.flip()

    if recorder:
        out = recorder.close()
        print(f"Done → {out}")

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
