"""Scene 8 — The Unraveling Noose & Wings of Freedom (6:20 – 7:15)."""

from __future__ import annotations

import math

import cairo

from hey_joe import config as C
from hey_joe.geometry import (
    feather_spline,
    glow_disc,
    lerp,
    log_spiral_points,
    peacock_eye,
    radial_fill,
    set_rgb,
    stroke_ring,
)
from hey_joe.scenes.base import Scene


class WingsScene(Scene):
    name = "wings"

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Expanding sunburst — Royal Blue, Turquoise, Gold (diagonal)
        expand = 0.6 + 0.4 * min(1.0, local_t / 20.0)
        radial_fill(
            ctx,
            self.cx + 40,
            self.cy - 30,
            0,
            max(self.w, self.h) * expand,
            [
                (0.0, C.GOLD, 1.0),
                (0.2, C.TURQUOISE, 1.0),
                (0.55, C.ROYAL_BLUE, 1.0),
                (1.0, (0.04, 0.08, 0.22), 1.0),
            ],
        )

        # Diagonal beam wash
        for i in range(24):
            a = -0.6 + i * (math.pi * 0.9 / 24) + local_t * 0.03
            set_rgb(ctx, C.GOLD, 0.04)
            ctx.set_line_width(3)
            ctx.move_to(self.cx, self.cy)
            ctx.line_to(
                self.cx + math.cos(a) * self.w * 1.2,
                self.cy + math.sin(a) * self.h * 1.2,
            )
            ctx.stroke()

        # Rotating concentric rings of ornamental dots expanding outward
        for ring in range(10):
            phase = (local_t * 0.4 + ring * 0.12) % 1.0
            r = 30 + phase * max(self.w, self.h) * 0.55 + ring * 8
            n = 18 + ring * 4
            rot = local_t * (0.15 if ring % 2 == 0 else -0.12)
            a = (1.0 - phase) * 0.55
            for i in range(n):
                ang = rot + i * math.tau / n
                x = self.cx + math.cos(ang) * r
                y = self.cy + math.sin(ang) * r
                set_rgb(ctx, C.GOLD if i % 2 == 0 else C.IVORY, a * 0.7)
                ctx.arc(x, y, 1.5 + (ring % 3) * 0.5, 0, math.tau)
                ctx.fill()

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Tight spiral noose loosens → unravels into wings
        unravel = min(1.0, local_t / 16.0)
        beat = 0.5 + 0.5 * math.sin(local_t * 2.4)  # rhythmic wing beat

        if unravel < 0.35:
            # constrictive spiral loop
            tightness = 1.0 - unravel / 0.35
            pts = log_spiral_points(
                self.cx,
                self.cy,
                8 + tightness * 20,
                0.22 * tightness + 0.08,
                3.5,
                200,
                local_t * 0.5,
            )
            if pts:
                ctx.move_to(pts[0][0], pts[0][1])
                for p in pts[1:]:
                    ctx.line_to(p[0], p[1])
                set_rgb(ctx, C.GOLD, 0.85)
                ctx.set_line_width(2.5 + tightness * 2)
                ctx.stroke()
        else:
            # wings emerge
            wing_t = (unravel - 0.35) / 0.65
            self._draw_wing(ctx, side=-1, open_t=wing_t, beat=beat, local_t=local_t)
            self._draw_wing(ctx, side=1, open_t=wing_t, beat=beat, local_t=local_t)

        glow_disc(ctx, self.cx, self.cy, 30 + unravel * 20, C.BINDU_GOLD, layers=5, peak_alpha=0.5)
        set_rgb(ctx, C.IVORY, 0.95)
        ctx.arc(self.cx, self.cy, 5, 0, math.tau)
        ctx.fill()

    def _draw_wing(self, ctx, side: int, open_t: float, beat: float, local_t: float):
        """Hundreds of Bézier feather splines ending in peacock eyes."""
        spread = lerp(0.4, 1.0, open_t) * (0.92 + 0.08 * beat)
        # Left wing fans around π, right around 0 — true bilateral wings
        center_ang = math.pi if side < 0 else 0.0
        flap = math.sin(local_t * 2.4) * 0.18 * open_t
        # lift tips slightly upward on the beat
        lift = -0.25 * open_t - 0.08 * beat

        n_feathers = 160
        for i in range(n_feathers):
            frac = i / (n_feathers - 1)
            span = 1.85 * spread
            ang = center_ang + (frac - 0.5) * span * side + flap * side + lift * abs(frac - 0.5)
            # longer primary feathers toward wing mid-span
            length = lerp(100, 380, math.sin(frac * math.pi) ** 0.65) * spread
            length *= 0.88 + 0.12 * beat
            x0 = self.cx + side * 18
            y0 = self.cy + 8
            x1 = self.cx + math.cos(ang) * length
            y1 = self.cy + math.sin(ang) * length

            bulge = 22 + 48 * math.sin(frac * math.pi)
            col = C.TURQUOISE if i % 3 == 0 else (C.ROYAL_BLUE if i % 3 == 1 else (0.1, 0.45, 0.55))
            set_rgb(ctx, col, 0.3 + 0.4 * (1 - frac))
            ctx.set_line_width(1.1 + (1 - frac) * 2.2)
            feather_spline(ctx, x0, y0, x1, y1, bulge, side)
            ctx.stroke()

            if i % 2 == 0:
                set_rgb(ctx, C.GOLD, 0.22)
                ctx.set_line_width(0.8)
                feather_spline(ctx, x0, y0, x1, y1, bulge * 0.55, -side)
                ctx.stroke()

            # dense peacock eyes on outer third
            if frac > 0.5 and i % 3 == 0:
                peacock_eye(ctx, x1, y1, 5 + 10 * (frac - 0.5), ang)
