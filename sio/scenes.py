"""Six timed scenes for the Shake It Off Himalayan synthwave visualizer."""

from __future__ import annotations

import math
import random

import moderngl
import numpy as np

from . import BEAT_SEC, GOLD, HEIGHT, MARIGOLD, SCENES, SONG_DURATION, VERMILLION, WIDTH
from .audio import AudioAnalysis
from .geometry import (
    circle_ring,
    cylinder_wire,
    grid_valley,
    lattice_structure,
    lowpoly_stupa,
    mandala_tiers,
    pagoda_wireframe,
    polyline,
    regular_polygon,
    solid_lathe_bell,
    tea_glass_wire,
)
from .math3d import (
    look_at,
    mul,
    perspective,
    rotate_x,
    rotate_y,
    rotate_z,
    scale,
    translate,
)
from .pipeline import Pipeline



def vertical_hex_ring(radius, z=0.0, color=(0.1, 1.0, 0.55), sides=6) -> np.ndarray:
    """Hexagon lying in the XY plane (tunnel portal facing along Z)."""
    verts = []
    for i in range(sides):
        a0 = (i / sides) * math.tau
        a1 = ((i + 1) / sides) * math.tau
        p0 = (math.cos(a0) * radius, math.sin(a0) * radius, z)
        p1 = (math.cos(a1) * radius, math.sin(a1) * radius, z)
        verts.extend([*p0, *color, *p1, *color])
    return np.asarray(verts, dtype=np.float32)

def scene_id_at(t: float) -> str:
    for a, b, name in SCENES:
        if a <= t < b:
            return name
    return SCENES[-1][2]


class ParticleStorm:
    def __init__(self, n=1200, mode="radial"):
        self.n = n
        self.mode = mode
        self.pos = np.zeros((n, 3), dtype=np.float32)
        self.vel = np.zeros((n, 3), dtype=np.float32)
        self.color = np.zeros((n, 3), dtype=np.float32)
        self.size = np.ones(n, dtype=np.float32) * 4.0
        self.life = np.zeros(n, dtype=np.float32)
        self.rng = np.random.default_rng(42)
        for i in range(n):
            self.respawn(i, initial=True)

    def respawn(self, i: int, initial: bool = False):
        if self.mode == "radial":
            a = float(self.rng.uniform(0, math.tau))
            r = float(self.rng.uniform(0.2, 0.8) if initial else 0.15)
            self.pos[i] = (math.cos(a) * r, float(self.rng.uniform(-0.2, 1.5)), math.sin(a) * r)
            speed = float(self.rng.uniform(1.5, 4.0))
            self.vel[i] = (math.cos(a) * speed, float(self.rng.uniform(0.5, 2.5)), math.sin(a) * speed)
            self.color[i] = (1.0, float(self.rng.uniform(0.55, 0.9)), float(self.rng.uniform(0.05, 0.25)))
            self.size[i] = float(self.rng.uniform(3.0, 9.0))
            self.life[i] = float(self.rng.uniform(0.5, 1.0) if initial else 1.0)
        elif self.mode == "gold_dust":
            self.pos[i] = (
                float(self.rng.uniform(-4, 4)),
                float(self.rng.uniform(0, 6)),
                float(self.rng.uniform(-4, 4)),
            )
            self.vel[i] = (
                float(self.rng.uniform(-0.3, 0.3)),
                float(self.rng.uniform(0.4, 1.8)),
                float(self.rng.uniform(-0.3, 0.3)),
            )
            self.color[i] = (1.0, float(self.rng.uniform(0.7, 0.95)), float(self.rng.uniform(0.15, 0.4)))
            self.size[i] = float(self.rng.uniform(2.0, 5.0))
            self.life[i] = float(self.rng.uniform(0.3, 1.0))
        else:
            a = float(self.rng.uniform(0, math.tau))
            self.pos[i] = (math.cos(a) * 2.5, float(self.rng.uniform(0.5, 4)), math.sin(a) * 2.5)
            self.vel[i] = (-math.sin(a) * 2.5, float(self.rng.uniform(-0.2, 0.8)), math.cos(a) * 2.5)
            self.color[i] = (0.95, float(self.rng.uniform(0.05, 0.25)), float(self.rng.uniform(0.05, 0.2)))
            self.size[i] = float(self.rng.uniform(4.0, 12.0))
            self.life[i] = float(self.rng.uniform(0.4, 1.0))

    def update(self, dt: float, boost: float = 0.0):
        if self.mode == "radial":
            self.pos += self.vel * dt * (1.0 + boost)
            x, z = self.pos[:, 0].copy(), self.pos[:, 2].copy()
            self.pos[:, 0] += -z * dt * 1.2
            self.pos[:, 2] += x * dt * 1.2
            self.vel[:, 1] -= 0.4 * dt
            self.life -= dt * 0.35
        elif self.mode == "gold_dust":
            self.pos += self.vel * dt * (1.0 + boost * 0.5)
            self.pos[:, 0] += np.sin(self.pos[:, 1] * 2 + self.life * 5) * dt * 0.4
            self.life -= dt * 0.2
            self.life[self.pos[:, 1] > 7] = 0
        else:
            self.pos += self.vel * dt
            x, z = self.pos[:, 0].copy(), self.pos[:, 2].copy()
            self.pos[:, 0] += -z * dt * 0.9
            self.pos[:, 2] += x * dt * 0.9
            self.life -= dt * 0.15
        for i in np.where(self.life <= 0)[0]:
            self.respawn(int(i))

    def pack(self) -> np.ndarray:
        out = np.zeros((self.n, 7), dtype=np.float32)
        out[:, 0:3] = self.pos
        out[:, 3:6] = self.color * self.life[:, None]
        out[:, 6] = self.size * (0.4 + 0.6 * self.life)
        return out.reshape(-1)


