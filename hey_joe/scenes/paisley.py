"""Scene 4 — The Fatal Descent & Paisley Tears (2:20 – 3:05)."""

from __future__ import annotations

import math

import cairo

from hey_joe import config as C
from hey_joe.geometry import draw_paisley, glow_disc, lerp, linear_fill, set_rgb
from hey_joe.scenes.base import Scene


class PaisleyScene(Scene):
    name = "paisley"

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Somber Peacock Teal → Charcoal Black
        linear_fill(
            ctx,
            0,
            0,
            0,
            self.h,
            [
                (0.0, (0.03, 0.12, 0.16), 1.0),
                (0.45, C.PEACOCK_TEAL, 1.0),
                (0.7, (0.04, 0.1, 0.12), 1.0),
                (1.0, C.CHARCOAL, 1.0),
            ],
        )

        # Dark horizontal horizon planes + faint widening elliptical ripples
        horizon = self.h * 0.62
        for i in range(5):
            y = horizon + i * 28
            set_rgb(ctx, (0.02, 0.06, 0.08), 0.35 + i * 0.08)
            ctx.rectangle(0, y, self.w, 3 + i)
            ctx.fill()

        for i in range(7):
            phase = (local_t * 0.35 + i * 0.18) % 1.0
            rx = 40 + phase * self.w * 0.55
            ry = 8 + phase * 40
            a = (1.0 - phase) * 0.25
            set_rgb(ctx, C.TEAL, a)
            ctx.save()
            ctx.translate(self.cx, horizon)
            ctx.scale(1.0, ry / max(rx, 1e-3))
            ctx.arc(0, 0, rx, 0, math.tau)
            ctx.set_line_width(1.5)
            ctx.stroke()
            ctx.restore()

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Teardrop accelerates down center axis, then bursts into paisleys
        fall_dur = 12.0
        if local_t < fall_dur:
            u = local_t / fall_dur
            # ease-in acceleration
            u2 = u * u
            y = lerp(self.h * 0.12, self.h * 0.72, u2)
            size = 18 + u * 10
            glow_disc(ctx, self.cx, y, size * 2.5, C.TEAL, layers=6, peak_alpha=0.45)
            self._teardrop(ctx, self.cx, y, size, C.BINDU_GOLD, C.IVORY)
        else:
            burst_t = local_t - fall_dur
            self._burst_paisleys(ctx, burst_t)

        # Paisley vines unfurling upward along borders like mourning drapes
        unfurl = min(1.0, local_t / 18.0)
        self._border_vines(ctx, local_t, unfurl, side=-1)
        self._border_vines(ctx, local_t, unfurl, side=1)

    def _teardrop(self, ctx, x, y, size, fill, stroke):
        ctx.save()
        ctx.translate(x, y)
        ctx.move_to(0, -size)
        ctx.curve_to(size * 0.75, -size * 0.2, size * 0.7, size * 0.6, 0, size)
        ctx.curve_to(-size * 0.7, size * 0.6, -size * 0.75, -size * 0.2, 0, -size)
        ctx.close_path()
        set_rgb(ctx, fill, 0.85)
        ctx.fill_preserve()
        set_rgb(ctx, stroke, 0.9)
        ctx.set_line_width(1.5)
        ctx.stroke()
        ctx.restore()

    def _burst_paisleys(self, ctx, burst_t: float):
        n = 16
        for i in range(n):
            ang = -math.pi / 2 + (i / n) * math.tau
            dist = min(220, burst_t * 55) * (0.6 + 0.4 * ((i * 7) % 5) / 5)
            px = self.cx + math.cos(ang) * dist
            py = self.h * 0.72 + math.sin(ang) * dist * 0.55
            draw_paisley(
                ctx,
                px,
                py,
                22 + (i % 4) * 6,
                ang + math.pi / 2,
                C.PEACOCK_TEAL,
                C.GOLD,
                fill_a=0.35,
                stroke_a=0.8,
            )

    def _border_vines(self, ctx, local_t: float, unfurl: float, side: int):
        x_base = self.w * 0.06 if side < 0 else self.w * 0.94
        count = int(14 * unfurl)
        for i in range(count):
            y = self.h * 0.95 - i * (self.h * 0.06 * unfurl)
            sway = math.sin(local_t * 0.6 + i * 0.5) * 12 * side
            size = 28 + (i % 3) * 8
            draw_paisley(
                ctx,
                x_base + sway,
                y,
                size,
                -math.pi / 2 + side * 0.4 + math.sin(local_t * 0.3 + i) * 0.15,
                (0.04, 0.2, 0.22),
                C.GOLD,
                fill_a=0.4,
                stroke_a=0.7,
            )
            # recursive smaller child
            draw_paisley(
                ctx,
                x_base + sway + side * 22,
                y - 18,
                size * 0.45,
                -math.pi / 2 - side * 0.8,
                C.PEACOCK_TEAL,
                C.MARIGOLD,
                fill_a=0.3,
                stroke_a=0.55,
            )
