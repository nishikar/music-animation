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
S3_FIRE = 156.0       # muzzle blast just before razor cut
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
    style: Optional[dict] = None,
) -> None:
    """Anonymous commuter with clothing/hair/hat variety; xray shows hollow cavity."""
    style = style or {}
    coat = style.get("coat", "coat")          # coat | trench | jacket | raincoat | overcoat
    hair = style.get("hair", "short")         # short | long | buzz | bun | bald
    hat = style.get("hat", "none")            # none | fedora | cap | beanie | bowler
    build = style.get("build", "avg")         # slim | avg | heavy
    bag = style.get("bag", False)
    facing = style.get("facing", 1)           # 1 right, -1 left

    width_mul = {"slim": 0.82, "avg": 1.0, "heavy": 1.22}.get(build, 1.0)
    hem = {"trench": -48, "coat": -52, "jacket": -62, "raincoat": -50, "overcoat": -46}.get(coat, -52)
    shoulder = 16 * width_mul
    hip = (14 if coat != "jacket" else 12) * width_mul

    ctx.save()
    ctx.translate(x, ground_y)
    ctx.scale(scale * facing, scale)

    stride = math.sin(walk_phase) * 0.35
    bob = abs(math.sin(walk_phase)) * 3
    ctx.translate(0, -bob)

    sil = (0.02, 0.02, 0.03)
    sil_a = 0.98 - 0.25 * xray  # keep coat shapes readable during xray

    # Legs / trousers (visible below coat hem)
    set_rgb(ctx, sil, sil_a)
    ctx.set_line_width(6.5 + (1.5 if build == "heavy" else 0))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(-5, hem + 4)
    ctx.line_to(-9 - stride * 18, -4)
    ctx.stroke()
    ctx.move_to(5, hem + 4)
    ctx.line_to(9 + stride * 18, -4)
    ctx.stroke()
    # Shoes
    ctx.set_line_width(3.5)
    ctx.move_to(-9 - stride * 18, -4)
    ctx.line_to(-16 - stride * 18, -2)
    ctx.stroke()
    ctx.move_to(9 + stride * 18, -4)
    ctx.line_to(18 + stride * 18, -2)
    ctx.stroke()

    # Coat / torso body — distinct silhouettes per garment
    set_rgb(ctx, sil, sil_a)
    if coat == "trench":
        # Flared trench with belt notch
        ctx.move_to(-shoulder - 4, -58)
        ctx.curve_to(-shoulder - 6, -100, -12, -118, 0, -124)
        ctx.curve_to(12, -118, shoulder + 6, -100, shoulder + 4, -58)
        ctx.line_to(hip + 8, hem)
        ctx.line_to(-hip - 8, hem)
        ctx.close_path()
        ctx.fill()
        # Belt
        set_rgb(ctx, sil, sil_a)
        ctx.rectangle(-hip - 2, -72, (hip + 2) * 2, 5)
        ctx.fill()
        # Collar flaps
        ctx.move_to(-10, -118)
        ctx.line_to(-18, -108)
        ctx.line_to(-6, -112)
        ctx.fill()
        ctx.move_to(10, -118)
        ctx.line_to(18, -108)
        ctx.line_to(6, -112)
        ctx.fill()
    elif coat == "raincoat":
        ctx.move_to(-shoulder - 2, -60)
        ctx.curve_to(-shoulder - 8, -95, -10, -120, 0, -124)
        ctx.curve_to(10, -120, shoulder + 8, -95, shoulder + 2, -60)
        ctx.line_to(hip + 10, hem)
        ctx.curve_to(0, hem + 6, 0, hem + 6, -hip - 10, hem)
        ctx.close_path()
        ctx.fill()
        # Hood bulge when no hat
        if hat == "none":
            set_rgb(ctx, sil, sil_a)
            ctx.arc(0, -130, 18, math.pi, 2 * math.pi)
            ctx.fill()
    elif coat == "jacket":
        ctx.move_to(-shoulder, -60)
        ctx.curve_to(-shoulder - 2, -100, -10, -118, 0, -122)
        ctx.curve_to(10, -118, shoulder + 2, -100, shoulder, -60)
        ctx.line_to(hip, hem)
        ctx.line_to(-hip, hem)
        ctx.close_path()
        ctx.fill()
        # Open front slit
        set_rgb(ctx, CHARCOAL, 0.5 * sil_a)
        ctx.move_to(0, -110)
        ctx.line_to(-3, hem)
        ctx.line_to(3, hem)
        ctx.close_path()
        ctx.fill()
    elif coat == "overcoat":
        ctx.move_to(-shoulder - 6, -58)
        ctx.curve_to(-shoulder - 8, -98, -12, -118, 0, -124)
        ctx.curve_to(12, -118, shoulder + 8, -98, shoulder + 6, -58)
        ctx.line_to(hip + 12, hem - 2)
        ctx.line_to(-hip - 12, hem - 2)
        ctx.close_path()
        ctx.fill()
    else:  # coat
        ctx.move_to(-shoulder, -58)
        ctx.curve_to(-shoulder - 4, -95, -12, -118, 0, -122)
        ctx.curve_to(12, -118, shoulder + 4, -95, shoulder, -58)
        ctx.line_to(hip + 4, hem)
        ctx.line_to(-hip - 4, hem)
        ctx.close_path()
        ctx.fill()

    # Head
    set_rgb(ctx, sil, sil_a)
    ctx.arc(0, -138, 13.5, 0, 2 * math.pi)
    ctx.fill()

    # Arms
    set_rgb(ctx, sil, sil_a * 0.95)
    sleeve_w = 5.5 if coat != "jacket" else 4.5
    ctx.set_line_width(sleeve_w)
    arm_end = -68 if coat in ("trench", "overcoat", "raincoat") else -72
    ctx.move_to(-shoulder + 2, -100)
    ctx.line_to(-22 - stride * 8, arm_end)
    ctx.stroke()
    ctx.move_to(shoulder - 2, -100)
    ctx.line_to(20 + stride * 8, arm_end - 2)
    ctx.stroke()

    if bag:
        set_rgb(ctx, sil, sil_a)
        bx = 18 + stride * 6
        ctx.rectangle(bx, -78, 14, 18)
        ctx.fill()
        ctx.set_line_width(1.5)
        ctx.move_to(shoulder - 2, -100)
        ctx.line_to(bx + 4, -78)
        ctx.stroke()

    if xray > 0.05:
        cav = cairo.RadialGradient(0, -95, 2, 0, -95, 28)
        cav.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.28 * xray)
        cav.add_color_stop_rgba(0.6, BLOOD[0], BLOOD[1], BLOOD[2], 0.10 * xray)
        cav.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(cav)
        ctx.save()
        ctx.scale(1.0, 1.35)
        ctx.arc(0, -95 / 1.35, 16, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        set_rgb(ctx, COLD_WHITE, 0.45 * xray)
        ctx.set_line_width(0.9)
        for i in range(6):
            yy = -108 + i * 7
            spread = 9 + i * 0.7
            ctx.move_to(-spread, yy)
            ctx.curve_to(-spread * 0.3, yy - 4, spread * 0.3, yy - 4, spread, yy)
            ctx.stroke()
        set_rgb(ctx, AMBER, 0.3 * xray)
        ctx.set_line_width(1.1)
        ctx.move_to(0, -118)
        ctx.line_to(0, -65)
        ctx.stroke()

    # Hats & hair drawn AFTER xray so silhouette variety always reads
    set_rgb(ctx, sil, min(1.0, sil_a + 0.15))
    if hair == "long":
        ctx.move_to(-14, -142)
        ctx.curve_to(-22, -128, -20, -100, -16, -88)
        ctx.line_to(-8, -90)
        ctx.curve_to(-12, -110, -10, -132, -4, -140)
        ctx.fill()
        ctx.move_to(14, -142)
        ctx.curve_to(22, -128, 20, -100, 16, -88)
        ctx.line_to(8, -90)
        ctx.curve_to(12, -110, 10, -132, 4, -140)
        ctx.fill()
        ctx.move_to(-12, -148)
        ctx.curve_to(-6, -115, 6, -115, 12, -148)
        ctx.close_path()
        ctx.fill()
    elif hair == "bun":
        ctx.arc(-2, -154, 8, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(0, -146, 13, math.pi, 2 * math.pi)
        ctx.fill()
    elif hair == "buzz":
        ctx.arc(0, -138, 15.5, math.pi * 1.02, math.pi * 1.98)
        ctx.fill()
    elif hair == "short":
        ctx.move_to(-14, -140)
        ctx.curve_to(-12, -155, 12, -155, 14, -140)
        ctx.line_to(12, -135)
        ctx.curve_to(8, -148, -8, -148, -12, -135)
        ctx.close_path()
        ctx.fill()

    if hat == "fedora":
        set_rgb(ctx, sil, 1.0)
        ctx.rectangle(-20, -150, 40, 5)
        ctx.fill()
        ctx.move_to(-13, -150)
        ctx.curve_to(-11, -168, 11, -168, 13, -150)
        ctx.close_path()
        ctx.fill()
        set_rgb(ctx, BRONZE, 0.35)
        ctx.rectangle(-18, -149, 36, 2)
        ctx.fill()
    elif hat == "cap":
        set_rgb(ctx, sil, 1.0)
        ctx.arc(0, -144, 15, math.pi, 2 * math.pi)
        ctx.fill()
        ctx.move_to(4, -144)
        ctx.line_to(26, -138)
        ctx.line_to(10, -148)
        ctx.close_path()
        ctx.fill()
    elif hat == "beanie":
        set_rgb(ctx, sil, 1.0)
        ctx.arc(0, -144, 16, math.pi, 2 * math.pi)
        ctx.fill()
        ctx.rectangle(-16, -146, 32, 10)
        ctx.fill()
        ctx.arc(0, -162, 4, 0, 2 * math.pi)
        ctx.fill()
    elif hat == "bowler":
        set_rgb(ctx, sil, 1.0)
        ctx.rectangle(-18, -148, 36, 4)
        ctx.fill()
        ctx.arc(0, -148, 14, math.pi, 2 * math.pi)
        ctx.fill()

    ctx.restore()


def draw_airplane(
    ctx: cairo.Context, x: float, y: float, scale: float, heading: float, bank: float = 0.0
) -> None:
    """Noir metallic airliner / bomber with cockpit glass and engine nacelles."""
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(heading)
    ctx.scale(scale, scale * (1.0 - abs(bank) * 0.12))

    # Soft under-shadow
    set_rgb(ctx, (0, 0, 0), 0.25)
    ctx.save()
    ctx.translate(0, 10)
    ctx.scale(1.0, 0.25)
    ctx.arc(0, 0, 50, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()

    # Main wing (drawn under fuselage)
    wing = cairo.LinearGradient(0, -40, 0, 40)
    wing.add_color_stop_rgb(0, 0.42, 0.45, 0.48)
    wing.add_color_stop_rgb(0.5, 0.22, 0.24, 0.26)
    wing.add_color_stop_rgb(1, 0.42, 0.45, 0.48)
    ctx.set_source(wing)
    ctx.move_to(-8, 0)
    ctx.line_to(-35, -38 - bank * 10)
    ctx.line_to(8, -32 - bank * 8)
    ctx.line_to(22, -2)
    ctx.line_to(8, 32 + bank * 8)
    ctx.line_to(-35, 38 + bank * 10)
    ctx.close_path()
    ctx.fill()
    # Wing edge light
    set_rgb(ctx, COLD_WHITE, 0.35)
    ctx.set_line_width(1.2)
    ctx.move_to(-30, -36 - bank * 10)
    ctx.line_to(6, -30 - bank * 8)
    ctx.stroke()

    # Engine nacelles
    for ey in (-18, 18):
        nac = cairo.LinearGradient(-5, ey - 5, -5, ey + 5)
        nac.add_color_stop_rgb(0, 0.5, 0.52, 0.55)
        nac.add_color_stop_rgb(1, 0.15, 0.16, 0.18)
        ctx.set_source(nac)
        ctx.rectangle(-18, ey - 4, 28, 8)
        ctx.fill()
        set_rgb(ctx, CHARCOAL, 0.9)
        ctx.arc(-18, ey, 3.5, 0, 2 * math.pi)
        ctx.fill()
        # Exhaust glow
        set_rgb(ctx, AMBER, 0.35)
        ctx.arc(10, ey, 2, 0, 2 * math.pi)
        ctx.fill()

    # Fuselage
    fus = cairo.LinearGradient(0, -8, 0, 8)
    fus.add_color_stop_rgb(0, 0.55, 0.58, 0.62)
    fus.add_color_stop_rgb(0.4, 0.72, 0.74, 0.76)
    fus.add_color_stop_rgb(0.7, 0.35, 0.37, 0.40)
    fus.add_color_stop_rgb(1, 0.12, 0.13, 0.15)
    ctx.set_source(fus)
    ctx.move_to(-62, 0)
    ctx.curve_to(-50, -9, 10, -10, 48, -4)
    ctx.curve_to(62, -2, 64, 0, 58, 2)
    ctx.curve_to(48, 5, 10, 10, -50, 9)
    ctx.curve_to(-58, 5, -62, 2, -62, 0)
    ctx.close_path()
    ctx.fill()

    # Windows row
    set_rgb(ctx, TUNGSTEN, 0.55)
    for i in range(8):
        ctx.rectangle(-20 + i * 7, -3.5, 4, 2.5)
        ctx.fill()

    # Cockpit glass
    glass = cairo.LinearGradient(45, -4, 58, 2)
    glass.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.75)
    glass.add_color_stop_rgba(1, 0.1, 0.15, 0.2, 0.5)
    ctx.set_source(glass)
    ctx.move_to(40, -3)
    ctx.curve_to(50, -5, 58, -2, 60, 0)
    ctx.line_to(52, 2)
    ctx.curve_to(48, 1, 42, 0, 40, 0)
    ctx.close_path()
    ctx.fill()

    # Tail fin
    set_rgb(ctx, (0.3, 0.32, 0.35), 0.95)
    ctx.move_to(-52, 0)
    ctx.line_to(-66, -20)
    ctx.line_to(-48, -3)
    ctx.close_path()
    ctx.fill()
    ctx.move_to(-54, 0)
    ctx.line_to(-62, 12)
    ctx.line_to(-48, 2)
    ctx.close_path()
    ctx.fill()

    # Nav lights
    set_rgb(ctx, BLOOD, 0.85)
    ctx.arc(-32, -36 - bank * 10, 2.2, 0, 2 * math.pi)
    ctx.fill()
    set_rgb(ctx, (0.15, 0.75, 0.35), 0.85)
    ctx.arc(-32, 36 + bank * 10, 2.2, 0, 2 * math.pi)
    ctx.fill()
    set_rgb(ctx, COLD_WHITE, 0.7)
    ctx.arc(58, 0, 1.8, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def draw_plane_trail(ctx: cairo.Context, trail: Sequence[Tuple[float, float, float]]) -> None:
    """Thick fading exhaust / contrail ribbon."""
    if len(trail) < 2:
        return
    for i in range(1, len(trail)):
        x0, y0, a0 = trail[i - 1]
        x1, y1, a1 = trail[i]
        wline = 3.0 + 10.0 * (1.0 - a1)
        set_rgb(ctx, COLD_WHITE, 0.18 * a1)
        ctx.set_line_width(wline)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(x0, y0)
        ctx.line_to(x1, y1)
        ctx.stroke()
        set_rgb(ctx, SLATE, 0.14 * a1)
        ctx.set_line_width(wline * 1.6)
        ctx.move_to(x0, y0 + 2)
        ctx.line_to(x1, y1 + 2)
        ctx.stroke()
        if i % 2 == 0:
            set_rgb(ctx, (0.45, 0.48, 0.52), 0.12 * a1)
            ctx.arc(x1, y1, 4 + 8 * (1 - a1), 0, 2 * math.pi)
            ctx.fill()


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

    # Extra variety: orbital tick marks, danger chevrons
    set_rgb(ctx, BRONZE, 0.4)
    ctx.set_line_width(1.0)
    for i in range(12):
        ang = i * math.pi / 6 + t * 0.05
        r0, r1 = 240, 255
        ctx.move_to(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0)
        ctx.line_to(cx + math.cos(ang) * r1, cy + math.sin(ang) * r1)
        ctx.stroke()
    threat2 = smoothstep(30.0, 55.0, local_t)
    if threat2 > 0.05:
        set_rgb(ctx, BLOOD, 0.35 * threat2 * pulse)
        for k in range(4):
            ang = t * 1.5 + k * math.pi / 2
            px = cx + math.cos(ang) * (40 + threat2 * 30)
            py = cy + math.sin(ang) * (40 + threat2 * 30)
            ctx.move_to(px, py)
            ctx.line_to(px + math.cos(ang + 2.5) * 12, py + math.sin(ang + 2.5) * 12)
            ctx.line_to(px + math.cos(ang - 2.5) * 12, py + math.sin(ang - 2.5) * 12)
            ctx.close_path()
            ctx.fill()


def draw_gun_pillow_scene(
    ctx: cairo.Context,
    w: int,
    h: int,
    t: float,
    local_t: float,
    zoom_t: float,
    fire_t: float = 0.0,
) -> None:
    """Solitary figure resting on giant rifled gun barrel, smoking a cigar; optional muzzle blast."""
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgb(0, 0.04, 0.045, 0.06)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.025)
    ctx.set_source(g)
    ctx.paint()

    win = cairo.LinearGradient(0, 80, w, 200)
    win.add_color_stop_rgba(0, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.0)
    win.add_color_stop_rgba(0.4, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.12)
    win.add_color_stop_rgba(1, TUNGSTEN[0], TUNGSTEN[1], TUNGSTEN[2], 0.0)
    ctx.set_source(win)
    ctx.rectangle(0, 60, w, 140)
    ctx.fill()

    if fire_t > 0:
        flash = clamp(1.0 - fire_t * 2.2)
        set_rgb(ctx, (1.0, 0.75, 0.35), 0.55 * flash)
        ctx.paint()

    z = 1.0 + zoom_t * 3.8
    ctx.save()
    cx, cy = w * 0.55, h * 0.55
    ctx.translate(cx, cy)
    ctx.scale(z, z)
    ctx.translate(-cx, -cy)

    bx0, by0 = -80, h * 0.48
    bw, bh = w * 0.85, 95
    barrel = cairo.LinearGradient(bx0, by0, bx0, by0 + bh)
    barrel.add_color_stop_rgb(0, 0.18, 0.20, 0.22)
    barrel.add_color_stop_rgb(0.35, 0.45, 0.48, 0.52)
    barrel.add_color_stop_rgb(0.5, 0.65, 0.68, 0.72)
    barrel.add_color_stop_rgb(0.65, 0.35, 0.37, 0.40)
    barrel.add_color_stop_rgb(1, 0.10, 0.11, 0.12)
    ctx.set_source(barrel)
    ctx.rectangle(bx0, by0, bw, bh)
    ctx.fill()
    set_rgb(ctx, COLD_WHITE, 0.35)
    ctx.rectangle(bx0, by0 + 18, bw, 6)
    ctx.fill()
    set_rgb(ctx, CHARCOAL, 0.5)
    ctx.rectangle(bx0, by0 + bh - 22, bw, 10)
    ctx.fill()
    set_rgb(ctx, (0.08, 0.08, 0.09), 1)
    ctx.move_to(bx0 + bw - 70, by0)
    ctx.line_to(bx0 + bw - 62, by0 - 18)
    ctx.line_to(bx0 + bw - 54, by0)
    ctx.close_path()
    ctx.fill()

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

    ctx.save()
    ctx.translate(mx, my)
    ctx.scale(0.55, 1.0)
    set_rgb(ctx, (0.01, 0.01, 0.015), 1)
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
    void = cairo.RadialGradient(0, 0, 0, 0, 0, 18)
    void.add_color_stop_rgb(0, 0, 0, 0)
    void.add_color_stop_rgb(1, 0.02, 0.02, 0.03)
    ctx.set_source(void)
    ctx.arc(0, 0, 18, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()

    if 0 < fire_t < 1.8:
        flash = clamp(1.0 - fire_t * 1.8)
        ctx.save()
        ctx.translate(mx + 30, my)
        for k in range(7):
            ang = -0.6 + k * 0.2
            length = (40 + k * 8) * flash
            flame = cairo.LinearGradient(0, 0, math.cos(ang) * length, math.sin(ang) * length)
            flame.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.95 * flash)
            flame.add_color_stop_rgba(0.4, 1, 0.45, 0.1, 0.7 * flash)
            flame.add_color_stop_rgba(1, 0.4, 0.05, 0.0, 0)
            ctx.set_source(flame)
            ctx.move_to(0, -4)
            ctx.line_to(math.cos(ang) * length, math.sin(ang) * length)
            ctx.line_to(0, 4)
            ctx.close_path()
            ctx.fill()
        blast = cairo.RadialGradient(20, 0, 2, 40, 0, 90)
        blast.add_color_stop_rgba(0, 1, 0.9, 0.5, 0.8 * flash)
        blast.add_color_stop_rgba(0.3, 0.9, 0.3, 0.05, 0.35 * flash)
        blast.add_color_stop_rgba(1, 0.2, 0.2, 0.2, 0)
        ctx.set_source(blast)
        ctx.arc(30, 0, 90, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        for i in range(5):
            age = fire_t - i * 0.12
            if age < 0:
                continue
            rr = 30 + age * 120
            set_rgb(ctx, SLATE, max(0, 0.35 - age * 0.18))
            ctx.set_line_width(max(0.5, 8 - age * 3))
            ctx.save()
            ctx.translate(mx + 40 + age * 80, my - age * 20)
            ctx.scale(1.6, 0.7)
            ctx.arc(0, 0, rr, 0, 2 * math.pi)
            ctx.stroke()
            ctx.restore()

    fig_a = 1.0 - smoothstep(0.3, 0.85, zoom_t)
    if fig_a > 0.02:
        ctx.save()
        ctx.translate(mx - 200, by0 + 20)
        ctx.rotate(-0.1)

        set_rgb(ctx, (0.0, 0.0, 0.0), 0.45 * fig_a)
        ctx.save()
        ctx.scale(1.0, 0.35)
        ctx.arc(40, 40, 120, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        set_rgb(ctx, (0.04, 0.04, 0.05), 0.98 * fig_a)
        ctx.set_line_width(14)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(-30, 18)
        ctx.curve_to(-70, 30, -110, 10, -130, -5)
        ctx.stroke()
        ctx.move_to(-30, 22)
        ctx.curve_to(-60, 45, -90, 50, -100, 35)
        ctx.stroke()
        ctx.set_line_width(8)
        ctx.move_to(-130, -5)
        ctx.line_to(-145, -8)
        ctx.stroke()

        set_rgb(ctx, (0.05, 0.05, 0.06), 0.98 * fig_a)
        ctx.move_to(-40, 5)
        ctx.curve_to(-10, 28, 40, 30, 70, 12)
        ctx.curve_to(50, 40, -20, 42, -45, 22)
        ctx.close_path()
        ctx.fill()

        set_rgb(ctx, (0.06, 0.055, 0.05), 0.98 * fig_a)
        ctx.move_to(50, 8)
        ctx.curve_to(90, -25, 140, -35, 175, -18)
        ctx.curve_to(180, 5, 100, 35, 55, 28)
        ctx.close_path()
        ctx.fill()
        set_rgb(ctx, (0.12, 0.10, 0.09), 0.7 * fig_a)
        ctx.move_to(90, -5)
        ctx.line_to(150, -12)
        ctx.line_to(145, 8)
        ctx.line_to(85, 12)
        ctx.close_path()
        ctx.fill()

        set_rgb(ctx, (0.07, 0.06, 0.055), 0.98 * fig_a)
        ctx.set_line_width(11)
        ctx.move_to(100, 0)
        ctx.curve_to(130, -15, 160, -28, 185, -22)
        ctx.stroke()
        ctx.arc(188, -22, 7, 0, 2 * math.pi)
        ctx.fill()

        ctx.set_line_width(10)
        ctx.move_to(80, 15)
        ctx.curve_to(40, 35, -10, 40, -50, 25)
        ctx.stroke()

        set_rgb(ctx, (0.08, 0.07, 0.065), 0.98 * fig_a)
        ctx.set_line_width(12)
        ctx.move_to(165, -15)
        ctx.line_to(195, -28)
        ctx.stroke()
        head = cairo.RadialGradient(205, -38, 4, 210, -32, 30)
        head.add_color_stop_rgb(0, 0.18, 0.15, 0.13)
        head.add_color_stop_rgb(1, 0.04, 0.035, 0.03)
        ctx.set_source(head)
        ctx.save()
        ctx.translate(210, -34)
        ctx.scale(1.15, 1.0)
        ctx.arc(0, 0, 26, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        set_rgb(ctx, (0.12, 0.10, 0.09), 0.8 * fig_a)
        ctx.set_line_width(2)
        ctx.move_to(228, -34)
        ctx.line_to(238, -30)
        ctx.stroke()
        ctx.move_to(218, -38)
        ctx.curve_to(224, -40, 230, -39, 234, -36)
        ctx.stroke()
        set_rgb(ctx, (0.02, 0.02, 0.025), 0.95 * fig_a)
        ctx.move_to(190, -45)
        ctx.curve_to(200, -62, 230, -60, 235, -40)
        ctx.line_to(220, -42)
        ctx.close_path()
        ctx.fill()
        set_rgb(ctx, (0.1, 0.08, 0.07), 0.9 * fig_a)
        ctx.arc(198, -32, 5, 0, 2 * math.pi)
        ctx.fill()

        cigar_x, cigar_y = 240, -28
        set_rgb(ctx, BRONZE, 0.95 * fig_a)
        ctx.set_line_width(4.5)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(232, -30)
        ctx.line_to(258, -26)
        ctx.stroke()
        set_rgb(ctx, (0.35, 0.35, 0.32), 0.9 * fig_a)
        ctx.arc(258, -26, 2.5, 0, 2 * math.pi)
        ctx.fill()
        ember = 0.6 + 0.4 * math.sin(t * 8)
        set_rgb(ctx, (1.0, 0.35, 0.05), ember * fig_a)
        ctx.arc(256, -26, 2.2, 0, 2 * math.pi)
        ctx.fill()
        set_rgb(ctx, AMBER, 0.7 * ember * fig_a)
        ctx.arc(255, -26, 1.2, 0, 2 * math.pi)
        ctx.fill()

        for i in range(5):
            sy = cigar_y - 8 - i * 14 - (t * 18 + i * 7) % 40
            sx = cigar_x + 16 + math.sin(t * 1.5 + i) * 8 + i * 3
            set_rgb(ctx, SLATE, (0.22 - i * 0.03) * fig_a)
            ctx.save()
            ctx.translate(sx, sy)
            ctx.scale(1.0 + i * 0.3, 1.4)
            ctx.arc(0, 0, 5 + i * 1.5, 0, 2 * math.pi)
            ctx.fill()
            ctx.restore()

        if zoom_t < 0.4:
            set_rgb(ctx, TUNGSTEN, 0.12 * fig_a)
            ctx.arc(120, -5, 14, 0, 2 * math.pi)
            ctx.fill()

        ctx.restore()

    ctx.restore()

    set_rgb(ctx, COLD_WHITE, 0.15)
    for i in range(20):
        px = (math.sin(t * 0.3 + i * 1.7) * 0.5 + 0.5) * w
        py = 90 + (i * 37 + t * 12) % 200
        ctx.arc(px, py, 1.2, 0, 2 * math.pi)
        ctx.fill()


def draw_razor_wire_scene(ctx: cairo.Context, w: int, h: int, t: float, local_t: float) -> None:
    """Unmistakable straight-razor macro: handle, spine, cutting edge + wire walker below."""
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgb(0, 0.18, 0.22, 0.28)
    g.add_color_stop_rgb(0.35, 0.08, 0.09, 0.11)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.03)
    ctx.set_source(g)
    ctx.paint()

    blade_y = h * 0.32
    ctx.save()
    ctx.translate(40, blade_y + 30)
    ctx.rotate(-0.08)
    handle = cairo.LinearGradient(0, -25, 0, 25)
    handle.add_color_stop_rgb(0, 0.25, 0.14, 0.08)
    handle.add_color_stop_rgb(0.5, 0.45, 0.28, 0.14)
    handle.add_color_stop_rgb(1, 0.12, 0.07, 0.04)
    ctx.set_source(handle)
    ctx.rectangle(0, -22, 160, 44)
    ctx.fill()
    set_rgb(ctx, STEEL, 0.9)
    ctx.arc(150, 0, 6, 0, 2 * math.pi)
    ctx.fill()
    set_rgb(ctx, CHARCOAL, 1)
    ctx.arc(150, 0, 2.5, 0, 2 * math.pi)
    ctx.fill()
    set_rgb(ctx, BRONZE, 0.4)
    ctx.set_line_width(1.5)
    ctx.move_to(4, -20)
    ctx.line_to(155, -20)
    ctx.stroke()
    ctx.restore()

    tip_x = w - 30
    spine_y = blade_y - 8
    edge_y = blade_y + 78
    blade = cairo.LinearGradient(0, spine_y, 0, edge_y)
    blade.add_color_stop_rgb(0.0, 0.55, 0.58, 0.62)
    blade.add_color_stop_rgb(0.15, 0.78, 0.82, 0.86)
    blade.add_color_stop_rgb(0.45, 0.95, 0.96, 0.97)
    blade.add_color_stop_rgb(0.72, 0.55, 0.58, 0.62)
    blade.add_color_stop_rgb(0.92, 0.25, 0.26, 0.28)
    blade.add_color_stop_rgb(1.0, 0.92, 0.94, 0.96)
    ctx.set_source(blade)
    ctx.move_to(180, spine_y + 10)
    ctx.line_to(tip_x - 40, spine_y)
    ctx.line_to(tip_x, spine_y + 18)
    ctx.line_to(tip_x - 20, edge_y)
    ctx.line_to(200, edge_y + 6)
    ctx.line_to(180, spine_y + 35)
    ctx.close_path()
    ctx.fill()

    set_rgb(ctx, COLD_WHITE, 0.55)
    ctx.set_line_width(2.5)
    ctx.move_to(185, spine_y + 10)
    ctx.line_to(tip_x - 40, spine_y)
    ctx.stroke()

    set_rgb(ctx, (1, 1, 1), 0.98)
    ctx.set_line_width(2.0)
    ctx.move_to(200, edge_y + 5)
    ctx.line_to(tip_x - 20, edge_y)
    ctx.stroke()
    set_rgb(ctx, TUNGSTEN, 0.5)
    ctx.set_line_width(4)
    ctx.move_to(205, edge_y - 10)
    ctx.line_to(tip_x - 25, edge_y - 14)
    ctx.stroke()

    set_rgb(ctx, COLD_WHITE, 0.35)
    ctx.set_line_width(6)
    ctx.move_to(220, blade_y + 20)
    ctx.line_to(tip_x - 60, blade_y + 8)
    ctx.stroke()

    set_rgb(ctx, STEEL, 0.25)
    ctx.set_line_width(1.2)
    ctx.arc(w * 0.55, blade_y + 30, 90, 0.15, math.pi - 0.4)
    ctx.stroke()

    wire_y = h * 0.78
    walker_x = 100 + ((t * 42) % (w - 200))
    vib = math.sin(t * 48) * (1.0 + 2.0 * abs(math.sin(t * 2.5)))

    for px in (70, w - 70):
        post = cairo.LinearGradient(px - 10, wire_y - 50, px + 10, wire_y + 40)
        post.add_color_stop_rgb(0, 0.4, 0.42, 0.45)
        post.add_color_stop_rgb(1, 0.12, 0.12, 0.14)
        ctx.set_source(post)
        ctx.rectangle(px - 10, wire_y - 50, 20, 90)
        ctx.fill()
        set_rgb(ctx, BRONZE, 0.7)
        ctx.rectangle(px - 14, wire_y - 8, 28, 10)
        ctx.fill()

    set_rgb(ctx, (0.75, 0.78, 0.82), 0.95)
    ctx.set_line_width(1.6)
    ctx.move_to(70, wire_y)
    for x in range(70, w - 70, 3):
        dist = abs(x - walker_x)
        local_vib = vib * math.exp(-dist * 0.035) * 10
        ctx.line_to(x, wire_y + local_vib)
    ctx.line_to(w - 70, wire_y)
    ctx.stroke()
    set_rgb(ctx, AMBER, 0.25)
    ctx.set_line_width(0.8)
    ctx.move_to(70, wire_y - 1)
    ctx.line_to(w - 70, wire_y - 1)
    ctx.stroke()

    dist_phase = (t * 42) % 18
    step = 1 if dist_phase < 3 else 0
    # Larger walker so the "tiny silhouette on the wire" still reads at 1080p
    wx, wy = walker_x, wire_y - 55 - step * 3
    set_rgb(ctx, AMBER, 0.5)
    ctx.arc(wx, wire_y, 7, 0, 2 * math.pi)
    ctx.fill()
    set_rgb(ctx, (0.02, 0.02, 0.03), 1)
    ctx.set_line_width(5)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(wx, wy + 14)
    ctx.line_to(wx - 12 - step * 4, wire_y - 2)
    ctx.move_to(wx, wy + 14)
    ctx.line_to(wx + 11 + (1 - step) * 4, wire_y - 2)
    ctx.stroke()
    ctx.set_line_width(11)
    ctx.move_to(wx, wy + 14)
    ctx.line_to(wx, wy - 10)
    ctx.stroke()
    set_rgb(ctx, (0.03, 0.03, 0.04), 1)
    ctx.move_to(wx - 14, wy - 4)
    ctx.line_to(wx, wy - 18)
    ctx.line_to(wx + 14, wy - 4)
    ctx.line_to(wx + 11, wy + 12)
    ctx.line_to(wx - 11, wy + 12)
    ctx.close_path()
    ctx.fill()
    ctx.arc(wx, wy - 28, 10, 0, 2 * math.pi)
    ctx.fill()
    # Fedora
    ctx.rectangle(wx - 14, wy - 36, 28, 4)
    ctx.fill()
    ctx.arc(wx, wy - 36, 11, math.pi, 2 * math.pi)
    ctx.fill()
    set_rgb(ctx, STEEL, 0.9)
    ctx.set_line_width(2.2)
    ctx.move_to(wx - 42, wy - 8)
    ctx.line_to(wx + 42, wy - 14)
    ctx.stroke()
    set_rgb(ctx, (0.02, 0.02, 0.03), 1)
    ctx.set_line_width(3.5)
    ctx.move_to(wx, wy - 12)
    ctx.line_to(wx - 24, wy - 9)
    ctx.move_to(wx, wy - 12)
    ctx.line_to(wx + 24, wy - 12)
    ctx.stroke()

    set_rgb(ctx, BLOOD, 0.08)
    ctx.rectangle(0, edge_y, w, max(1, wire_y - edge_y - 40))
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
        self._gun_fired = False
        self._fibers_left = 12
        coats = ["trench", "coat", "jacket", "raincoat", "overcoat"]
        hairs = ["short", "long", "buzz", "bun", "bald"]
        hats = ["none", "fedora", "cap", "beanie", "bowler", "none"]
        builds = ["slim", "avg", "heavy"]
        self._commuters = []
        for i in range(9):
            self._commuters.append(
                {
                    "x": random.uniform(-120, WIDTH + 120),
                    "speed": random.uniform(26, 58),
                    "phase": random.uniform(0, 10),
                    "scale": random.uniform(0.82, 1.22),
                    "facing": 1 if i % 3 else -1,
                    "style": {
                        "coat": coats[i % len(coats)],
                        "hair": hairs[i % len(hairs)],
                        "hat": hats[(i * 2) % len(hats)] if hairs[i % len(hairs)] != "bun" else "none",
                        "build": builds[i % len(builds)],
                        "bag": i % 3 == 0,
                        "facing": 1 if i % 3 else -1,
                    },
                }
            )
        # Scene 2 aircraft
        self._planes = [
            {"x": -200.0, "y": 150.0, "vx": 100.0, "vy": 5.0, "scale": 1.55, "bank": 0.12, "trail": [], "delay": 1.0},
            {"x": WIDTH + 220.0, "y": 230.0, "vx": -120.0, "vy": -7.0, "scale": 1.25, "bank": -0.18, "trail": [], "delay": 8.0},
            {"x": -280.0, "y": 310.0, "vx": 85.0, "vy": -12.0, "scale": 1.85, "bank": 0.08, "trail": [], "delay": 18.0},
            {"x": WIDTH + 300.0, "y": 110.0, "vx": -75.0, "vy": 9.0, "scale": 1.05, "bank": 0.22, "trail": [], "delay": 32.0},
            {"x": -350.0, "y": 200.0, "vx": 130.0, "vy": 2.0, "scale": 0.95, "bank": -0.1, "trail": [], "delay": 45.0},
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
            self._gun_fired = False
            self._fibers_left = 12
            parts.shards.clear()
            parts.dust.clear()
            parts.fiber_bits.clear()
            cam.target_zoom = 1.0
            cam.zoom = 1.0
            for p in self._planes:
                p["trail"] = []
                if p["vx"] > 0:
                    p["x"] = -200.0 - abs(p["delay"]) * 10
                else:
                    p["x"] = WIDTH + 220.0 + abs(p["delay"]) * 10

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
            # Sustained shake / aberration during muzzle blast
            if t >= S3_FIRE:
                fire_age = t - S3_FIRE
                if fire_age < 2.0:
                    cam.impulse(18 * max(0.0, 1.0 - fire_age * 0.7))
                    aberrate = 1.6 * max(0.0, 1.0 - fire_age * 0.5)
                    grain = 0.7
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
            direction = c["style"].get("facing", 1)
            c["x"] += c["speed"] * dt * direction
            if direction > 0 and c["x"] > WIDTH + 100:
                c["x"] = -100
                c["scale"] = random.uniform(0.82, 1.22)
                c["speed"] = random.uniform(26, 58)
            elif direction < 0 and c["x"] < -100:
                c["x"] = WIDTH + 100
                c["scale"] = random.uniform(0.82, 1.22)
                c["speed"] = random.uniform(26, 58)
            phase = t * 3.2 + c["phase"]
            draw_hollow_silhouette(
                ctx,
                c["x"] - cam_x * 0.15,
                ground_y,
                c["scale"],
                t,
                phase,
                xray,
                style=c["style"],
            )

        # Rain
        self.particles.spawn_rain(5, wind=-1.5)
        if random.random() < 0.08:
            self.particles.spawn_smoke(random.uniform(0, WIDTH), ground_y - 20)

    def _scene2(self, ctx: cairo.Context, t: float, dt: float) -> None:
        local = t - S1_END
        self.canvas.clear()
        pan = smoothstep(0, 8, local)
        draw_noir_sky(ctx, WIDTH, HEIGHT, t, dusk=0.7)
        if pan < 0.95:
            ctx.save()
            ctx.translate(0, pan * HEIGHT * 0.55)
            draw_city_skyline(ctx, WIDTH, HEIGHT, t, local * 5)
            ctx.restore()
        draw_atom_loom(ctx, WIDTH, HEIGHT, t, local)

        # Aircraft looping past the atom with smoke / contrails
        for i, p in enumerate(self._planes):
            if local < p["delay"]:
                continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt + math.sin(t * 1.2 + i) * 8 * dt
            # Recycle off-screen
            if p["vx"] > 0 and p["x"] > WIDTH + 260:
                p["x"] = -260
                p["y"] = 120 + (i * 70) % 280
                p["trail"] = []
            elif p["vx"] < 0 and p["x"] < -260:
                p["x"] = WIDTH + 260
                p["y"] = 100 + (i * 85) % 300
                p["trail"] = []
            # Trail points (engine exhaust slightly behind)
            heading = 0.0 if p["vx"] > 0 else math.pi
            heading += math.atan2(p["vy"], abs(p["vx"])) * (1 if p["vx"] > 0 else -1) * 0.5
            ex = p["x"] - math.cos(heading) * 50 * p["scale"]
            ey = p["y"] - math.sin(heading) * 8
            p["trail"].append((ex, ey, 1.0))
            # Fade & trim
            p["trail"] = [(x, y, a - dt * 0.55) for x, y, a in p["trail"] if a - dt * 0.55 > 0.05][-80:]
            draw_plane_trail(ctx, p["trail"])
            draw_airplane(ctx, p["x"], p["y"], p["scale"], heading, bank=p["bank"])
            # Occasional engine smoke puffs into particle system
            if random.random() < 0.15:
                self.particles.spawn_smoke(ex, ey)

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
        fire_t = max(0.0, t - S3_FIRE) if t >= S3_FIRE else 0.0

        if t < S3_FIRE + 0.15:
            # Hold on barrel (with smoker) through zoom, fire at S3_FIRE
            zoom_t = smoothstep(S3_BARREL_ZOOM - S2_END, S3_FIRE - S2_END, local)
            # Keep enough frame to read the smoker + muzzle blast (don't bury flash in bore)
            zoom_t = min(zoom_t, 0.48)
            if t >= S3_FIRE and not self._gun_fired:
                self._gun_fired = True
                self.camera.impulse(22)
                # Blast smoke into particle world
                for _ in range(18):
                    self.particles.spawn_smoke(
                        WIDTH * 0.78 + random.uniform(-20, 40),
                        HEIGHT * 0.52 + random.uniform(-30, 30),
                    )
                    self.particles.dust.append(
                        DustMote(
                            x=WIDTH * 0.8 + random.uniform(-30, 30),
                            y=HEIGHT * 0.5 + random.uniform(-20, 20),
                            vx=random.uniform(40, 160),
                            vy=random.uniform(-60, 40),
                            r=random.uniform(1.5, 4.0),
                            life=random.uniform(0.8, 1.8),
                            max_life=1.8,
                            color=random.choice([AMBER, STEEL, SLATE]),
                        )
                    )
            draw_gun_pillow_scene(ctx, WIDTH, HEIGHT, t, local, zoom_t, fire_t=fire_t)
        elif t < S3_RAZOR:
            # Brief aftershock — pull back slightly so blast smoke reads
            zoom_t = 0.55
            draw_gun_pillow_scene(ctx, WIDTH, HEIGHT, t, local, zoom_t, fire_t=fire_t)
            for _ in range(2):
                self.particles.spawn_smoke(
                    WIDTH * 0.82 + random.uniform(-10, 60),
                    HEIGHT * 0.5 + random.uniform(-40, 20),
                )
        else:
            blend = smoothstep(S3_RAZOR, S3_RAZOR + 1.5, t)
            if blend < 1:
                draw_gun_pillow_scene(ctx, WIDTH, HEIGHT, t, local, 1.0, fire_t=fire_t)
                set_rgb(ctx, CHARCOAL, blend * 0.9)
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
