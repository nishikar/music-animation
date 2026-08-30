"""Scene 6 — The Raga-Rock Solo / The Jhala Vortex (4:00 – 5:20)."""

from __future__ import annotations

import math

import cairo

from hey_joe import config as C
from hey_joe.geometry import (
    bezier_ribbon,
    lerp_color,
    lissajous_points,
    log_spiral_points,
    set_rgb,
)
from hey_joe.scenes.base import Scene


class JhalaScene(Scene):
    name = "jhala"

    PSYCH = [C.ACID_PURPLE, C.MAGENTA, C.SAFFRON, C.TEAL, C.GOLD, C.ROYAL_BLUE]

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Multi-layered logarithmic spiral hyperspace tunnel
        set_rgb(ctx, (0.02, 0.01, 0.05), 1.0)
        ctx.paint()

        hue_shift = int(local_t * 0.8) % len(self.PSYCH)
        # Concentric tunnel rings rushing inward
        for ring in range(22):
            depth = (ring / 22.0 + local_t * 0.22) % 1.0
            r = 12 + depth * depth * depth * max(self.w, self.h) * 0.7
            col = self.PSYCH[(hue_shift + ring) % len(self.PSYCH)]
            alpha = 0.55 * (1.0 - depth) ** 0.7
            set_rgb(ctx, col, alpha)
            ctx.set_line_width(1.0 + (1.0 - depth) * 5)
            ctx.set_dash([6 + depth * 20, 8 + depth * 10])
            ctx.arc(self.cx, self.cy, r, 0, math.tau)
            ctx.stroke()
            ctx.set_dash([])
            # radial spokes for hyperspace feel
            if ring % 2 == 0:
                set_rgb(ctx, col, alpha * 0.45)
                ctx.set_line_width(0.8)
                for s in range(12):
                    a = s * math.tau / 12 + local_t * 0.3 * (1 if ring % 4 == 0 else -1)
                    ctx.move_to(self.cx + math.cos(a) * r * 0.85, self.cy + math.sin(a) * r * 0.85)
                    ctx.line_to(self.cx + math.cos(a) * r, self.cy + math.sin(a) * r)
                ctx.stroke()

        for layer in range(10):
            col = self.PSYCH[(hue_shift + layer) % len(self.PSYCH)]
            next_col = self.PSYCH[(hue_shift + layer + 1) % len(self.PSYCH)]
            mix = lerp_color(col, next_col, 0.35)
            depth = (layer / 10.0 + local_t * 0.15) % 1.0
            scale = 0.1 + depth * 1.5
            a_param = 10 * scale
            b_param = 0.14
            rot = local_t * (0.5 + layer * 0.04) * (1 if layer % 2 == 0 else -1)
            pts = log_spiral_points(self.cx, self.cy, a_param, b_param, 3.8, 200, rot)
            if len(pts) < 2:
                continue
            ctx.move_to(pts[0][0], pts[0][1])
            for p in pts[1:]:
                ctx.line_to(p[0], p[1])
            alpha = 0.2 + 0.4 * (1.0 - abs(depth - 0.5) * 2)
            set_rgb(ctx, mix, alpha)
            ctx.set_line_width(1.8 + (1.0 - depth) * 5)
            ctx.stroke()

        # central vanishing glow
        for i in range(6):
            r = 10 + i * 18
            set_rgb(ctx, C.MAGENTA, 0.2 / (i + 1))
            ctx.arc(self.cx, self.cy, r, 0, math.tau)
            ctx.fill()

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Melodic peak envelope (jhala intensity)
        peak = 0.5 + 0.5 * math.sin(local_t * 3.5) * math.sin(local_t * 1.1)

        # Lissajous harmonic ribbons — guitar vs sitar duel
        for i, (a, b, col) in enumerate(
            [
                (3, 4, C.SAFFRON),
                (5, 4, C.TEAL),
                (3, 5, C.MAGENTA),
                (2, 3, C.GOLD),
            ]
        ):
            delta = local_t * (0.8 + i * 0.2) + i
            ax = 220 + peak * 80 + i * 20
            ay = 140 + peak * 60 + i * 15
            pts = lissajous_points(self.cx, self.cy, ax, ay, a, b, delta, n=360)
            # draw as thick glowing stroke
            if pts:
                ctx.move_to(pts[0][0], pts[0][1])
                for p in pts[1:]:
                    ctx.line_to(p[0], p[1])
                set_rgb(ctx, col, 0.2)
                ctx.set_line_width(6 + peak * 4)
                ctx.stroke_preserve()
                set_rgb(ctx, col, 0.75)
                ctx.set_line_width(1.5 + peak * 1.5)
                ctx.stroke()

        # Counter-rotating spiral arms with dynamic stroke weights
        for arm, direction in enumerate((1, -1)):
            col = C.ELECTRIC_SAFFRON if arm == 0 else C.ACID_PURPLE
            rot = local_t * 1.2 * direction
            expand = 1.0 + peak * 0.45
            pts = log_spiral_points(
                self.cx,
                self.cy,
                20 * expand,
                0.15,
                2.8,
                220,
                rot,
            )
            # variable-width segments
            for i in range(0, len(pts) - 1, 2):
                w = 0.8 + 4.5 * (i / len(pts)) * (0.5 + peak)
                set_rgb(ctx, col, 0.35 + 0.4 * (i / len(pts)))
                ctx.set_line_width(w)
                ctx.move_to(pts[i][0], pts[i][1])
                ctx.line_to(pts[i + 1][0], pts[i + 1][1])
                ctx.stroke()

        # Extra twisting ribbons near tunnel mouth
        for i in range(3):
            pts = []
            for k in range(12):
                ang = local_t * 2 + i * 2.1 + k * 0.35
                r = 60 + k * 22 + peak * 30
                pts.append(
                    (
                        self.cx + math.cos(ang) * r,
                        self.cy + math.sin(ang * 1.3) * r * 0.65,
                    )
                )
            bezier_ribbon(ctx, pts, self.PSYCH[i % len(self.PSYCH)], 0.45, 3 + peak * 3)
