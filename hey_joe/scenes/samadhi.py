"""Scene 9 — Dissolution / Samadhi (7:15 – 7:51)."""

from __future__ import annotations

import math
import random

import cairo

from hey_joe import config as C
from hey_joe.geometry import glow_disc, lerp, lerp_color, radial_fill, set_rgb
from hey_joe.scenes.base import Scene


class SamadhiScene(Scene):
    name = "samadhi"

    def __init__(self, width: int, height: int):
        super().__init__(width, height)
        rng = random.Random(99)
        # Fractured structures → stardust cloud
        self.stars = [
            {
                "ang": rng.random() * math.tau,
                "r0": rng.uniform(40, 380),
                "size": rng.uniform(0.6, 2.8),
                "spin": rng.uniform(-0.4, 0.4),
                "phase": rng.random() * math.tau,
            }
            for _ in range(520)
        ]

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Smooth fade toward Midnight Navy / Black cosmic void
        # Scene duration = 36s (435→471); final black at 07:51
        fade = min(1.0, local_t / 36.0)
        core_glow = max(0.0, 1.0 - fade * 1.1)
        center = lerp_color(C.DARK_INDIGO, C.BLACK, fade)
        edge = lerp_color(C.MIDNIGHT_NAVY, C.BLACK, fade * 0.9)

        radial_fill(
            ctx,
            self.cx,
            self.cy,
            0,
            max(self.w, self.h) * (0.35 + 0.4 * (1.0 - fade)),
            [
                (0.0, lerp_color(C.BINDU_GOLD, center, 1.0 - core_glow * 0.35), core_glow * 0.5 + 0.1),
                (0.35, center, 1.0),
                (1.0, edge, 1.0),
            ],
        )

        # Soft diminishing central radial glow contracts over time
        if core_glow > 0.02:
            glow_disc(
                ctx,
                self.cx,
                self.cy,
                180 * core_glow,
                C.DARK_INDIGO,
                layers=8,
                peak_alpha=0.35 * core_glow,
            )

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        duration = 36.0
        # Phases: fracture swirl (0-22s) → merge to bindu (22-30s) → 3 pulses → black at 36s
        merge_start = 22.0
        pulse_start = 30.0

        if local_t < merge_start:
            pull = local_t / merge_start  # 0→1 gradually inward
            for s in self.stars:
                # Spiral inward via gravitational pull
                r = s["r0"] * (1.0 - pull * 0.85) * (0.7 + 0.3 * math.sin(s["phase"]))
                ang = s["ang"] + local_t * s["spin"] + pull * 2.5
                x = self.cx + math.cos(ang) * r
                y = self.cy + math.sin(ang) * r
                a = 0.3 + 0.5 * (1.0 - pull * 0.5)
                set_rgb(ctx, C.GOLD, a)
                ctx.arc(x, y, s["size"] * (1.0 - pull * 0.4), 0, math.tau)
                ctx.fill()
                # faint trail
                if pull > 0.2:
                    set_rgb(ctx, C.GOLD, a * 0.25)
                    ctx.set_line_width(0.6)
                    x2 = self.cx + math.cos(ang - 0.15) * (r + 8)
                    y2 = self.cy + math.sin(ang - 0.15) * (r + 8)
                    ctx.move_to(x2, y2)
                    ctx.line_to(x, y)
                    ctx.stroke()

            # residual fractured geometry shards
            for i in range(12):
                ang = i * math.tau / 12 + local_t * 0.2
                r = 200 * (1.0 - pull)
                set_rgb(ctx, C.IVORY, 0.15 * (1.0 - pull))
                ctx.set_line_width(1.2)
                ctx.move_to(self.cx, self.cy)
                ctx.line_to(self.cx + math.cos(ang) * r, self.cy + math.sin(ang) * r)
                ctx.stroke()

        elif local_t < pulse_start:
            # Merge into singular bindu
            u = (local_t - merge_start) / (pulse_start - merge_start)
            remaining = int(80 * (1.0 - u))
            for i, s in enumerate(self.stars[: max(1, remaining)]):
                r = s["r0"] * 0.15 * (1.0 - u)
                ang = s["ang"] + local_t * s["spin"]
                x = lerp(self.cx + math.cos(ang) * r, self.cx, u)
                y = lerp(self.cy + math.sin(ang) * r, self.cy, u)
                set_rgb(ctx, C.GOLD, 0.6 * (1.0 - u * 0.5))
                ctx.arc(x, y, s["size"] * (1.0 - u * 0.7), 0, math.tau)
                ctx.fill()
            glow_disc(ctx, self.cx, self.cy, 40 + u * 20, C.BINDU_GOLD, layers=7, peak_alpha=0.6)
            set_rgb(ctx, C.IVORY, 0.95)
            ctx.arc(self.cx, self.cy, 6 + u * 4, 0, math.tau)
            ctx.fill()

        else:
            # Three gentle pulses then fade entirely to black at 07:51
            pulse_t = local_t - pulse_start  # 0→6s
            # three pulses at 0.5s, 2.0s, 3.5s
            pulse_amp = 0.0
            for pt in (0.5, 2.0, 3.5):
                d = abs(pulse_t - pt)
                pulse_amp = max(pulse_amp, math.exp(-d * 4.0))

            fade_out = clamp01((pulse_t - 4.0) / 2.0)  # last 2s → black
            if fade_out >= 1.0 - 1e-6:
                set_rgb(ctx, C.BLACK, 1.0)
                ctx.paint()
                return

            br = 8 + pulse_amp * 22
            glow_disc(
                ctx,
                self.cx,
                self.cy,
                br * 3 * (1.0 - fade_out),
                C.BINDU_GOLD,
                layers=6,
                peak_alpha=0.65 * (1.0 - fade_out),
            )
            set_rgb(ctx, C.IVORY, 0.95 * (1.0 - fade_out))
            ctx.arc(self.cx, self.cy, max(0.5, br * 0.35 * (1.0 - fade_out)), 0, math.tau)
            ctx.fill()

            # final veil to black
            if fade_out > 0:
                set_rgb(ctx, C.BLACK, fade_out)
                ctx.paint()


def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v
