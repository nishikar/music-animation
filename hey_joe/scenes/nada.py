"""Scene 1 — The Primordial Resonance / Nada Brahma (0:00 – 0:45)."""

from __future__ import annotations

import math

import cairo

from hey_joe import config as C
from hey_joe.geometry import (
    SeededParticles,
    draw_lotus,
    glow_disc,
    radial_fill,
    set_rgb,
    sine_spline,
    stroke_ring,
)
from hey_joe.scenes.base import Scene


class NadaScene(Scene):
    name = "nada"

    def __init__(self, width: int, height: int):
        super().__init__(width, height)
        self.dust = SeededParticles(140, seed=101)

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Midnight Navy → dark Indigo radial field
        radial_fill(
            ctx,
            self.cx,
            self.cy,
            0,
            max(self.w, self.h) * 0.75,
            [
                (0.0, C.DARK_INDIGO, 1.0),
                (0.45, (0.07, 0.06, 0.22), 1.0),
                (1.0, C.MIDNIGHT_NAVY, 1.0),
            ],
        )

        # Translucent concentric acoustic rings — slow pulse / expand
        pulse = 0.5 + 0.5 * math.sin(local_t * 0.7)
        for i in range(12):
            base = 40 + i * 48
            expand = (local_t * 28 + i * 18) % (max(self.w, self.h) * 0.7)
            r = base + expand * 0.35
            a = (0.18 - i * 0.01) * (0.55 + 0.45 * pulse) * (1.0 - (expand / (max(self.w, self.h) * 0.7)))
            stroke_ring(ctx, self.cx, self.cy, r, C.GOLD, max(0.0, a), 1.2 + pulse * 0.6)

        # Sparse golden dust with slow wander
        for x, y, s, p in self.dust.positions(local_t, self.w, self.h, drift=0.35):
            tw = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(local_t * 1.2 + p))
            set_rgb(ctx, C.GOLD, 0.15 + 0.35 * tw)
            ctx.arc(x, y, s * 0.7, 0, math.tau)
            ctx.fill()

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Simulated sitar plucks ~ every 2.8s with meend tightening
        pluck_phase = (local_t % 2.8) / 2.8
        pluck = math.exp(-pluck_phase * 5.0)  # sharp attack, soft decay
        freq = 2.2 + pluck * 4.5
        amp = 18 + pluck * 28

        # Horizontal sine-wave splines
        for i, yfrac in enumerate((0.28, 0.38, 0.48, 0.58, 0.68)):
            y = self.h * yfrac
            phase = local_t * (1.1 + i * 0.15) + i
            set_rgb(ctx, C.IVORY if i % 2 == 0 else C.MARIGOLD, 0.25 + pluck * 0.45)
            sine_spline(
                ctx,
                y,
                amp * (0.6 + 0.1 * i),
                freq + i * 0.35,
                phase,
                1.2 + pluck * 1.5,
                -20,
                self.w + 20,
                steps=220,
            )

        # Central Bindhu unfurling into 12-petaled lotus
        unfurl = min(1.0, local_t / 12.0)  # slow reveal over ~12s
        bindu_r = 6 + unfurl * 14
        glow_disc(ctx, self.cx, self.cy, 90 * unfurl + 20, C.BINDU_GOLD, layers=8, peak_alpha=0.5)

        if unfurl > 0.05:
            rot = local_t * 0.08  # meditative rotation
            draw_lotus(
                ctx,
                self.cx,
                self.cy,
                55 + 160 * unfurl,
                petals=12,
                rot=rot,
                stroke_a=C.MARIGOLD,
                stroke_b=C.IVORY,
                layers=3,
            )

        # Core bindu
        glow_disc(ctx, self.cx, self.cy, bindu_r * 2.2, C.BINDU_GOLD, layers=5, peak_alpha=0.7)
        set_rgb(ctx, C.IVORY, 0.95)
        ctx.arc(self.cx, self.cy, bindu_r * 0.55, 0, math.tau)
        ctx.fill()
