"""Scene 7 — The Desert Flight to the South (5:20 – 6:20)."""

from __future__ import annotations

import math
import random

import cairo

from hey_joe import config as C
from hey_joe.geometry import (
    SeededParticles,
    minaret,
    mughal_arch,
    radial_fill,
    set_rgb,
)
from hey_joe.scenes.base import Scene


class DesertScene(Scene):
    name = "desert"

    def __init__(self, width: int, height: int):
        super().__init__(width, height)
        self.dust = SeededParticles(100, seed=77)
        rng = random.Random(3)
        self.skyline = []
        x = -80
        while x < width + 400:
            kind = rng.choice(["arch", "arch", "arch", "minaret", "dome", "gate"])
            w = rng.uniform(55, 130)
            h = rng.uniform(90, 200)
            self.skyline.append({"x": x, "w": w, "h": h, "kind": kind})
            x += w * rng.uniform(0.85, 1.35)

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Massive multi-ringed sunburst — Saffron / Terracotta
        radial_fill(
            ctx,
            self.cx,
            self.h * 0.38,
            0,
            max(self.w, self.h),
            [
                (0.0, (1.0, 0.85, 0.35), 1.0),
                (0.15, C.SAFFRON, 1.0),
                (0.4, C.TERRACOTTA, 1.0),
                (0.7, (0.45, 0.18, 0.1), 1.0),
                (1.0, (0.18, 0.08, 0.06), 1.0),
            ],
        )

        # Linear geometric sunbeams
        sun_x, sun_y = self.cx, self.h * 0.38
        for i in range(36):
            a = i * (math.tau / 36) + local_t * 0.05
            set_rgb(ctx, C.SAFFRON, 0.06 + 0.04 * (i % 3 == 0))
            ctx.set_line_width(2 if i % 3 else 4)
            ctx.move_to(sun_x, sun_y)
            ctx.line_to(sun_x + math.cos(a) * self.w, sun_y + math.sin(a) * self.h)
            ctx.stroke()

        # Concentric sun rings
        for i in range(8):
            r = 40 + i * 35
            set_rgb(ctx, C.GOLD, 0.12)
            ctx.arc(sun_x, sun_y, r, 0, math.tau)
            ctx.set_line_width(1.5)
            ctx.stroke()

        # 3 layers of sine-wave dunes — parallax scroll
        dune_colors = [
            ((0.55, 0.28, 0.12), 0.95, 0.72, 38, 55),
            ((0.42, 0.2, 0.1), 0.9, 0.78, 28, 85),
            ((0.28, 0.12, 0.07), 0.95, 0.85, 18, 120),
        ]
        for ci, (col, alpha, yfrac, amp, speed) in enumerate(dune_colors):
            ybase = self.h * yfrac
            scroll = local_t * speed
            set_rgb(ctx, col, alpha)
            ctx.move_to(-20, self.h)
            ctx.line_to(-20, ybase)
            steps = 80
            for s in range(steps + 1):
                x = s * (self.w + 40) / steps - 20
                y = ybase + math.sin((x + scroll) * 0.012 + ci) * amp
                y += math.sin((x + scroll) * 0.03 + ci * 2) * amp * 0.35
                ctx.line_to(x, y)
            ctx.line_to(self.w + 20, self.h)
            ctx.close_path()
            ctx.fill()

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Silhouettes sweeping along bottom — galloping flight
        scroll = local_t * 160
        sil = (0.05, 0.03, 0.04)
        base_y = self.h * 0.92
        for b in self.skyline:
            x = ((b["x"] - scroll) % (self.w + 500)) - 100
            if b["kind"] == "minaret":
                minaret(ctx, x + b["w"] * 0.5, base_y, b["h"], sil, 1.0)
            elif b["kind"] == "dome":
                set_rgb(ctx, sil, 1.0)
                ctx.rectangle(x, base_y - b["h"] * 0.4, b["w"], b["h"] * 0.4)
                ctx.fill()
                ctx.arc(x + b["w"] / 2, base_y - b["h"] * 0.4, b["w"] * 0.48, math.pi, math.tau)
                ctx.fill()
                ctx.set_line_width(2)
                ctx.move_to(x + b["w"] / 2, base_y - b["h"] * 0.4 - b["w"] * 0.48)
                ctx.line_to(x + b["w"] / 2, base_y - b["h"] * 0.7)
                ctx.stroke()
            elif b["kind"] == "gate":
                # Triple-arch gateway silhouette
                gap = b["w"] / 3.2
                for k in range(3):
                    mughal_arch(ctx, x + k * gap, base_y, gap * 0.92, b["h"] * (0.7 + 0.15 * (k == 1)), sil, 1.0)
            else:
                mughal_arch(ctx, x, base_y, b["w"], b["h"], sil, 1.0)
                # flanking chhatri finials
                set_rgb(ctx, sil, 1.0)
                for fx in (x + b["w"] * 0.08, x + b["w"] * 0.92):
                    ctx.arc(fx, base_y - b["h"] * 0.55, 6, math.pi, math.tau)
                    ctx.fill()

        # Fast wind streamlines
        for i in range(18):
            y = self.h * 0.15 + (i * 37 + local_t * 40) % (self.h * 0.7)
            x0 = ((i * 97 - local_t * 320) % (self.w + 200)) - 100
            set_rgb(ctx, C.IVORY, 0.12 + 0.08 * (i % 3))
            ctx.set_line_width(1.0 + (i % 4) * 0.4)
            ctx.move_to(x0, y)
            ctx.curve_to(x0 + 60, y - 8, x0 + 120, y + 6, x0 + 180, y)
            ctx.stroke()

        # Drifting dust streaks
        for x, y, s, p in self.dust.positions(local_t * 3.5, self.w, self.h, drift=2.5):
            set_rgb(ctx, C.SAFFRON, 0.25)
            ctx.set_line_width(1.0)
            ctx.move_to(x, y)
            ctx.line_to(x + 12 + s * 8, y + math.sin(p) * 2)
            ctx.stroke()
