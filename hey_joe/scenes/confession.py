"""Scene 5 — The Polyrhythmic Confession (3:05 – 4:00)."""

from __future__ import annotations

import math

import cairo

from hey_joe import config as C
from hey_joe.geometry import glow_disc, jali_pattern, set_rgb, sudarshana_chakra
from hey_joe.scenes.base import Scene


class ConfessionScene(Scene):
    name = "confession"

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Dark base
        set_rgb(ctx, (0.06, 0.04, 0.1), 1.0)
        ctx.paint()

        # Dual-layer Jali screens sliding out of phase → moiré
        slide_a = local_t * 28
        slide_b = -local_t * 19
        jali_pattern(
            ctx,
            -40,
            -40,
            self.w + 80,
            self.h + 80,
            cell=46,
            offset=slide_a,
            color=C.DARK_GOLD,
            alpha=0.35,
        )
        jali_pattern(
            ctx,
            -40,
            -40,
            self.w + 80,
            self.h + 80,
            cell=38,
            offset=slide_b,
            color=C.VIOLET,
            alpha=0.28,
        )
        # tertiary finer lattice for denser interference
        jali_pattern(
            ctx,
            -40,
            -40,
            self.w + 80,
            self.h + 80,
            cell=22,
            offset=local_t * 12,
            color=C.GOLD,
            alpha=0.1,
        )

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Tabla / staccato accents ~ 0.28s and 0.5s polyrhythm
        accent_a = math.exp(-((local_t % 0.5) / 0.5) * 8.0)
        accent_b = math.exp(-((local_t % 0.28) / 0.28) * 10.0)
        accent = max(accent_a, accent_b * 0.85)

        # Collapse blades inward on accents then snap out
        collapse = 0.55 + 0.45 * (1.0 - accent) + accent * 0.15

        # 8-fold chakra
        sudarshana_chakra(
            ctx,
            self.cx,
            self.cy,
            160,
            blades=8,
            rot=local_t * 1.1,
            collapse=collapse,
            color=C.VIOLET,
            accent=C.GOLD,
        )
        # 16-fold outer disc
        sudarshana_chakra(
            ctx,
            self.cx,
            self.cy,
            260,
            blades=16,
            rot=-local_t * 0.75,
            collapse=0.7 + 0.3 * collapse,
            color=C.DARK_GOLD,
            accent=C.ELECTRIC_SAFFRON,
        )

        # Flash halos on accented downbeats
        if accent > 0.15:
            glow_disc(
                ctx,
                self.cx,
                self.cy,
                80 + accent * 220,
                C.IVORY,
                layers=7,
                peak_alpha=accent * 0.55,
            )
            set_rgb(ctx, C.GOLD, accent * 0.4)
            ctx.arc(self.cx, self.cy, 40 + accent * 120, 0, math.tau)
            ctx.set_line_width(3 + accent * 6)
            ctx.stroke()
