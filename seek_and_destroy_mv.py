#!/usr/bin/env python3
"""Seek & Destroy — Narayan Gopal x Metallica Himalayan music-video animation.

Playback:
    python seek_and_destroy_mv.py

Export to MP4 (requires ffmpeg):
    python seek_and_destroy_mv.py --export
    python seek_and_destroy_mv.py --export --no-preview -o out.mp4
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from pathlib import Path

import cairo
import pygame

# ==============================================================================
# 1. TIMELINE, BPM & CONSTANTS
# ==============================================================================
WINDOW_W, WINDOW_H = 1080, 720
FPS = 60
BPM = 72.0
BEAT_FREQ = BPM / 60.0  # 1.2 Hz
SONG_DURATION = 313.0   # 5m 13s
SINGING_START_TIME = 33.0

SCRIPT_DIR = Path(__file__).resolve().parent
AUDIO_FILE = SCRIPT_DIR / "seek_and_destroy_nepali.mp3"
# Backward-compatible typo from earlier builds
AUDIO_FILE_ALT = SCRIPT_DIR / "seek_and_destory_nepali.mp3"
DEFAULT_EXPORT_PATH = SCRIPT_DIR / "seek_and_destroy.mp4"

COLOR_SKIN = (0.88, 0.72, 0.58)
COLOR_GOLD = (0.95, 0.78, 0.22)
COLOR_WHITE = (0.95, 0.95, 0.95)
COLOR_DARK = (0.12, 0.12, 0.14)


def resolve_audio_path() -> Path | None:
    if AUDIO_FILE.is_file():
        return AUDIO_FILE
    if AUDIO_FILE_ALT.is_file():
        return AUDIO_FILE_ALT
    return None


# ==============================================================================
# FFMPEG EXPORT
# ==============================================================================
class FfmpegRecorder:
    """Pipe raw RGB frames to ffmpeg and mux optional audio into an MP4."""

    def __init__(self, output_path, fps=FPS, width=WINDOW_W, height=WINDOW_H, audio_path=None):
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

        cmd.extend([
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
        ])
        if self._has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.extend(["-t", str(SONG_DURATION)])
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Seek & Destroy — Narayan Gopal x Metallica Himalayan MV",
    )
    parser.add_argument(
        "--export", "-e", action="store_true",
        help="Render to MP4 via ffmpeg pipe instead of interactive playback",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=DEFAULT_EXPORT_PATH,
        help=f"Output MP4 path (default: {DEFAULT_EXPORT_PATH.name})",
    )
    parser.add_argument(
        "--no-preview", action="store_true",
        help="Headless export (no window); sets SDL_VIDEODRIVER=dummy",
    )
    parser.add_argument(
        "--hud", action="store_true",
        help="Include on-screen HUD in exported video (hidden by default)",
    )
    return parser.parse_args()


# ==============================================================================
# 2. VECTOR BACKGROUND: HIMALAYAS, STUPA, PAGODA & MOON
# ==============================================================================
class HimalayanStageRenderer:
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)
        self._stars = [
            (95, 55, 1.1), (168, 92, 0.9), (240, 48, 1.3), (310, 118, 0.8),
            (390, 70, 1.0), (470, 40, 1.4), (545, 105, 0.9), (620, 62, 1.1),
            (700, 88, 0.8), (780, 45, 1.2), (845, 120, 0.7), (930, 70, 1.0),
            (1005, 95, 0.9), (1050, 50, 1.1), (50, 140, 0.7), (880, 35, 0.8),
        ]

    def draw_background(self, t, camera_x=0.0):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        ctx.save()
        ctx.translate(-camera_x * 0.25, 0)

        self._draw_sky(ctx)
        self._draw_moon(ctx, t)
        self._draw_stars(ctx, t)
        self._draw_distant_haze(ctx)
        self._draw_mountain_layers(ctx)
        self.draw_stupa(ctx, 150, 455, t)
        self.draw_pagoda(ctx, 930, 455, t)
        self._draw_courtyard_floor(ctx)
        self._draw_oil_lamps(ctx, t)

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")

    def _draw_sky(self, ctx):
        sky = cairo.LinearGradient(0, 0, 0, self.h)
        sky.add_color_stop_rgb(0.00, 0.03, 0.04, 0.12)
        sky.add_color_stop_rgb(0.35, 0.07, 0.08, 0.20)
        sky.add_color_stop_rgb(0.62, 0.14, 0.12, 0.24)
        sky.add_color_stop_rgb(0.82, 0.22, 0.16, 0.26)
        sky.add_color_stop_rgb(1.00, 0.28, 0.18, 0.22)
        ctx.set_source(sky)
        ctx.paint()

    def _draw_moon(self, ctx, t):
        mx, my, r = 860, 118, 46
        # Soft atmospheric glow rings
        for i, (rad, a) in enumerate([(96, 0.04), (78, 0.07), (62, 0.12)]):
            glow = cairo.RadialGradient(mx, my, r * 0.4, mx, my, rad)
            glow.add_color_stop_rgba(0.0, 1.0, 0.96, 0.82, a + 0.02)
            glow.add_color_stop_rgba(1.0, 0.7, 0.75, 0.95, 0.0)
            ctx.set_source(glow)
            ctx.arc(mx, my, rad, 0, 2 * math.pi)
            ctx.fill()

        # Moon disk with subtle warm gradient
        moon = cairo.RadialGradient(mx - 12, my - 10, 4, mx, my, r)
        moon.add_color_stop_rgb(0.0, 1.00, 0.98, 0.92)
        moon.add_color_stop_rgb(0.55, 0.96, 0.93, 0.84)
        moon.add_color_stop_rgb(1.0, 0.82, 0.80, 0.72)
        ctx.set_source(moon)
        ctx.arc(mx, my, r, 0, 2 * math.pi)
        ctx.fill()

        # Craters (maria) — quiet, low-contrast
        ctx.set_source_rgba(0.72, 0.70, 0.64, 0.35)
        for cx, cy, cr in [(-14, -8, 9), (10, 6, 7), (-4, 14, 5), (16, -12, 4), (2, -18, 3.5)]:
            ctx.arc(mx + cx, my + cy, cr, 0, 2 * math.pi)
            ctx.fill()
        ctx.set_source_rgba(0.88, 0.86, 0.80, 0.25)
        for cx, cy, cr in [(-10, -6, 4), (12, 8, 3)]:
            ctx.arc(mx + cx, my + cy, cr, 0, 2 * math.pi)
            ctx.fill()

        # Terminator shade on the left edge
        shade = cairo.RadialGradient(mx + 18, my - 6, 8, mx - 8, my, r)
        shade.add_color_stop_rgba(0.0, 0.55, 0.55, 0.58, 0.0)
        shade.add_color_stop_rgba(1.0, 0.35, 0.38, 0.48, 0.22)
        ctx.set_source(shade)
        ctx.arc(mx, my, r, 0, 2 * math.pi)
        ctx.fill()

        # Slow shimmer along rim
        shimmer = 0.08 + 0.04 * math.sin(t * 0.7)
        ctx.set_source_rgba(1.0, 0.98, 0.90, shimmer)
        ctx.set_line_width(1.5)
        ctx.arc(mx, my, r - 0.8, -0.4, 1.2)
        ctx.stroke()

    def _draw_stars(self, ctx, t):
        for i, (sx, sy, base) in enumerate(self._stars):
            twinkle = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * (2.2 + (i % 5) * 0.35) + i * 1.7))
            ctx.set_source_rgba(1.0, 0.98, 0.92, 0.35 + twinkle * 0.55)
            ctx.arc(sx, sy, base * (0.7 + twinkle * 0.6), 0, 2 * math.pi)
            ctx.fill()

    def _draw_distant_haze(self, ctx):
        haze = cairo.LinearGradient(0, 250, 0, 420)
        haze.add_color_stop_rgba(0.0, 0.35, 0.38, 0.55, 0.0)
        haze.add_color_stop_rgba(0.6, 0.40, 0.35, 0.48, 0.12)
        haze.add_color_stop_rgba(1.0, 0.45, 0.32, 0.38, 0.22)
        ctx.set_source(haze)
        ctx.rectangle(-120, 250, self.w + 340, 180)
        ctx.fill()

    def _draw_mountain_layers(self, ctx):
        """Hand-shaped Himalayan massifs — broad shoulders, soft snow, no tent cones."""
        # Far atmospheric wall (gentle rolls)
        self._paint_massif(ctx, [
            (-180, 400), (-20, 375), (120, 390), (280, 365), (440, 385),
            (600, 360), (760, 380), (920, 355), (1080, 375), (1320, 385),
        ], rock=(0.12, 0.14, 0.24), snow=0.15)

        # Mid range — long rolling crest, shallow cols
        self._paint_massif(ctx, [
            (-180, 425), (-40, 395), (80, 410), (220, 375), (360, 400),
            (500, 355), (640, 385), (780, 340), (920, 375), (1060, 350),
            (1200, 380), (1320, 400),
        ], rock=(0.17, 0.21, 0.34), snow=0.45)

        # Near range — broad massifs / shoulders (avoid steep isolated spikes)
        self._paint_massif(ctx, [
            (-180, 448), (-20, 415), (100, 435), (240, 390), (380, 420),
            (500, 360), (560, 355), (620, 365),  # wide shoulder plateau
            (720, 325), (780, 330), (840, 355),  # broad main summit
            (960, 345), (1040, 360), (1140, 340), (1240, 370), (1320, 415),
        ], rock=(0.23, 0.27, 0.41), snow=0.72)

        # Soft foothill roll
        self._paint_massif(ctx, [
            (-180, 458), (0, 448), (160, 455), (340, 442), (520, 452),
            (700, 440), (880, 450), (1060, 442), (1320, 455),
        ], rock=(0.14, 0.16, 0.24), snow=0.0)

    def _paint_massif(self, ctx, ridge, rock, snow):
        # Densify with soft midpoints so the silhouette rolls instead of tents
        pts = []
        for i, (x, y) in enumerate(ridge):
            pts.append((float(x), float(y)))
            if i < len(ridge) - 1:
                x1, y1 = ridge[i + 1]
                for t, drop in ((0.28, 0.08), (0.5, 0.11), (0.72, 0.07)):
                    ix = x + (x1 - x) * t
                    iy = y + (y1 - y) * t
                    # Pull midpoints down into saddles (broadens peaks)
                    iy += abs(x1 - x) * drop + 4
                    # Tiny ridge notches for crag without making cones
                    iy += 3.5 * math.sin(ix * 0.07 + i * 1.3)
                    pts.append((ix, iy))

        ymin = min(p[1] for p in pts)

        def trace():
            ctx.move_to(pts[0][0], self.h)
            ctx.line_to(*pts[0])
            for i in range(len(pts) - 1):
                x0, y0 = pts[i]
                x1, y1 = pts[i + 1]
                dx = x1 - x0
                ctx.curve_to(x0 + dx * 0.5, y0, x1 - dx * 0.5, y1, x1, y1)
            ctx.line_to(pts[-1][0], self.h)
            ctx.close_path()

        trace()
        body = cairo.LinearGradient(0, ymin, 0, 470)
        body.add_color_stop_rgb(0.0, min(1, rock[0] * 1.2), min(1, rock[1] * 1.15), min(1, rock[2] * 1.1))
        body.add_color_stop_rgb(0.55, *rock)
        body.add_color_stop_rgb(1.0, rock[0] * 0.7, rock[1] * 0.7, rock[2] * 0.75)
        ctx.set_source(body)
        ctx.fill()

        if snow <= 0.01:
            return

        # Elevation snow wash only — no per-peak white caps (those read as tent tops)
        ctx.save()
        trace()
        ctx.clip()
        snow_g = cairo.LinearGradient(0, ymin - 6, 0, ymin + 155)
        a = snow
        snow_g.add_color_stop_rgba(0.00, 0.97, 0.98, 1.00, 0.88 * a)
        snow_g.add_color_stop_rgba(0.18, 0.90, 0.92, 0.96, 0.50 * a)
        snow_g.add_color_stop_rgba(0.45, 0.48, 0.52, 0.64, 0.14 * a)
        snow_g.add_color_stop_rgba(1.00, 0, 0, 0, 0.0)
        ctx.set_source(snow_g)
        ctx.paint()

        # Couloir / face shade — long diagonal strokes, not crater dots
        for i in range(3, len(pts) - 3, 5):
            x0, y0 = pts[i]
            x1, y1 = pts[min(i + 2, len(pts) - 1)]
            ctx.set_source_rgba(0.10, 0.12, 0.20, 0.14 * a)
            ctx.move_to(x0 + 2, y0 + 6)
            ctx.line_to(x1 + 8, y1 + 12)
            ctx.line_to((x0 + x1) * 0.5 + 25, max(y0, y1) + 70)
            ctx.close_path()
            ctx.fill()
        ctx.restore()

        # Thin bright crest highlight along the ridgeline
        ctx.set_source_rgba(0.95, 0.96, 0.98, 0.35 * snow)
        ctx.set_line_width(2.2)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(*pts[0])
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            dx = x1 - x0
            ctx.curve_to(x0 + dx * 0.5, y0, x1 - dx * 0.5, y1, x1, y1)
        ctx.stroke()

    def _draw_courtyard_floor(self, ctx):
        """Traditional Nepali brick / stone courtyard (Durbar-square style)."""
        floor_y = 455
        # Base terracotta clay wash
        base = cairo.LinearGradient(0, floor_y, 0, self.h)
        base.add_color_stop_rgb(0.0, 0.42, 0.28, 0.20)
        base.add_color_stop_rgb(0.45, 0.36, 0.24, 0.17)
        base.add_color_stop_rgb(1.0, 0.28, 0.18, 0.13)
        ctx.set_source(base)
        ctx.rectangle(-120, floor_y, self.w + 340, self.h - floor_y + 20)
        ctx.fill()

        # Horizon stone curb
        ctx.set_source_rgb(0.55, 0.48, 0.38)
        ctx.rectangle(-120, floor_y, self.w + 340, 8)
        ctx.fill()
        ctx.set_source_rgb(0.38, 0.32, 0.26)
        ctx.rectangle(-120, floor_y + 8, self.w + 340, 3)
        ctx.fill()

        # Perspective brick courses (running bond, weathered terracotta)
        brick_h = 15
        for row, y in enumerate(range(floor_y + 14, self.h + 20, brick_h)):
            # Slight perspective: bricks widen toward camera
            depth = (y - floor_y) / max(1, self.h - floor_y)
            brick_w = int(48 + depth * 16)
            offset = (row % 2) * (brick_w // 2)
            ctx.set_source_rgb(0.28, 0.20, 0.14)
            ctx.rectangle(-120, y, self.w + 340, 2)
            ctx.fill()
            x = -120 + offset
            col = 0
            while x < self.w + 220:
                # Varied kiln-fired brick tones
                n = (col * 17 + row * 31) % 5
                tones = [
                    (0.54, 0.33, 0.22),
                    (0.48, 0.28, 0.18),
                    (0.58, 0.36, 0.24),
                    (0.50, 0.30, 0.20),
                    (0.45, 0.26, 0.17),
                ]
                r, g, b = tones[n]
                # Darken slightly with depth
                r *= 1.0 - depth * 0.12
                g *= 1.0 - depth * 0.12
                b *= 1.0 - depth * 0.10
                ctx.set_source_rgb(r, g, b)
                ctx.rectangle(x + 1, y + 2, brick_w - 4, brick_h - 4)
                ctx.fill()
                # Top highlight / wear
                ctx.set_source_rgba(0.72, 0.52, 0.36, 0.28)
                ctx.rectangle(x + 1, y + 2, brick_w - 4, 2)
                ctx.fill()
                # Mortar joint
                ctx.set_source_rgb(0.28, 0.20, 0.14)
                ctx.rectangle(x + brick_w - 3, y + 2, 3, brick_h - 4)
                ctx.fill()
                x += brick_w
                col += 1

        # Central carved stone lotus (subtle floor inlay, not a prop)
        cx, cy = self.w / 2, floor_y + 135
        ctx.set_source_rgb(0.40, 0.32, 0.24)
        ctx.arc(cx, cy, 38, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.48, 0.40, 0.30)
        ctx.arc(cx, cy, 30, 0, 2 * math.pi)
        ctx.fill()
        for i in range(8):
            ang = i * math.pi / 4 - math.pi / 2
            px = cx + math.cos(ang) * 16
            py = cy + math.sin(ang) * 16
            ctx.set_source_rgb(0.36 if i % 2 == 0 else 0.44, 0.30, 0.22)
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(ang + math.pi / 2)
            ctx.scale(1.0, 1.4)
            ctx.arc(0, 0, 7, 0, 2 * math.pi)
            ctx.fill()
            ctx.restore()
        ctx.set_source_rgb(0.55, 0.45, 0.32)
        ctx.arc(cx, cy, 7, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(0.28, 0.22, 0.16, 0.7)
        ctx.set_line_width(1.5)
        ctx.arc(cx, cy, 38, 0, 2 * math.pi)
        ctx.stroke()

        # Weathered stone pavers near temple bases (irregular slabs)
        for bx, by, bw, bh in [
            (70, floor_y + 20, 85, 32), (185, floor_y + 24, 70, 28),
            (840, floor_y + 22, 80, 30), (960, floor_y + 20, 75, 34),
        ]:
            ctx.set_source_rgb(0.52, 0.46, 0.38)
            ctx.rectangle(bx, by, bw, bh)
            ctx.fill()
            ctx.set_source_rgb(0.36, 0.30, 0.24)
            ctx.set_line_width(1.5)
            ctx.rectangle(bx, by, bw, bh)
            ctx.stroke()
            ctx.set_source_rgba(0.65, 0.58, 0.48, 0.35)
            ctx.rectangle(bx + 2, by + 2, bw - 4, 4)
            ctx.fill()

    def _draw_oil_lamps(self, ctx, t):
        for lx in (70, 280, 800, 1010):
            ly = 448
            ctx.set_source_rgb(0.35, 0.22, 0.12)
            ctx.rectangle(lx - 5, ly - 8, 10, 10)
            ctx.fill()
            flick = math.sin(t * 11.0 + lx * 0.1) * 2
            ctx.set_source_rgba(1.0, 0.55, 0.12, 0.55)
            ctx.arc(lx + flick * 0.3, ly - 16, 10, 0, 2 * math.pi)
            ctx.fill()
            ctx.set_source_rgb(1.0, 0.85, 0.35)
            ctx.move_to(lx, ly - 8)
            ctx.curve_to(lx + 4 + flick, ly - 18, lx - 2, ly - 24, lx, ly - 28)
            ctx.curve_to(lx + 2, ly - 22, lx - 4 + flick, ly - 16, lx, ly - 8)
            ctx.fill()

    def draw_stupa(self, ctx, x, y, t=0.0):
        """Boudhanath / Swayambhu inspired white stupa with Buddha eyes."""
        ctx.save()
        ctx.translate(x, y)

        # Stepped plinth (medhi)
        for i, (w, h, col) in enumerate([
            (170, 18, (0.55, 0.45, 0.32)),
            (145, 14, (0.62, 0.52, 0.38)),
            (120, 12, (0.58, 0.48, 0.35)),
        ]):
            yy = -sum([18, 14, 12][:i])
            ctx.set_source_rgb(*col)
            ctx.rectangle(-w / 2, yy - h, w, h)
            ctx.fill()
            ctx.set_source_rgba(0.3, 0.25, 0.18, 0.35)
            ctx.rectangle(-w / 2, yy - 2, w, 2)
            ctx.fill()

        # Dome (anda / garbha) with volume shading
        dome_y = -44
        dome = cairo.RadialGradient(-18, dome_y - 30, 8, 0, dome_y, 78)
        dome.add_color_stop_rgb(0.0, 0.98, 0.97, 0.94)
        dome.add_color_stop_rgb(0.55, 0.90, 0.89, 0.86)
        dome.add_color_stop_rgb(1.0, 0.72, 0.70, 0.66)
        ctx.set_source(dome)
        ctx.move_to(-78, 0)
        ctx.curve_to(-78, -70, -40, -95, 0, -95)
        ctx.curve_to(40, -95, 78, -70, 78, 0)
        ctx.close_path()
        ctx.fill()

        # Dome base ring
        ctx.set_source_rgb(0.82, 0.80, 0.76)
        ctx.rectangle(-80, -6, 160, 10)
        ctx.fill()

        # Harmika (square tower with painted eyes)
        ctx.set_source_rgb(0.96, 0.82, 0.28)
        ctx.rectangle(-28, -132, 56, 40)
        ctx.fill()
        # Gold border frames
        ctx.set_source_rgb(0.75, 0.55, 0.12)
        ctx.set_line_width(2.0)
        ctx.rectangle(-28, -132, 56, 40)
        ctx.stroke()
        ctx.rectangle(-24, -128, 22, 32)
        ctx.stroke()
        ctx.rectangle(2, -128, 22, 32)
        ctx.stroke()

        # Buddha eyes (all-seeing)
        ctx.set_source_rgb(0.08, 0.08, 0.10)
        ctx.set_line_width(2.2)
        for ex in (-12, 12):
            ctx.arc(ex, -112, 7, 0.15, math.pi - 0.15)
            ctx.stroke()
            ctx.arc(ex, -110, 2.2, 0, 2 * math.pi)
            ctx.fill()
        # Nepali-style nose (question-mark / curly)
        ctx.set_line_width(2.0)
        ctx.move_to(0, -118)
        ctx.curve_to(5, -110, -5, -100, 0, -94)
        ctx.stroke()
        ctx.arc(0, -92, 1.8, 0, 2 * math.pi)
        ctx.fill()

        # Thirteen chatra tiers (spire)
        for step in range(13):
            sw = 42 - step * 2.6
            yy = -136 - step * 5.2
            gold = 0.78 + (step % 3) * 0.05
            ctx.set_source_rgb(gold, 0.62 + step * 0.01, 0.14)
            ctx.rectangle(-sw / 2, yy, sw, 4.2)
            ctx.fill()
            ctx.set_source_rgba(1.0, 0.9, 0.5, 0.25)
            ctx.rectangle(-sw / 2, yy, sw, 1.2)
            ctx.fill()

        # Gajur / pinnacle
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.move_to(0, -210)
        ctx.line_to(7, -204)
        ctx.line_to(3, -198)
        ctx.line_to(8, -192)
        ctx.line_to(0, -185)
        ctx.line_to(-8, -192)
        ctx.line_to(-3, -198)
        ctx.line_to(-7, -204)
        ctx.close_path()
        ctx.fill()
        ctx.arc(0, -214, 4.5, 0, 2 * math.pi)
        ctx.fill()

        # Fluttering prayer flags (cloth rectangles on lines)
        flag_cols = [
            (0.15, 0.35, 0.85), (0.95, 0.95, 0.95), (0.85, 0.12, 0.12),
            (0.15, 0.70, 0.28), (0.92, 0.78, 0.12),
        ]
        wind = math.sin(t * 2.5) * 8
        for side in (-1, 1):
            for i, col in enumerate(flag_cols):
                end_x = side * (82 - i * 14) - side * wind * (0.35 + i * 0.07)
                ctx.set_source_rgba(0.75, 0.72, 0.65, 0.7)
                ctx.set_line_width(1.0)
                ctx.move_to(0, -210)
                ctx.curve_to(side * 15, -155, end_x * 0.55, -105, end_x, -58)
                ctx.stroke()
                # Flag cloth
                fx = end_x * 0.55
                fy = -130 - i * 8
                flutter = math.sin(t * 4.0 + i + side) * 3
                ctx.set_source_rgb(*col)
                ctx.move_to(fx, fy)
                ctx.line_to(fx + side * 14 + flutter, fy + 3)
                ctx.line_to(fx + side * 12 + flutter * 0.5, fy + 12)
                ctx.line_to(fx - side * 2, fy + 10)
                ctx.close_path()
                ctx.fill()

        ctx.restore()

    def draw_pagoda(self, ctx, x, y, t=0.0):
        """Multi-tier Newar pagoda temple with upturned eaves and lattice."""
        ctx.save()
        ctx.translate(x, y)

        # Stone plinth
        ctx.set_source_rgb(0.48, 0.42, 0.34)
        ctx.rectangle(-88, -8, 176, 14)
        ctx.fill()
        ctx.set_source_rgb(0.38, 0.32, 0.26)
        ctx.rectangle(-80, -18, 160, 12)
        ctx.fill()

        # Ground floor brick body
        ctx.set_source_rgb(0.52, 0.28, 0.20)
        ctx.rectangle(-58, -78, 116, 60)
        ctx.fill()
        # Doorway
        ctx.set_source_rgb(0.18, 0.10, 0.08)
        ctx.rectangle(-14, -52, 28, 34)
        ctx.fill()
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.set_line_width(2)
        ctx.rectangle(-14, -52, 28, 34)
        ctx.stroke()
        # Carved pillars
        ctx.set_source_rgb(0.35, 0.18, 0.12)
        for px in (-48, -28, 20, 40):
            ctx.rectangle(px, -78, 8, 60)
            ctx.fill()

        self._draw_roof_tier(ctx, 0, -78, 168, 28, t)

        # Mid story
        ctx.set_source_rgb(0.48, 0.24, 0.17)
        ctx.rectangle(-40, -128, 80, 42)
        ctx.fill()
        # Lattice windows
        ctx.set_source_rgb(0.22, 0.12, 0.08)
        for wx in (-28, 8):
            ctx.rectangle(wx, -118, 20, 22)
            ctx.fill()
            ctx.set_source_rgb(0.70, 0.55, 0.20)
            ctx.set_line_width(1.0)
            for gx in range(4):
                ctx.move_to(wx + 4 + gx * 4, -118)
                ctx.line_to(wx + 4 + gx * 4, -96)
                ctx.stroke()
            for gy in range(4):
                ctx.move_to(wx, -116 + gy * 5)
                ctx.line_to(wx + 20, -116 + gy * 5)
                ctx.stroke()
            ctx.set_source_rgb(0.22, 0.12, 0.08)

        self._draw_roof_tier(ctx, 0, -128, 128, 24, t)

        # Upper story
        ctx.set_source_rgb(0.44, 0.22, 0.15)
        ctx.rectangle(-26, -168, 52, 32)
        ctx.fill()
        ctx.set_source_rgb(0.20, 0.10, 0.07)
        ctx.rectangle(-10, -160, 20, 16)
        ctx.fill()
        self._draw_roof_tier(ctx, 0, -168, 90, 20, t)

        # Golden gajur / pinnacle
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.move_to(0, -218)
        ctx.line_to(8, -188)
        ctx.line_to(-8, -188)
        ctx.close_path()
        ctx.fill()
        ctx.arc(0, -220, 5, 0, 2 * math.pi)
        ctx.fill()
        ctx.rectangle(-2, -188, 4, 8)
        ctx.fill()

        # Hanging bells under eaves
        ctx.set_source_rgb(0.85, 0.70, 0.20)
        for bx in (-55, -25, 25, 55):
            sway = math.sin(t * 3.0 + bx) * 1.5
            ctx.move_to(bx, -78)
            ctx.line_to(bx + sway, -68)
            ctx.set_line_width(1.2)
            ctx.stroke()
            ctx.arc(bx + sway, -65, 3.5, 0, 2 * math.pi)
            ctx.fill()

        ctx.restore()

    def _draw_roof_tier(self, ctx, cx, cy, span, h, t=0.0):
        # Deep crimson tiled roof with upturned eaves
        roof = cairo.LinearGradient(cx, cy - h, cx, cy)
        roof.add_color_stop_rgb(0.0, 0.72, 0.22, 0.14)
        roof.add_color_stop_rgb(0.5, 0.55, 0.14, 0.10)
        roof.add_color_stop_rgb(1.0, 0.38, 0.10, 0.08)
        ctx.set_source(roof)
        flare = 14
        ctx.move_to(cx - span / 2, cy)
        ctx.curve_to(
            cx - span / 2 - flare, cy - h * 0.25,
            cx - span / 3, cy - h * 0.85,
            cx, cy - h,
        )
        ctx.curve_to(
            cx + span / 3, cy - h * 0.85,
            cx + span / 2 + flare, cy - h * 0.25,
            cx + span / 2, cy,
        )
        ctx.close_path()
        ctx.fill()

        # Tile ridge lines
        ctx.set_source_rgba(0.25, 0.08, 0.06, 0.45)
        ctx.set_line_width(1.0)
        for i in range(1, 6):
            yy = cy - h * (i / 6.5)
            half = (span / 2) * (1.0 - i / 7.5)
            ctx.move_to(cx - half, yy)
            ctx.line_to(cx + half, yy)
            ctx.stroke()

        # Gold roof edge trim
        ctx.set_source_rgb(0.85, 0.68, 0.22)
        ctx.set_line_width(2.0)
        ctx.move_to(cx - span / 2, cy)
        ctx.line_to(cx + span / 2, cy)
        ctx.stroke()

        # Corner struts
        ctx.set_source_rgb(0.40, 0.22, 0.12)
        ctx.set_line_width(3)
        ctx.move_to(cx - span / 2 + 8, cy)
        ctx.line_to(cx - span / 2 - 6, cy + 10)
        ctx.stroke()
        ctx.move_to(cx + span / 2 - 8, cy)
        ctx.line_to(cx + span / 2 + 6, cy + 10)
        ctx.stroke()


# ==============================================================================
# 3. CHARACTER RIGS
# ==============================================================================

class NarayanGopalRig:
    def __init__(self):
        self.w, self.h = 340, 380
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_singing):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        vibrato = math.sin(t * 8.0) * 0.03 if is_singing else 0.0
        sing_intensity = max(0.0, math.sin(t * BEAT_FREQ * 2 * math.pi)) if is_singing else 0.1
        bellows = (math.sin(t * BEAT_FREQ * 2 * math.pi) + 1.0) * 0.5

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)

        # Shadow
        ctx.set_source_rgba(0, 0, 0, 0.25)
        ctx.scale(1.0, 0.28)
        ctx.arc(0, 8, 55, 0, 2 * math.pi)
        ctx.fill()
        ctx.scale(1.0, 1.0 / 0.28)

        # Cross-legged posture (suruwal)
        ctx.set_line_width(18)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.18, 0.18, 0.22)
        ctx.move_to(-38, -8)
        ctx.curve_to(-55, 5, -70, 18, -55, 22)
        ctx.stroke()
        ctx.move_to(38, -8)
        ctx.curve_to(55, 5, 70, 18, 55, 22)
        ctx.stroke()
        # Soft shoes
        ctx.set_source_rgb(0.55, 0.42, 0.28)
        ctx.arc(-55, 24, 7, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(55, 24, 7, 0, 2 * math.pi)
        ctx.fill()

        # Torso & tweed blazer
        ctx.save()
        ctx.rotate(math.sin(t * BEAT_FREQ * math.pi) * 0.03)
        blazer = cairo.LinearGradient(-22, -80, 22, 0)
        blazer.add_color_stop_rgb(0.0, 0.30, 0.28, 0.32)
        blazer.add_color_stop_rgb(1.0, 0.20, 0.19, 0.22)
        ctx.set_source(blazer)
        ctx.move_to(-24, -78)
        ctx.line_to(24, -78)
        ctx.line_to(20, 0)
        ctx.line_to(-20, 0)
        ctx.close_path()
        ctx.fill()
        # Lapels
        ctx.set_source_rgb(0.35, 0.33, 0.38)
        ctx.move_to(-8, -78)
        ctx.line_to(-2, -40)
        ctx.line_to(-18, -10)
        ctx.line_to(-22, -78)
        ctx.close_path()
        ctx.fill()
        ctx.move_to(8, -78)
        ctx.line_to(2, -40)
        ctx.line_to(18, -10)
        ctx.line_to(22, -78)
        ctx.close_path()
        ctx.fill()

        # Cream muffler
        ctx.set_source_rgb(0.90, 0.84, 0.72)
        ctx.rectangle(-18, -78, 36, 16)
        ctx.fill()
        ctx.rectangle(-7, -64, 10, 48)
        ctx.fill()
        ctx.set_source_rgba(0.75, 0.65, 0.45, 0.4)
        for i in range(4):
            ctx.rectangle(-7, -60 + i * 12, 10, 2)
            ctx.fill()

        # Head
        ctx.save()
        ctx.translate(0, -96)
        ctx.rotate(-0.05 - (sing_intensity * 0.12) + vibrato)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 0, 15, 0, 2 * math.pi)
        ctx.fill()
        # Ears
        ctx.arc(-14, 1, 4, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(14, 1, 4, 0, 2 * math.pi)
        ctx.fill()

        # Wavy black hair
        ctx.set_source_rgb(0.10, 0.08, 0.08)
        ctx.arc(0, -5, 16, math.pi, 2 * math.pi)
        ctx.fill()
        for hx, hy in [(-10, -8), (-4, -14), (4, -14), (10, -8)]:
            ctx.arc(hx, hy, 6, 0, 2 * math.pi)
            ctx.fill()

        # Glasses
        ctx.set_line_width(2.3)
        ctx.set_source_rgb(0.12, 0.12, 0.12)
        ctx.rectangle(-12, -5, 10, 8)
        ctx.stroke()
        ctx.rectangle(2, -5, 10, 8)
        ctx.stroke()
        ctx.move_to(-2, -1)
        ctx.line_to(2, -1)
        ctx.stroke()
        ctx.move_to(-12, -1)
        ctx.line_to(-16, -2)
        ctx.stroke()
        ctx.move_to(12, -1)
        ctx.line_to(16, -2)
        ctx.stroke()
        # Lens glint
        ctx.set_source_rgba(0.9, 0.95, 1.0, 0.25)
        ctx.rectangle(-10, -3, 4, 3)
        ctx.fill()

        # Eyes / brows
        ctx.set_source_rgb(0.15, 0.12, 0.10)
        ctx.set_line_width(1.5)
        ctx.move_to(-10, -8)
        ctx.line_to(-3, -9)
        ctx.stroke()
        ctx.move_to(3, -9)
        ctx.line_to(10, -8)
        ctx.stroke()

        # Singing mouth
        mouth_h = 2 + sing_intensity * 7.0
        ctx.set_source_rgb(0.45, 0.1, 0.12)
        ctx.rectangle(-4, 6, 8, mouth_h)
        ctx.fill()
        ctx.restore()

        # Left arm — bellows
        ctx.save()
        ctx.translate(-22, -68)
        ctx.rotate(-0.85 - bellows * 0.28)
        ctx.set_line_width(11)
        ctx.set_source_rgb(0.25, 0.24, 0.28)
        ctx.line_to(0, 34)
        ctx.stroke()
        ctx.translate(0, 34)
        ctx.rotate(-0.65 + bellows * 0.4)
        ctx.line_to(0, 28)
        ctx.stroke()
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 30, 5, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Right arm — keys
        ctx.save()
        ctx.translate(22, -68)
        ctx.rotate(0.55 + math.sin(t * 5.5) * 0.05)
        ctx.set_line_width(11)
        ctx.set_source_rgb(0.25, 0.24, 0.28)
        ctx.line_to(0, 34)
        ctx.stroke()
        ctx.translate(0, 34)
        ctx.rotate(0.85 + math.sin(t * 6.0) * 0.1)
        ctx.line_to(0, 28)
        ctx.stroke()
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 30, 5, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        ctx.restore()

        # Harmonium (wooden, with bellows & keys)
        ctx.save()
        ctx.translate(0, 12)
        # Body
        wood = cairo.LinearGradient(-58, -50, 58, 0)
        wood.add_color_stop_rgb(0.0, 0.55, 0.30, 0.14)
        wood.add_color_stop_rgb(1.0, 0.38, 0.18, 0.08)
        ctx.set_source(wood)
        ctx.rectangle(-58, -48, 116, 48)
        ctx.fill()
        ctx.set_source_rgb(0.70, 0.50, 0.22)
        ctx.set_line_width(2)
        ctx.rectangle(-58, -48, 116, 48)
        ctx.stroke()
        # Decorative inlay
        ctx.set_source_rgb(0.75, 0.55, 0.20)
        ctx.rectangle(-50, -44, 100, 3)
        ctx.fill()
        # Bellows folds
        bw = 16 + bellows * 18
        for i in range(5):
            shade = 0.55 + (i % 2) * 0.12
            ctx.set_source_rgb(shade, 0.12, 0.14)
            ctx.rectangle(-58 - bw + i * (bw / 5), -46, bw / 5 + 1, 44)
            ctx.fill()
        # Keyboard
        ctx.set_source_rgb(0.96, 0.95, 0.90)
        ctx.rectangle(-4, -44, 58, 16)
        ctx.fill()
        ctx.set_source_rgb(0.12, 0.10, 0.10)
        for k in range(7):
            ctx.rectangle(2 + k * 7.5, -44, 4, 10)
            ctx.fill()
        # Stops / knobs
        ctx.set_source_rgb(0.85, 0.70, 0.25)
        for kx in (-40, -25, -10):
            ctx.arc(kx, -36, 3.5, 0, 2 * math.pi)
            ctx.fill()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


class NepaliDancersRig:
    def __init__(self):
        self.w, self.h = 280, 420
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, which="pair", is_twirling=False):
        """which: 'female', 'male', or 'pair'."""
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        sway = math.sin(t * BEAT_FREQ * 2 * math.pi)
        twirl_scale = math.cos(t * 5.0) if is_twirling else 1.0
        hop = abs(math.sin(t * BEAT_FREQ * 2 * math.pi)) * 6 if is_twirling else 0

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40 - hop)

        if which in ("female", "pair"):
            ctx.save()
            ox = -55 if which == "pair" else 0
            ctx.translate(ox, 0)
            ctx.scale(max(0.25, abs(twirl_scale)) * (1 if twirl_scale >= 0 else -1), 1.0)
            self._draw_female(ctx, sway, t)
            ctx.restore()

        if which in ("male", "pair"):
            ctx.save()
            ox = 55 if which == "pair" else 0
            ctx.translate(ox, 0)
            ctx.scale(max(0.25, abs(twirl_scale)) * (1 if twirl_scale >= 0 else -1), 1.0)
            self._draw_male(ctx, -sway, t)
            ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")

    def _draw_female(self, ctx, sway, t):
        # Shadow
        ctx.set_source_rgba(0, 0, 0, 0.2)
        ctx.save()
        ctx.scale(1.0, 0.25)
        ctx.arc(0, 10, 40, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        flare = 48 + abs(sway) * 18
        # Gunyu / black skirt with gold border
        skirt = cairo.LinearGradient(0, -80, 0, 0)
        skirt.add_color_stop_rgb(0.0, 0.18, 0.16, 0.20)
        skirt.add_color_stop_rgb(1.0, 0.08, 0.08, 0.10)
        ctx.set_source(skirt)
        ctx.move_to(-12, -80)
        ctx.curve_to(-flare * 0.6, -40, -flare, -5, -flare, 0)
        ctx.line_to(flare, 0)
        ctx.curve_to(flare, -5, flare * 0.6, -40, 12, -80)
        ctx.close_path()
        ctx.fill()
        ctx.set_line_width(4)
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.move_to(-flare, 0)
        ctx.line_to(flare, 0)
        ctx.stroke()
        # Inner gold stripe
        ctx.set_line_width(2)
        ctx.move_to(-flare * 0.85, -8)
        ctx.line_to(flare * 0.85, -8)
        ctx.stroke()

        # Red cholo blouse
        ctx.set_source_rgb(0.82, 0.12, 0.16)
        ctx.move_to(-16, -140)
        ctx.line_to(16, -140)
        ctx.line_to(14, -80)
        ctx.line_to(-14, -80)
        ctx.close_path()
        ctx.fill()
        # Gold neckline
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.set_line_width(2)
        ctx.move_to(-10, -138)
        ctx.line_to(0, -128)
        ctx.line_to(10, -138)
        ctx.stroke()

        # Head & hair bun with tika
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, -156, 12, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.08, 0.06, 0.06)
        ctx.arc(-9, -160, 8, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(0, -168, 7, 0, 2 * math.pi)
        ctx.fill()
        # Red tika
        ctx.set_source_rgb(0.85, 0.1, 0.12)
        ctx.arc(0, -158, 2.2, 0, 2 * math.pi)
        ctx.fill()
        # Gold earring
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.arc(-12, -152, 2.5, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(12, -152, 2.5, 0, 2 * math.pi)
        ctx.fill()

        # Mudra arms
        ctx.set_line_width(7)
        ctx.set_source_rgb(0.82, 0.12, 0.16)
        ctx.move_to(-14, -132)
        ctx.line_to(-40, -168 + sway * 14)
        ctx.stroke()
        ctx.move_to(14, -132)
        ctx.line_to(40, -168 - sway * 14)
        ctx.stroke()
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(-40, -168 + sway * 14, 4, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(40, -168 - sway * 14, 4, 0, 2 * math.pi)
        ctx.fill()

    def _draw_male(self, ctx, sway, t):
        ctx.set_source_rgba(0, 0, 0, 0.2)
        ctx.save()
        ctx.scale(1.0, 0.25)
        ctx.arc(0, 10, 35, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Suruwal legs
        ctx.set_line_width(11)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.90, 0.88, 0.82)
        ctx.move_to(-10, -72)
        ctx.line_to(-18 + sway * 12, 0)
        ctx.stroke()
        ctx.move_to(10, -72)
        ctx.line_to(18 - sway * 12, 0)
        ctx.stroke()
        # Moja / shoes
        ctx.set_source_rgb(0.35, 0.22, 0.14)
        ctx.arc(-18 + sway * 12, 4, 6, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(18 - sway * 12, 4, 6, 0, 2 * math.pi)
        ctx.fill()

        # Daura suruwal coat
        ctx.set_source_rgb(0.92, 0.90, 0.86)
        ctx.move_to(-16, -145)
        ctx.line_to(16, -145)
        ctx.line_to(15, -72)
        ctx.line_to(-15, -72)
        ctx.close_path()
        ctx.fill()
        # Double-breasted waistcoat panels
        ctx.set_source_rgb(0.14, 0.15, 0.22)
        ctx.rectangle(-15, -145, 9, 48)
        ctx.fill()
        ctx.rectangle(6, -145, 9, 48)
        ctx.fill()
        # Tie strings
        ctx.set_source_rgb(0.85, 0.75, 0.35)
        for by in (-130, -115, -100):
            ctx.arc(0, by, 2, 0, 2 * math.pi)
            ctx.fill()

        # Patuka sash
        ctx.set_source_rgb(0.80, 0.12, 0.15)
        ctx.rectangle(-18, -80, 36, 12)
        ctx.fill()
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.rectangle(-18, -80, 36, 2)
        ctx.fill()

        # Head + Dhaka topi
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, -160, 12, 0, 2 * math.pi)
        ctx.fill()
        # Dhaka pattern topi
        ctx.set_source_rgb(0.72, 0.16, 0.18)
        ctx.move_to(-12, -168)
        ctx.line_to(-11, -182)
        ctx.line_to(3, -186)
        ctx.line_to(12, -174)
        ctx.line_to(12, -168)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(0.90, 0.75, 0.25)
        ctx.set_line_width(1.2)
        ctx.move_to(-8, -172)
        ctx.line_to(6, -178)
        ctx.stroke()
        ctx.move_to(-6, -178)
        ctx.line_to(8, -172)
        ctx.stroke()

        # Arms
        ctx.set_line_width(8)
        ctx.set_source_rgb(0.92, 0.90, 0.86)
        ctx.move_to(-14, -138)
        ctx.line_to(-44, -112 + sway * 16)
        ctx.stroke()
        ctx.move_to(14, -138)
        ctx.line_to(44, -112 - sway * 16)
        ctx.stroke()
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(-44, -112 + sway * 16, 4.5, 0, 2 * math.pi)
        ctx.fill()
        ctx.arc(44, -112 - sway * 16, 4.5, 0, 2 * math.pi)
        ctx.fill()


class RoyalGuardRig:
    def __init__(self):
        self.w, self.h = 360, 440
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_attacking=False):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        slash = math.sin(t * (BEAT_FREQ * 4 * math.pi if is_attacking else BEAT_FREQ * 2 * math.pi))
        lean = slash * (0.12 if is_attacking else 0.04)

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)
        ctx.rotate(lean)

        # Shadow
        ctx.set_source_rgba(0, 0, 0, 0.22)
        ctx.save()
        ctx.scale(1.0, 0.25)
        ctx.arc(0, 10, 42, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Legs
        ctx.set_line_width(13)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.12, 0.14, 0.18)
        ctx.move_to(-16, -78)
        ctx.line_to(-38 - (8 if is_attacking else 0), 0)
        ctx.stroke()
        ctx.move_to(16, -78)
        ctx.line_to(40 + (6 if is_attacking else 0), 0)
        ctx.stroke()
        # Boots
        ctx.set_source_rgb(0.18, 0.14, 0.10)
        ctx.arc(-38 - (8 if is_attacking else 0), 4, 8, 0, math.pi)
        ctx.fill()
        ctx.arc(40 + (6 if is_attacking else 0), 4, 8, 0, math.pi)
        ctx.fill()

        # Scarlet tunic
        tunic = cairo.LinearGradient(-20, -160, 20, -70)
        tunic.add_color_stop_rgb(0.0, 0.82, 0.14, 0.16)
        tunic.add_color_stop_rgb(1.0, 0.58, 0.08, 0.10)
        ctx.set_source(tunic)
        ctx.rectangle(-20, -155, 40, 78)
        ctx.fill()
        # White cross belts
        ctx.set_line_width(4.5)
        ctx.set_source_rgb(0.95, 0.94, 0.90)
        ctx.move_to(-18, -152)
        ctx.line_to(18, -82)
        ctx.stroke()
        ctx.move_to(18, -152)
        ctx.line_to(-18, -82)
        ctx.stroke()
        # Brass buckle
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.arc(0, -100, 5, 0, 2 * math.pi)
        ctx.fill()
        # Belt
        ctx.set_source_rgb(0.15, 0.12, 0.10)
        ctx.rectangle(-20, -85, 40, 8)
        ctx.fill()

        # Head & plumed cap
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, -172, 13, 0, 2 * math.pi)
        ctx.fill()
        # Mustache
        ctx.set_source_rgb(0.15, 0.12, 0.10)
        ctx.set_line_width(2)
        ctx.move_to(-7, -166)
        ctx.curve_to(-3, -163, 3, -163, 7, -166)
        ctx.stroke()
        # Cap
        ctx.set_source_rgb(0.12, 0.14, 0.18)
        ctx.rectangle(-14, -192, 28, 15)
        ctx.fill()
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.rectangle(-14, -180, 28, 3)
        ctx.fill()
        # Red plume
        ctx.set_source_rgb(0.9, 0.1, 0.1)
        ctx.set_line_width(3)
        ctx.move_to(0, -192)
        ctx.curve_to(5, -208, -4, -218, 2, -226)
        ctx.stroke()

        # Left arm — torch
        ctx.save()
        ctx.translate(-20, -148)
        ctx.rotate(-1.55 + math.sin(t * 3.0) * 0.1)
        ctx.set_line_width(10)
        ctx.set_source_rgb(0.76, 0.10, 0.14)
        ctx.line_to(0, 36)
        ctx.stroke()
        ctx.translate(0, 36)
        ctx.rotate(-0.75)
        ctx.line_to(0, 32)
        ctx.stroke()
        ctx.translate(0, 32)
        # Torch staff
        ctx.set_line_width(5)
        ctx.set_source_rgb(0.35, 0.22, 0.12)
        ctx.line_to(0, -34)
        ctx.stroke()
        # Flame
        flick = math.sin(t * 16.0) * 3
        ctx.set_source_rgba(1.0, 0.4, 0.05, 0.5)
        ctx.arc(flick * 0.5, -46, 16, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(1.0, 0.45, 0.08)
        ctx.move_to(-6, -36)
        ctx.curve_to(-10 + flick, -50, 0, -58, 2, -64)
        ctx.curve_to(6, -54, 10 + flick, -46, 6, -36)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(1.0, 0.9, 0.3)
        ctx.arc(0, -44, 6, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Right arm — khukuri
        ctx.save()
        ctx.translate(20, -148)
        arm_rot = 0.35 + slash * 1.2 if is_attacking else 0.5 + slash * 0.28
        ctx.rotate(arm_rot)
        ctx.set_line_width(10)
        ctx.set_source_rgb(0.76, 0.10, 0.14)
        ctx.line_to(0, 36)
        ctx.stroke()
        ctx.translate(0, 36)
        ctx.rotate(1.05)
        ctx.line_to(0, 30)
        ctx.stroke()
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 32, 5, 0, 2 * math.pi)
        ctx.fill()
        # Khukuri blade (inward curve)
        ctx.translate(0, 32)
        blade = cairo.LinearGradient(0, 0, 10, -40)
        blade.add_color_stop_rgb(0.0, 0.75, 0.78, 0.82)
        blade.add_color_stop_rgb(1.0, 0.92, 0.94, 0.97)
        ctx.set_source(blade)
        ctx.move_to(0, 0)
        ctx.curve_to(8, -12, 14, -28, 4, -48)
        ctx.curve_to(-6, -34, -8, -14, 0, 0)
        ctx.close_path()
        ctx.fill()
        # Notch near handle
        ctx.set_source_rgb(0.25, 0.2, 0.15)
        ctx.rectangle(-3, -4, 8, 5)
        ctx.fill()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


class JamesHetfieldRig:
    def __init__(self):
        self.w, self.h = 440, 440
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_swinging=False):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        downpick = math.sin(t * 24.0) * 6.0
        headbang = math.sin(t * BEAT_FREQ * 4 * math.pi) * 0.30
        guitar_tilt = -0.35 - (0.65 if is_swinging else 0.0)
        stance = math.sin(t * BEAT_FREQ * 2 * math.pi) * 4

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)

        ctx.set_source_rgba(0, 0, 0, 0.22)
        ctx.save()
        ctx.scale(1.0, 0.25)
        ctx.arc(0, 10, 50, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Power stance
        ctx.set_line_width(15)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.14, 0.15, 0.20)
        ctx.move_to(-22, -78)
        ctx.line_to(-52 + stance, 0)
        ctx.stroke()
        ctx.move_to(22, -78)
        ctx.line_to(52 - stance, 0)
        ctx.stroke()
        # Boots
        ctx.set_source_rgb(0.10, 0.10, 0.12)
        ctx.arc(-52 + stance, 4, 9, 0, math.pi)
        ctx.fill()
        ctx.arc(52 - stance, 4, 9, 0, math.pi)
        ctx.fill()

        # Black sleeveless torso
        ctx.set_source_rgb(0.10, 0.10, 0.12)
        ctx.rectangle(-24, -155, 48, 78)
        ctx.fill()
        # Vest cut
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.move_to(-24, -155)
        ctx.line_to(-18, -120)
        ctx.line_to(-24, -100)
        ctx.fill()
        ctx.move_to(24, -155)
        ctx.line_to(18, -120)
        ctx.line_to(24, -100)
        ctx.fill()

        # Head & blonde hair
        ctx.save()
        ctx.translate(0, -172)
        ctx.rotate(headbang)
        # Hair mass
        ctx.set_source_rgb(0.78, 0.62, 0.34)
        ctx.arc(0, 0, 18, 0, 2 * math.pi)
        ctx.fill()
        ctx.move_to(-18, 2)
        ctx.curve_to(-30, 20, -28, 40, -22, 48)
        ctx.line_to(22, 48)
        ctx.curve_to(28, 40, 30, 20, 18, 2)
        ctx.close_path()
        ctx.fill()
        # Face
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 4, 12, 0, 2 * math.pi)
        ctx.fill()
        # Open mouth scream
        ctx.set_source_rgb(0.4, 0.08, 0.1)
        ctx.rectangle(-5, 6, 10, 8)
        ctx.fill()
        # Goatee
        ctx.set_line_width(2)
        ctx.set_source_rgb(0.45, 0.34, 0.18)
        ctx.arc(0, 10, 6, 0.1, math.pi - 0.1)
        ctx.stroke()
        ctx.restore()

        # ESP/Explorer-style Flying V
        ctx.save()
        ctx.translate(-8, -92)
        ctx.rotate(guitar_tilt)
        # Neck
        ctx.set_source_rgb(0.18, 0.12, 0.08)
        ctx.rectangle(-118, -5, 118, 10)
        ctx.fill()
        ctx.set_source_rgb(0.75, 0.65, 0.35)
        for fi in range(8):
            ctx.rectangle(-110 + fi * 12, -5, 1.5, 10)
            ctx.fill()
        # Headstock
        ctx.set_source_rgb(0.15, 0.12, 0.10)
        ctx.rectangle(-128, -8, 14, 16)
        ctx.fill()
        # Body
        ctx.set_source_rgb(0.96, 0.95, 0.92)
        ctx.move_to(0, -16)
        ctx.line_to(88, -46)
        ctx.line_to(50, 0)
        ctx.line_to(88, 46)
        ctx.line_to(0, 16)
        ctx.close_path()
        ctx.fill()
        # Bridge / pickups
        ctx.set_source_rgb(0.2, 0.2, 0.22)
        ctx.rectangle(18, -8, 14, 16)
        ctx.fill()
        ctx.rectangle(38, -6, 10, 12)
        ctx.fill()
        # Strings
        ctx.set_source_rgba(0.7, 0.7, 0.75, 0.7)
        ctx.set_line_width(0.8)
        for s in range(6):
            yy = -4 + s * 1.6
            ctx.move_to(-118, yy)
            ctx.line_to(45, yy)
            ctx.stroke()
        ctx.restore()

        # Right arm downpicking
        ctx.save()
        ctx.translate(24, -148)
        ctx.rotate(0.55 + downpick * 0.015)
        ctx.set_line_width(12)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.line_to(0, 36)
        ctx.stroke()
        ctx.translate(0, 36)
        ctx.rotate(1.05 + downpick * 0.02)
        ctx.line_to(0, 30)
        ctx.stroke()
        ctx.restore()

        # Left arm on neck
        ctx.save()
        ctx.translate(-22, -148)
        ctx.rotate(-0.9)
        ctx.set_line_width(11)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.line_to(0, 40)
        ctx.stroke()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


class LarsUlrichRig:
    def __init__(self):
        self.w, self.h = 440, 440
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_twirling=False):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        snare_hit = max(0.0, -math.sin(t * BEAT_FREQ * 4 * math.pi))
        twirl_rot = (t * 14.0) % (2 * math.pi) if is_twirling else 0.4
        bounce = snare_hit * 4

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40 - bounce)

        ctx.set_source_rgba(0, 0, 0, 0.22)
        ctx.save()
        ctx.scale(1.0, 0.25)
        ctx.arc(0, 10, 48, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Legs under kit
        ctx.set_line_width(12)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.14, 0.14, 0.18)
        ctx.move_to(-18, -70)
        ctx.line_to(-30, 0)
        ctx.stroke()
        ctx.move_to(18, -70)
        ctx.line_to(32, 0)
        ctx.stroke()

        # Torso
        ctx.set_source_rgb(0.12, 0.12, 0.15)
        ctx.rectangle(-22, -148, 44, 78)
        ctx.fill()

        # Head & black cap
        ctx.save()
        ctx.translate(0, -164)
        ctx.rotate(math.sin(t * 6.0) * 0.15)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 0, 13, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.08, 0.08, 0.10)
        ctx.arc(0, -3, 14, math.pi, 2 * math.pi)
        ctx.fill()
        ctx.rectangle(-20, -5, 10, 5)
        ctx.fill()
        # Open mouth
        ctx.set_source_rgb(0.85, 0.25, 0.30)
        ctx.rectangle(-3, 6, 6, 7)
        ctx.fill()
        ctx.restore()

        # Snare drum (chrome + batter head)
        ctx.set_source_rgb(0.55, 0.58, 0.64)
        ctx.rectangle(-40, -55, 80, 38)
        ctx.fill()
        ctx.set_source_rgb(0.88, 0.88, 0.90)
        ctx.rectangle(-40, -55, 80, 8)
        ctx.fill()
        # Lugs
        ctx.set_source_rgb(0.75, 0.75, 0.78)
        for lx in (-30, -10, 10, 30):
            ctx.rectangle(lx - 2, -48, 4, 28)
            ctx.fill()
        # Kick hint
        ctx.set_source_rgb(0.25, 0.26, 0.30)
        ctx.rectangle(-28, -18, 56, 22)
        ctx.fill()

        # Ride cymbal
        ctx.save()
        ctx.translate(90, -118)
        wobble = 1.0 + snare_hit * 0.04
        ctx.scale(1.0, 0.28 * wobble)
        cym = cairo.RadialGradient(0, 0, 5, 0, 0, 48)
        cym.add_color_stop_rgb(0.0, 0.95, 0.85, 0.35)
        cym.add_color_stop_rgb(0.5, 0.80, 0.68, 0.22)
        cym.add_color_stop_rgb(1.0, 0.55, 0.45, 0.15)
        ctx.set_source(cym)
        ctx.arc(0, 0, 48, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        # Cymbal stand
        ctx.set_source_rgb(0.5, 0.5, 0.55)
        ctx.set_line_width(2)
        ctx.move_to(90, -110)
        ctx.line_to(90, -40)
        ctx.stroke()

        # Left arm — snare
        ctx.save()
        ctx.translate(-20, -140)
        ctx.rotate(-0.85 + snare_hit * 0.7)
        ctx.set_line_width(10)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.line_to(0, 32)
        ctx.stroke()
        ctx.translate(0, 32)
        ctx.rotate(-0.75)
        ctx.line_to(0, 26)
        ctx.stroke()
        ctx.set_line_width(3.2)
        ctx.set_source_rgb(0.92, 0.88, 0.72)
        ctx.line_to(0, -42)
        ctx.stroke()
        ctx.restore()

        # Right arm — cymbal / twirl
        ctx.save()
        ctx.translate(20, -140)
        ctx.rotate(0.85 - snare_hit * 0.45)
        ctx.set_line_width(10)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.line_to(0, 32)
        ctx.stroke()
        ctx.translate(0, 32)
        ctx.rotate(0.75)
        ctx.line_to(0, 26)
        ctx.stroke()
        ctx.translate(0, 26)
        ctx.rotate(twirl_rot)
        ctx.set_line_width(3.2)
        ctx.set_source_rgb(0.92, 0.88, 0.72)
        ctx.move_to(0, 18)
        ctx.line_to(0, -42)
        ctx.stroke()
        # Stick tip
        ctx.set_source_rgb(0.95, 0.92, 0.85)
        ctx.arc(0, -42, 2.5, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


# ==============================================================================
# 4. DIRECTOR ENGINE
# ==============================================================================
class MusicVideoDirector:
    def __init__(self):
        self.stage = HimalayanStageRenderer(WINDOW_W, WINDOW_H)
        self.narayan = NarayanGopalRig()
        self.dancers = NepaliDancersRig()
        self.guard = RoyalGuardRig()
        self.hetfield = JamesHetfieldRig()
        self.ulrich = LarsUlrichRig()

    def get_scene_descriptor(self, t):
        if t < SINGING_START_TIME:
            return "INTRO_ESTABLISHING"
        elif 33 <= t < 78:
            return "SCENE_SINGING_1"
        elif 78 <= t < 125:
            return "SCENE_FIGHT_HETFIELD"
        elif 125 <= t < 172:
            return "SCENE_SINGING_2"
        elif 172 <= t < 218:
            return "SCENE_FIGHT_ULRICH"
        elif 218 <= t < 265:
            return "SCENE_FIGHT_TRIO"
        else:
            return "SCENE_GRAND_FINALE"

    def render_frame(self, screen, t, show_hud=True):
        scene = self.get_scene_descriptor(t)
        camera_pan = math.sin(t * 0.15) * 80.0

        bg_surface = self.stage.draw_background(t, camera_pan)
        screen.blit(bg_surface, (0, 0))

        # Lateral motion (incommensurate rates so travel stays visible)
        dance_lat = math.sin(t * 0.85) * 80 + math.sin(t * 1.7) * 22
        fight_orbit = math.sin(t * 1.15) * 95
        fight_bob = math.sin(t * 2.05 + 0.6) * 32

        if scene == "INTRO_ESTABLISHING":
            guard_x = int(WINDOW_W * 0.5 + math.sin(t * 0.55) * 280)
            screen.blit(self.guard.render(t, is_attacking=False), (guard_x - 180, 200))
            if show_hud:
                self._render_hud_title(screen, "INTRO: HIMALAYAN MOONLIGHT (72 BPM)", t)

        elif scene in ("SCENE_SINGING_1", "SCENE_SINGING_2"):
            twirl = scene == "SCENE_SINGING_2"
            # Dancers well clear of singer, sweeping laterally on the wings
            female_x = int(10 + max(0, dance_lat + 50))
            male_x = int(WINDOW_W - 270 - max(0, -dance_lat + 50))
            singer_x = WINDOW_W // 2 - 170
            screen.blit(self.dancers.render(t, which="female", is_twirling=twirl), (female_x, 200))
            screen.blit(self.dancers.render(t, which="male", is_twirling=twirl), (male_x, 200))
            screen.blit(self.narayan.render(t, is_singing=True), (singer_x, 250))
            if show_hud:
                self._render_hud_title(
                    screen, "SWAR SAMRAT NARAYAN GOPAL - 'SEEK & DESTROY' (ADHUNIK)", t,
                )

        elif scene == "SCENE_FIGHT_HETFIELD":
            # Close-quarters duel — centers stay ~100px apart while both travel
            mid = WINDOW_W // 2 + int(fight_orbit)
            hx = mid - 50 + int(fight_bob)
            gx = mid + 55 - int(fight_bob * 0.35)
            screen.blit(self.hetfield.render(t, is_swinging=math.sin(t * 2.0) > 0.3), (hx - 220, 200))
            screen.blit(self.guard.render(t, is_attacking=True), (gx - 180, 200))
            if show_hud:
                self._render_hud_title(
                    screen, "DUEL 1: HETFIELD (FLYING V) vs PALACE GUARD (KHUKURI)", t,
                )

        elif scene == "SCENE_FIGHT_ULRICH":
            mid = WINDOW_W // 2 + int(fight_orbit)
            lx = mid - 50 + int(fight_bob)
            gx = mid + 55 - int(fight_bob * 0.35)
            screen.blit(self.ulrich.render(t, is_twirling=True), (lx - 220, 200))
            screen.blit(self.guard.render(t, is_attacking=True), (gx - 180, 200))
            if show_hud:
                self._render_hud_title(
                    screen, "DUEL 2: ULRICH (DRUMSTICKS) vs PALACE GUARD (TORCH)", t,
                )

        elif scene == "SCENE_FIGHT_TRIO":
            # Tight cluster that drifts as a unit across the courtyard
            mid = WINDOW_W // 2 + int(fight_orbit * 0.85)
            hx = mid - 95 + int(fight_bob)
            gx = mid + int(math.sin(t * 1.8) * 14)
            lx = mid + 100 - int(fight_bob * 0.5)
            screen.blit(self.hetfield.render(t, is_swinging=True), (hx - 220, 200))
            screen.blit(self.guard.render(t, is_attacking=True), (gx - 180, 200))
            screen.blit(self.ulrich.render(t, is_twirling=True), (lx - 220, 200))
            if show_hud:
                self._render_hud_title(
                    screen, "CLASH 3: METALLICA DUO vs ROYAL GUARD STANDOFF", t,
                )

        elif scene == "SCENE_GRAND_FINALE":
            # Spread finale: Metallica left wing, singer right-of-center, dancers on flanks
            het_x = int(-10 + math.sin(t * 0.9) * 30)
            lars_x = int(95 + math.sin(t * 1.1 + 0.8) * 35)
            female_x = int(300 + dance_lat * 0.35)
            singer_x = WINDOW_W // 2 + 100
            male_x = int(WINDOW_W - 290 - dance_lat * 0.35)
            guard_x = int(WINDOW_W - 140 + math.sin(t * 0.7) * 28)

            screen.blit(self.hetfield.render(t, is_swinging=False), (het_x, 220))
            screen.blit(self.ulrich.render(t, is_twirling=True), (lars_x, 220))
            screen.blit(self.dancers.render(t, which="female", is_twirling=True), (female_x, 200))
            screen.blit(self.narayan.render(t, is_singing=True), (singer_x, 250))
            screen.blit(self.dancers.render(t, which="male", is_twirling=True), (male_x, 200))
            screen.blit(self.guard.render(t, is_attacking=False), (guard_x - 180, 200))
            if show_hud:
                self._render_hud_title(
                    screen, "FINALE: EAST-WEST ADHUNIK THRASHER CONVERGENCE", t,
                )

    def _render_hud_title(self, screen, title, t):
        font = pygame.font.SysFont("arial", 18, bold=True)
        pygame.draw.rect(screen, (10, 10, 15), (0, 0, WINDOW_W, 46))
        pygame.draw.rect(screen, (10, 10, 15), (0, WINDOW_H - 36, WINDOW_W, 36))
        txt = font.render(title, True, (240, 220, 140))
        screen.blit(txt, (24, 12))
        mins = int(t) // 60
        secs = int(t) % 60
        tc = font.render(f"TIMECODE: {mins:02d}:{secs:02d} / 05:13", True, (200, 200, 200))
        screen.blit(tc, (WINDOW_W - 240, 12))
        hint = font.render("[ESC quit]  [SPACE +30s]  [--export for MP4]", True, (140, 140, 150))
        screen.blit(hint, (24, WINDOW_H - 28))


# ==============================================================================
# 5. MAIN LOOP
# ==============================================================================
def main():
    args = parse_args()
    export_mode = args.export

    if export_mode and args.no_preview:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    pygame.init()
    if not export_mode:
        pygame.mixer.init()

    caption = (
        "Seek & Destroy — Exporting…"
        if export_mode
        else "Seek & Destroy - Narayan Gopal x Metallica"
    )
    pygame.display.set_caption(caption)
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock = pygame.time.Clock()

    audio_path = resolve_audio_path()
    if not export_mode and audio_path is not None:
        try:
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
        except Exception as e:
            print(f"[AUDIO] {e}")
    elif not export_mode:
        print("[AUDIO] No audio file found (seek_and_destroy_nepali.mp3)")

    director = MusicVideoDirector()
    recorder = None
    anim_time = 0.0
    frame_index = 0
    total_frames = int(SONG_DURATION * FPS)
    running = True

    if export_mode:
        recorder = FfmpegRecorder(args.output, audio_path=audio_path)
        print(f"Exporting {total_frames} frames ({SONG_DURATION:.0f}s @ {FPS}fps) → {args.output}")
        if audio_path:
            print(f"Muxing audio from {audio_path.name}")

    while running:
        if export_mode:
            if frame_index >= total_frames:
                break
            anim_time = frame_index / FPS
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    running = False
                    break
        else:
            dt = clock.tick(FPS) / 1000.0
            anim_time += dt

            if anim_time > SONG_DURATION:
                anim_time = 0.0
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.play()

            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    anim_time = min(SONG_DURATION, anim_time + 30.0)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                    print("Tip: run with --export to write an MP4 via ffmpeg")

        show_hud = (not export_mode) or args.hud
        director.render_frame(screen, anim_time, show_hud=show_hud)

        if export_mode:
            recorder.write_frame(screen)
            frame_index += 1
            if not args.no_preview:
                pygame.display.flip()
            if frame_index % (FPS * 5) == 0 or frame_index == total_frames:
                pct = 100.0 * frame_index / max(1, total_frames)
                print(f"  {frame_index}/{total_frames} frames ({pct:.0f}%)")
        else:
            pygame.display.flip()

    if recorder:
        out = recorder.close()
        print(f"Wrote {out} ({recorder.frames_written} frames)")

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
