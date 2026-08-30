"""Scene 3 — The Flare of Raudra / Betrayal (1:30 – 2:20)."""

from __future__ import annotations

import math
import random

import cairo

from hey_joe import config as C
from hey_joe.geometry import lerp_color, radial_fill, set_rgb, sri_yantra
from hey_joe.scenes.base import Scene


class RaudraScene(Scene):
    name = "raudra"

    def __init__(self, width: int, height: int):
        super().__init__(width, height)
        rng = random.Random(7)
        self.shards = [
            {
                "ang": rng.random() * math.tau,
                "spd": rng.uniform(80, 280),
                "len": rng.uniform(20, 70),
                "w": rng.uniform(1.0, 3.5),
                "phase": rng.random(),
            }
            for _ in range(90)
        ]
        self.sparks = [
            {
                "ang": rng.random() * math.tau,
                "spd": rng.uniform(120, 420),
                "life": rng.uniform(0.4, 1.2),
                "phase": rng.random() * math.tau,
            }
            for _ in range(160)
        ]

    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Pulsating Blood Crimson ↔ Volcanic Burgundy
        beat = 0.5 + 0.5 * math.sin(local_t * 4.2)  # rapid taans energy
        core = lerp_color(C.BLOOD_CRIMSON, C.VOLCANIC_BURGUNDY, 1.0 - beat)
        edge = lerp_color(C.VOLCANIC_BURGUNDY, (0.12, 0.02, 0.04), beat)
        radial_fill(
            ctx,
            self.cx,
            self.cy,
            0,
            max(self.w, self.h) * 0.85,
            [
                (0.0, core, 1.0),
                (0.4, lerp_color(core, edge, 0.5), 1.0),
                (1.0, edge, 1.0),
            ],
        )

        # Symmetrical jagged energy shockwaves
        for wave in range(6):
            phase = (local_t * 1.8 + wave * 0.35) % 1.0
            radius = 40 + phase * max(self.w, self.h) * 0.55
            alpha = (1.0 - phase) ** 1.5 * 0.45
            self._jagged_ring(ctx, radius, alpha, local_t + wave)

    def _jagged_ring(self, ctx: cairo.Context, radius: float, alpha: float, seed_t: float):
        n = 48
        ctx.move_to(self.cx + radius, self.cy)
        for i in range(n + 1):
            a = i * math.tau / n
            jag = 1.0 + 0.12 * math.sin(a * 8 + seed_t * 6) + 0.06 * math.sin(a * 17 - seed_t * 4)
            r = radius * jag
            x = self.cx + math.cos(a) * r
            y = self.cy + math.sin(a) * r
            if i == 0:
                ctx.move_to(x, y)
            else:
                ctx.line_to(x, y)
        set_rgb(ctx, C.ELECTRIC_SAFFRON, alpha)
        ctx.set_line_width(2.2)
        ctx.stroke()

    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        # Downbeat vibration (~ tabla/taan accents every 0.45s)
        down = (local_t % 0.45) / 0.45
        vib = math.exp(-down * 6.0)
        scale = 110 + vib * 35 + 20 * math.sin(local_t * 2.0)

        sri_yantra(
            ctx,
            self.cx,
            self.cy,
            scale,
            rot=local_t * 0.05,
            color_a=C.ELECTRIC_SAFFRON,
            color_b=C.GOLD,
            vib=vib * 3.0,
        )

        # High-velocity radial spark vectors
        for s in self.sparks:
            life_t = (local_t * s["spd"] / 200 + s["phase"]) % s["life"]
            frac = life_t / s["life"]
            dist = 30 + frac * max(self.w, self.h) * 0.55
            x = self.cx + math.cos(s["ang"]) * dist
            y = self.cy + math.sin(s["ang"]) * dist
            a = (1.0 - frac) * 0.85
            set_rgb(ctx, C.ELECTRIC_SAFFRON if frac < 0.4 else C.GOLD, a)
            ctx.arc(x, y, 1.2 + (1.0 - frac) * 2.0, 0, math.tau)
            ctx.fill()
            # trail
            tx = self.cx + math.cos(s["ang"]) * (dist - 18)
            ty = self.cy + math.sin(s["ang"]) * (dist - 18)
            ctx.set_line_width(1.0)
            ctx.move_to(tx, ty)
            ctx.line_to(x, y)
            ctx.stroke()

        # Angular geometric shards
        for sh in self.shards:
            dist = 50 + ((local_t * sh["spd"] + sh["phase"] * 500) % 500)
            ang = sh["ang"] + local_t * 0.2 * sh["phase"]
            x = self.cx + math.cos(ang) * dist
            y = self.cy + math.sin(ang) * dist
            a = max(0.0, 1.0 - dist / 550) * 0.7
            set_rgb(ctx, C.GOLD, a)
            ctx.save()
            ctx.translate(x, y)
            ctx.rotate(ang + math.pi / 2)
            ctx.move_to(0, -sh["len"] * 0.5)
            ctx.line_to(sh["w"] * 3, 0)
            ctx.line_to(0, sh["len"] * 0.5)
            ctx.close_path()
            ctx.fill()
            ctx.restore()