class SceneManager:
    def __init__(self, pipeline: Pipeline):
        self.pipe = pipeline
        self.ctx = pipeline.ctx
        self.proj = perspective(60.0, WIDTH / float(HEIGHT), 0.1, 200.0)
        self.active_banner: tuple[str, str] | None = None
        self.shake_amp = 0.0
        self.shockwaves: list[dict] = []
        self.beacon_life = 1.0
        self._temps: list = []

        self.marigold = ParticleStorm(1400, "radial")
        self.gold_dust = ParticleStorm(800, "gold_dust")
        self.streamers = ParticleStorm(600, "streamers")
        self.p_vbo, self.p_vao = pipeline.make_particle_buffer(2000)

        # Scene 1
        self.valley = pipeline.make_line_mesh(grid_valley(36, 70, scale=1.15))
        bell_v, bell_i = solid_lathe_bell(40)
        self.bell = pipeline.make_solid_mesh(bell_v, bell_i)

        # Scene 2
        self.tiers = mandala_tiers()
        self.tier_meshes = []
        for tier in self.tiers:
            wire = regular_polygon(
                tier["sides"], tier["radius"], y=0.0, color=tier["color"], star=tier["star"]
            )
            bottom = regular_polygon(
                tier["sides"],
                tier["radius"] * 0.92,
                y=-tier["thick"],
                color=tier["color"],
                star=tier["star"],
            )
            chunks = [wire, bottom]
            for i in range(tier["sides"]):
                a = (i / tier["sides"]) * math.tau - math.pi / 2
                r = tier["radius"]
                p0 = (math.cos(a) * r, 0.0, math.sin(a) * r)
                p1 = (math.cos(a) * r * 0.92, -tier["thick"], math.sin(a) * r * 0.92)
                chunks.append(polyline([p0, p1], tier["color"]))
            self.tier_meshes.append(pipeline.make_line_mesh(np.concatenate(chunks)))
        fin = [circle_ring(0.18 - i * 0.02, y=i * 0.08, segments=16, color=GOLD) for i in range(6)]
        fin.append(circle_ring(0.05, y=0.55, segments=12, color=VERMILLION))
        self.finial = pipeline.make_line_mesh(np.concatenate(fin))

        # Scene 3
        hexes = []
        for i in range(40):
            z = -i * 2.2
            c = (0.1, 1.0, 0.55) if i % 2 == 0 else (0.15, 0.85, 1.0)
            hexes.append(vertical_hex_ring(3.2, z=z, color=c, sides=6))
            # also slightly smaller inner ring for thickness
            hexes.append(vertical_hex_ring(3.05, z=z, color=c, sides=6))
            for s in range(6):
                a = (s / 6) * math.tau
                p0 = (math.cos(a) * 3.2, math.sin(a) * 3.2, z)
                p1 = (math.cos(a) * 3.2, math.sin(a) * 3.2, z - 2.2)
                hexes.append(polyline([p0, p1], c))
        self.corridor = pipeline.make_line_mesh(np.concatenate(hexes))
        self.wheel_mesh = pipeline.make_line_mesh(
            cylinder_wire(0.55, 2.4, segments=20, color=(1.0, 0.78, 0.18), rings=6)
        )
        self.wheel_positions = []
        for i in range(24):
            z = -i * 2.2 - 1.0
            self.wheel_positions.append((-2.4, 0.0, z, 1 if i % 2 == 0 else -1))
            self.wheel_positions.append((2.4, 0.0, z, -1 if i % 2 == 0 else 1))
        self.eq_vbo = self.ctx.buffer(reserve=64 * 24 * 6 * 4)
        self.eq_vao = self.ctx.vertex_array(
            pipeline.line_prog,
            [(self.eq_vbo, "3f 3f", "in_pos", "in_color")],
        )

        # Scene 4
        self.tea = pipeline.make_line_mesh(tea_glass_wire())
        self.lattice = pipeline.make_line_mesh(lattice_structure())
        grid = []
        for x in range(-8, 9):
            grid.append(polyline([(x, 0, -8), (x, 0, 8)], (1.0, 0.45, 0.1)))
        for z in range(-8, 9):
            grid.append(polyline([(-8, 0, z), (8, 0, z)], (1.0, 0.45, 0.1)))
        for side in (-1, 1):
            pts = [
                (side * (3 + i * 0.4), 0.2 + abs(math.sin(i * 0.7)) * 2.2, -6 + i * 0.1)
                for i in range(20)
            ]
            grid.append(polyline(pts, (1.0, 0.15, 0.1)))
        self.arcade_grid = pipeline.make_line_mesh(np.concatenate(grid))
        self.banners = [
            (160.0, 166.0, "YO KURO!", "CHAI TIME"),
            (166.0, 172.0, "ARCADE SHAKE", "हल्ला मच्चाऊ"),
            (172.0, 178.0, "MILK TEA", "वार्म अप"),
            (178.0, 183.0, "SHAKE IT", "झटका दे"),
            (183.0, 186.0, "OH MY GOD!", "ओ माई गड!"),
        ]

        # Scene 5
        self.pagoda = pipeline.make_line_mesh(pagoda_wireframe())
        fairy = []
        rng = random.Random(9)
        self.fairy_bulbs: list[list[float]] = []
        for s in range(8):
            pts = []
            for k in range(24):
                tt = k / 23
                x = -6 + tt * 12
                y = 5.5 + s * 0.15 + math.sin(tt * 6 + s) * 0.2
                z = math.sin(tt * math.pi * 2 + s) * 2.5 + rng.uniform(-0.3, 0.3)
                pts.append((x, y, z))
                self.fairy_bulbs.append([x, y, z])
            fairy.append(polyline(pts, (1.0, 0.85, 0.35)))
        self.fairy_lines = pipeline.make_line_mesh(np.concatenate(fairy))
        floor = []
        for x in range(-10, 11):
            floor.append(polyline([(x * 0.6, 0, -10), (x * 0.6, 0, 6)], (0.9, 0.15, 0.2)))
        for z in range(-10, 7):
            floor.append(polyline([(-6, 0, z * 0.6), (6, 0, z * 0.6)], (1.0, 0.7, 0.15)))
        self.festival_floor = pipeline.make_line_mesh(np.concatenate(floor))
        sil = []
        for i in range(12):
            x = -9 + i * 1.6
            h = 1.2 + (i * 37 % 5) * 0.35
            sil.append(
                polyline(
                    [
                        (x, 0, -8),
                        (x, h, -8),
                        (x + 0.4, h * 0.7, -8),
                        (x + 0.8, h, -8),
                        (x + 0.8, 0, -8),
                    ],
                    (0.3, 0.25, 0.2),
                )
            )
        self.silhouettes = pipeline.make_line_mesh(np.concatenate(sil))

        # Scene 6
        self.ridge = pipeline.make_line_mesh(grid_valley(40, 50, scale=1.3))
        stupas = [
            lowpoly_stupa(sx, sz, scale=0.7 + i * 0.08)
            for i, (sx, sz) in enumerate([(-4, -6), (-1.5, -10), (2.5, -8), (5, -14), (-6, -16)])
        ]
        self.stupas = pipeline.make_line_mesh(np.concatenate(stupas))
        flags = []
        colors = [(0.2, 0.4, 1), (1, 1, 1), (0.9, 0.1, 0.1), (0.1, 0.7, 0.2), (1, 0.85, 0.1)]
        for fi in range(5):
            pts = []
            for k in range(20):
                tt = k / 19
                x = -5 + tt * 10
                y = 2.2 + math.sin(tt * 8 + fi) * 0.15
                z = -4 - fi * 1.5
                pts.append((x, y, z))
            flags.append(polyline(pts, colors[fi % 5]))
            flags.append(polyline([(-5, 0, -4 - fi * 1.5), (-5, 2.4, -4 - fi * 1.5)], (0.4, 0.25, 0.1)))
            flags.append(polyline([(5, 0, -4 - fi * 1.5), (5, 2.4, -4 - fi * 1.5)], (0.4, 0.25, 0.1)))
        self.flags = pipeline.make_line_mesh(np.concatenate(flags))

    def _mvp(self, view, model=None):
        if model is None:
            return mul(self.proj, view)
        return mul(self.proj, view, model)

    def _upload_particles(self, storm: ParticleStorm) -> int:
        data = storm.pack()
        self.p_vbo.write(data.tobytes())
        return storm.n

    def _clear_temps(self):
        for m in self._temps:
            try:
                m.vao.release()
            except Exception:
                pass
        self._temps.clear()

    def _temp_lines(self, data: np.ndarray):
        mesh = self.pipe.make_line_mesh(data)
        self._temps.append(mesh)
        return mesh

    def render(self, t: float, audio: AudioAnalysis, force_scene: str | None = None):
        self._clear_temps()
        name = force_scene or scene_id_at(t)
        self.pipe.crt_mode = 1 if name == "chai" else 0
        self.pipe.shake = [0.0, 0.0]
        self.active_banner = None

        if name == "mountain":
            self._render_mountain(t, audio)
        elif name == "mandala":
            self._render_mandala(t, audio)
        elif name == "corridor":
            self._render_corridor(t, audio)
        elif name == "chai":
            self._render_chai(t, audio)
        elif name == "pagoda":
            self._render_pagoda(t, audio)
        else:
            self._render_twilight(t, audio)

        self.pipe.end_and_composite(time=t)

    def _render_mountain(self, t, audio: AudioAnalysis):
        pipe = self.pipe
        pipe.begin_scene((0.02, 0.02, 0.08, 1))
        pipe.draw_background(
            top=(0.04, 0.03, 0.12),
            mid=(0.25, 0.05, 0.28),
            bot=(0.08, 0.04, 0.18),
            star_amount=0.7,
            time=t,
        )
        z = -t * 4.5
        eye = (math.sin(t * 0.15) * 1.2, 3.2 + audio.bass * 0.3, z + 8)
        target = (0.0, 1.5, z - 10)
        view = look_at(eye, target)

        if audio.drop or (audio.beat and audio.bass > 0.55):
            self.shockwaves.append({"r": 0.3, "life": 1.0, "y": 2.2})

        # Scroll valley under the camera so the pass feels infinite
        scroll = translate(0.0, 0.0, z + 20.0)
        mvp = self._mvp(view, scroll)
        pipe.draw_lines(self.valley, mvp, time=t, pulse=audio.bass)
        # second tile ahead
        pipe.draw_lines(self.valley, self._mvp(view, translate(0.0, 0.0, z + 20.0 - 70.0)), time=t, pulse=audio.bass)
        mvp = self._mvp(view)

        sway = math.sin(t * (118 / 60) * math.pi) * 0.12 + audio.bass * 0.08
        model = mul(translate(0, 4.5, z - 2), rotate_z(sway), scale(1.1))
        pipe.draw_solid(
            self.bell,
            self._mvp(view, model),
            model,
            light_dir=(0.3, -0.7, 0.4),
            light_color=(1.0, 0.85, 0.5),
        )
        hang = self._temp_lines(polyline([(0, 8.5, z - 2), (0, 5.7, z - 2)], (0.2, 0.9, 1.0)))
        pipe.draw_lines(hang, mvp, pulse=audio.treble)

        alive = []
        for sw in self.shockwaves:
            sw["r"] += (2.8 + audio.bass * 2) * (1 / 60)
            sw["life"] -= 0.012
            if sw["life"] <= 0:
                continue
            alive.append(sw)
            col = (
                VERMILLION[0] * sw["life"] + MARIGOLD[0] * (1 - sw["life"]),
                VERMILLION[1] * sw["life"] + MARIGOLD[1] * (1 - sw["life"]),
                VERMILLION[2] * sw["life"] + MARIGOLD[2] * (1 - sw["life"]),
            )
            ring = circle_ring(sw["r"], y=sw["y"], segments=72, color=col, z=z - 2)
            pipe.draw_lines(self._temp_lines(ring), mvp, pulse=sw["life"])
        self.shockwaves = alive[-12:]
        pipe.bloom_strength = 0.9 + audio.bass * 0.3

    def _render_mandala(self, t, audio: AudioAnalysis):
        pipe = self.pipe
        pipe.begin_scene((0.01, 0.01, 0.03, 1))
        pipe.draw_background(
            top=(0.01, 0.01, 0.04),
            mid=(0.08, 0.02, 0.1),
            bot=(0.02, 0.01, 0.05),
            star_amount=1.0,
            time=t,
        )
        local = t - 41.0
        bounce = 1.0 + audio.amp * 0.12 + abs(math.sin(local * math.pi / BEAT_SEC)) * 0.05
        view = look_at((0.0, 7.5 + math.sin(local * 0.3) * 0.4, 7.5), (0.0, 1.2, 0.0))

        for i, (tier, mesh) in enumerate(zip(self.tiers, self.tier_meshes)):
            direction = 1 if i % 2 == 0 else -1
            ang = local * (0.6 + i * 0.08) * direction + audio.mid * 0.4 * direction
            expand = bounce * (1.0 + 0.04 * math.sin(local * 3 + i) + audio.bass * 0.05)
            model = mul(
                translate(0, tier["y"] * bounce, 0),
                rotate_y(ang),
                scale(expand, 1.0, expand),
            )
            pipe.draw_lines(mesh, self._mvp(view, model), time=t, pulse=audio.bass)
        fin_model = mul(translate(0, self.tiers[-1]["y"] * bounce + 0.2, 0), scale(bounce))
        pipe.draw_lines(self.finial, self._mvp(view, fin_model), pulse=audio.treble)

        self.marigold.update(1 / 60, boost=audio.amp)
        if audio.beat:
            for _ in range(40):
                self.marigold.respawn(random.randrange(self.marigold.n))
        n = self._upload_particles(self.marigold)
        pipe.draw_particles(self.p_vao, n, self._mvp(view))
        pipe.bloom_strength = 1.0 + audio.amp * 0.4

    def _render_corridor(self, t, audio: AudioAnalysis):
        pipe = self.pipe
        pipe.begin_scene((0.0, 0.0, 0.0, 1))
        pipe.draw_background(
            top=(0.0, 0.0, 0.0),
            mid=(0.0, 0.02, 0.03),
            bot=(0.0, 0.0, 0.0),
            star_amount=0.0,
            time=t,
        )
        local = t - 72.0
        speed = 14.0 + audio.mid * 4
        z = -local * speed
        view = look_at((math.sin(local * 0.7) * 0.15, 0.2, z), (0.0, 0.0, z - 8))

        model = translate(0, 0, -(((-z) % 2.2)))
        pipe.draw_lines(self.corridor, self._mvp(view, model), time=t, pulse=audio.treble)

        for x, y, wz, direction in self.wheel_positions:
            rel = wz - z
            while rel > 2:
                rel -= 24 * 2.2
            while rel < -50:
                rel += 24 * 2.2
            ang = local * 4.0 * direction + audio.bass * 2
            wm = mul(translate(x, y, z + rel), rotate_y(ang))
            pipe.draw_lines(self.wheel_mesh, self._mvp(view, wm), pulse=audio.bass)

        bars = []
        nbar = 48
        for i in range(nbar):
            spec_i = float(audio.spectrum[i % 64])
            h = 0.15 + spec_i * (2.5 + audio.amp * 2)
            x = -3.2 + (i / (nbar - 1)) * 6.4
            col = (1.0, 0.15 + 0.55 * (i / nbar), 0.05 + 0.2 * spec_i)
            y0 = -2.6
            for bx in (-0.04, 0.04):
                bars.extend([x + bx, y0, z - 1, *col, x + bx, y0 + h, z - 1, *col])
            bars.extend([x - 0.04, y0 + h, z - 1, *col, x + 0.04, y0 + h, z - 1, *col])
            for row in range(1, 6):
                hh = h * (1.0 - row * 0.12) * (0.7 + float(audio.spectrum[(i + row) % 64]) * 0.5)
                zz = z - 1 - row * 0.55
                col2 = (col[0], col[1] * 0.85, col[2])
                bars.extend([x, y0, zz, *col2, x, y0 + hh, zz, *col2])
        arr = np.asarray(bars, dtype=np.float32)
        self.eq_vbo.write(arr.tobytes())
        pipe.line_prog["mvp"].write(mul(self.proj, view).T.astype(np.float32).tobytes())
        pipe.line_prog["time"].value = float(t)
        pipe.line_prog["pulse"].value = float(audio.amp)
        self.eq_vao.render(moderngl.LINES, vertices=len(arr) // 6)
        pipe.bloom_strength = 0.95

    def _render_chai(self, t, audio: AudioAnalysis):
        pipe = self.pipe
        pipe.begin_scene((0.02, 0.01, 0.04, 1))
        pipe.draw_background(
            top=(0.05, 0.02, 0.08),
            mid=(0.12, 0.04, 0.02),
            bot=(0.02, 0.01, 0.03),
            star_amount=0.15,
            time=t,
        )
        local = t - 158.0

        if 183.0 <= t < 185.5:
            self.shake_amp = max(self.shake_amp, 0.025)
            if audio.beat or t < 183.4:
                self.shake_amp = 0.04
        self.shake_amp *= 0.86
        pipe.shake = [
            math.sin(t * 55) * self.shake_amp,
            math.cos(t * 62) * self.shake_amp * 0.8,
        ]

        w2 = WIDTH // 2
        self.ctx.scissor = (0, 0, w2, HEIGHT)
        view = look_at((0.0, 1.2, 3.2), (0.0, 0.7, 0.0))
        pipe.draw_lines(self.arcade_grid, self._mvp(view), pulse=0.3)
        wobble = math.sin(local * 3.2) * 0.15 + audio.mid * 0.1
        tilt = math.sin(local * 2.1) * 0.2
        model = mul(translate(0, 0.1, 0), rotate_z(wobble), rotate_x(tilt * 0.3), scale(1.1))
        pipe.draw_lines(self.tea, self._mvp(view, model), time=t, pulse=audio.amp)

        self.ctx.scissor = (w2, 0, WIDTH - w2, HEIGHT)
        eye2 = (
            math.cos(local * 0.7) * 3.2,
            1.2 + math.sin(local * 0.5) * 0.4,
            math.sin(local * 0.7) * 3.2,
        )
        view2 = look_at(eye2, (0, 0.2, 0))
        lm = mul(rotate_y(local * 0.9), rotate_x(local * 0.3), scale(1.2))
        pipe.draw_lines(self.lattice, self._mvp(view2, lm), pulse=audio.treble)

        self.ctx.scissor = None
        pipe.bloom_strength = 0.95
        pipe.exposure = 1.45

        for a, b, en, np_text in self.banners:
            if a <= t < b:
                self.active_banner = (en, np_text)
                break

    def _render_pagoda(self, t, audio: AudioAnalysis):
        pipe = self.pipe
        pipe.begin_scene((0.01, 0.01, 0.05, 1))
        pipe.draw_background(
            top=(0.01, 0.01, 0.06),
            mid=(0.05, 0.03, 0.14),
            bot=(0.02, 0.01, 0.06),
            star_amount=1.2,
            time=t,
        )
        local = t - 186.0
        ascend = min(1.0, local / 4.0)
        y_off = -3.5 * (1.0 - ascend) + audio.bass * 0.15
        eye = (
            math.sin(local * 0.25) * 8.5,
            4.2 + ascend * 1.2,
            math.cos(local * 0.25) * 9.5,
        )
        view = look_at(eye, (0.0, 2.8 + y_off * 0.3, 0.0))

        pipe.draw_lines(self.festival_floor, self._mvp(view), pulse=audio.bass * 0.5)
        pipe.draw_lines(self.silhouettes, self._mvp(view), pulse=0.2)
        model = mul(translate(0, y_off, 0), rotate_y(local * 0.15), scale(1.0 + audio.amp * 0.03))
        pipe.draw_lines(self.pagoda, self._mvp(view, model), time=t, pulse=0.6 + audio.bass * 0.5)
        pipe.draw_lines(self.fairy_lines, self._mvp(view), pulse=0.8)

        bulbs = np.zeros((len(self.fairy_bulbs), 7), dtype=np.float32)
        for i, (x, y, z) in enumerate(self.fairy_bulbs):
            tw = 0.6 + 0.4 * math.sin(t * 5 + i)
            pulse = tw * (0.7 + audio.treble * 0.5)
            bulbs[i] = (x, y, z, 1.0 * pulse, 0.85 * pulse, 0.35 * pulse, 6.0 + (4 if audio.beat else 0))
        self.p_vbo.write(bulbs.tobytes())
        pipe.draw_particles(self.p_vao, len(self.fairy_bulbs), self._mvp(view))

        self.streamers.update(1 / 60, boost=audio.amp)
        self.gold_dust.update(1 / 60, boost=audio.bass)
        if audio.beat:
            for _ in range(25):
                self.streamers.respawn(random.randrange(self.streamers.n))
                self.gold_dust.respawn(random.randrange(self.gold_dust.n))
        n = self._upload_particles(self.streamers)
        pipe.draw_particles(self.p_vao, n, self._mvp(view))
        n = self._upload_particles(self.gold_dust)
        pipe.draw_particles(self.p_vao, n, self._mvp(view, translate(0, y_off, 0)))
        pipe.bloom_strength = 1.05 + audio.amp * 0.35

    def _render_twilight(self, t, audio: AudioAnalysis):
        pipe = self.pipe
        local = t - 235.0
        fade = min(1.0, max(0.0, local / 40.0))
        top = (0.08 * (1 - fade) + 0.02, 0.03, 0.12 * (1 - fade) + 0.02)
        mid = (0.45 * (1 - fade * 0.5), 0.12 * (1 - fade), 0.18 * (1 - fade * 0.3))
        bot = (0.55 * (1 - fade * 0.7), 0.25 * (1 - fade * 0.5), 0.08)
        pipe.begin_scene((0.02, 0.01, 0.03, 1))
        pipe.draw_background(top=top, mid=mid, bot=bot, star_amount=0.4 * (1 - fade), time=t)

        z = -8 - local * 0.35
        view = look_at((math.sin(local * 0.05) * 1.5, 2.8, z + 12), (0.0, 1.2, z - 5))
        alpha_pulse = max(0.0, 1.0 - fade)
        pipe.draw_lines(self.ridge, self._mvp(view), pulse=0.35 * alpha_pulse)
        pipe.draw_lines(self.stupas, self._mvp(view), pulse=0.5 * alpha_pulse)
        fm = translate(0, math.sin(t * 1.5) * 0.05, 0)
        pipe.draw_lines(self.flags, self._mvp(view, fm), pulse=0.4 * alpha_pulse)

        remain = SONG_DURATION - t
        if remain < 12:
            self.beacon_life = max(0.0, remain / 12)
            blink = 0.5 + 0.5 * math.sin(t * 8)
            if remain < 2:
                blink = 1.0 if int(t * 6) % 2 == 0 else 0.0
            strength = self.beacon_life * blink
            bulb = np.array(
                [0, 2.5, z - 4, strength, strength * 0.8, strength * 0.2, 18.0 * strength],
                dtype=np.float32,
            )
            self.p_vbo.write(bulb.tobytes())
            pipe.draw_particles(self.p_vao, 1, self._mvp(view))
            if remain < 0.15:
                pipe.begin_scene((0, 0, 0, 1))

        pipe.bloom_strength = 0.55 * alpha_pulse + 0.2
        pipe.vignette = 0.55 + fade * 0.35
        pipe.exposure = 1.1 - fade * 0.35
