"""Scene 2 — The Revolving Enigma (0:45 – 1:30)."""

from __future__ import annotations

import math

import cairo

from hey_joe import config as C
from hey_joe.geometry import (
    bezier_ribbon,
    dashed_spokes,
    draw_paisley,
    lerp_color,
    linear_fill,
    set_rgb,
    stroke_ring,
)
from hey_joe.scenes.base import Scene


class EnigmaScene(Scene):
    name = "enigma"

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Atmospheric gradient: Deep Amethyst ↔ Charcoal ↔ Navy
        pulse = 0.5 + 0.5 * math.sin(local_t * 0.35)
        top = lerp_color(C.DEEP_AMETHYST, C.NAVY, 0.3 + 0.3 * pulse)
        mid = lerp_color(C.CHARCOAL, C.DEEP_AMETHYST, 0.4)
        bot = lerp_color(C.NAVY, C.CHARCOAL, pulse)
        linear_fill(
            ctx,
            0,
            0,
            0,
            self.h,
            [(0.0, top, 1.0), (0.5, mid, 1.0), (1.0, bot, 1.0)],
        )

        # Giant low-opacity geometric wheel — dashed rings + spokes, counter-rotation
        rot_a = local_t * 0.12
        rot_b = -local_t * 0.09
        for i in range(8):
            r = 80 + i * 55
            stroke_ring(
                ctx,
                self.cx,
                self.cy,
                r,
                C.GOLD,
                0.08 + 0.02 * (i % 3),
                1.0,
                dash=(8 + i * 2, 10 + i),
            )
        dashed_spokes(ctx, self.cx, self.cy, 60, 480, 24, rot_a, C.IVORY, 0.07, 0.8)
        dashed_spokes(ctx, self.cx, self.cy, 100, 520, 16, rot_b, C.GOLD, 0.06, 0.9)
        stroke_ring(ctx, self.cx, self.cy, 420, C.VIOLET, 0.12, 2.0, dash=(14, 18))

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # 6-chambered cylinder motif (revolver × sitar pegbox)
        self._draw_cylinder(ctx, local_t)

        # Floral filigree vines through chambers
        self._draw_filigree(ctx, local_t)

        # Translucent Bézier smoke ribbons — vertical, swaying
        for i in range(5):
            pts = []
            base_x = self.cx + (i - 2) * 70
            for k in range(10):
                yy = self.h * 0.95 - k * (self.h * 0.09)
                sway = math.sin(local_t * 0.9 + i * 0.7 + k * 0.4) * (18 + k * 3)
                pts.append((base_x + sway, yy))
            bezier_ribbon(
                ctx,
                pts,
                (0.75, 0.72, 0.78),
                0.12 + 0.04 * (i % 2),
                14 - i,
            )

    def _draw_cylinder(self, ctx: cairo.Context, local_t: float):
        cx, cy = self.cx, self.cy
        R = 155
        rot = local_t * 0.15
        # outer barrel
        set_rgb(ctx, (0.18, 0.16, 0.2), 0.85)
        ctx.arc(cx, cy, R, 0, math.tau)
        ctx.fill()
        stroke_ring(ctx, cx, cy, R, C.GOLD, 0.75, 2.5)
        stroke_ring(ctx, cx, cy, R * 0.92, C.IVORY, 0.35, 1.0)

        # six chambers
        for i in range(6):
            a = rot + i * (math.tau / 6)
            hx = cx + math.cos(a) * R * 0.52
            hy = cy + math.sin(a) * R * 0.52
            cr = R * 0.22
            # chamber bore
            set_rgb(ctx, (0.05, 0.05, 0.07), 0.95)
            ctx.arc(hx, hy, cr, 0, math.tau)
            ctx.fill()
            stroke_ring(ctx, hx, hy, cr, C.GOLD, 0.7, 1.5)
            # sitar pegbox bridge hint — small bar across chamber
            set_rgb(ctx, C.DARK_GOLD, 0.8)
            ctx.set_line_width(2.0)
            tang = a + math.pi / 2
            ctx.move_to(hx + math.cos(tang) * cr * 0.7, hy + math.sin(tang) * cr * 0.7)
            ctx.line_to(hx - math.cos(tang) * cr * 0.7, hy - math.sin(tang) * cr * 0.7)
            ctx.stroke()
            # peg knob
            set_rgb(ctx, C.MARIGOLD, 0.85)
            ctx.arc(hx + math.cos(a) * cr * 0.15, hy + math.sin(a) * cr * 0.15, 4, 0, math.tau)
            ctx.fill()

        # central spindle
        set_rgb(ctx, C.GOLD, 0.9)
        ctx.arc(cx, cy, 18, 0, math.tau)
        ctx.fill()
        set_rgb(ctx, C.IVORY, 0.95)
        ctx.arc(cx, cy, 7, 0, math.tau)
        ctx.fill()

    def _draw_filigree(self, ctx: cairo.Context, local_t: float):
        for i in range(6):
            a = local_t * 0.15 + i * (math.tau / 6)
            for k in range(3):
                rr = 95 + k * 28
                px = self.cx + math.cos(a + k * 0.2) * rr
                py = self.cy + math.sin(a + k * 0.2) * rr
                draw_paisley(
                    ctx,
                    px,
                    py,
                    16 + k * 4,
                    a + math.pi / 2,
                    C.VIOLET,
                    C.GOLD,
                    fill_a=0.2,
                    stroke_a=0.55,
                )
