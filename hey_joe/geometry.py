"""High-quality vector primitives used across scenes."""

from __future__ import annotations

import math
import random
from typing import Iterable, Sequence, Tuple

import cairo

Color = Tuple[float, float, float]
RGBA = Tuple[float, float, float, float]


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(c1: Sequence[float], c2: Sequence[float], t: float) -> Tuple[float, ...]:
    t = clamp(t)
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = clamp((x - edge0) / (edge1 - edge0 + 1e-9))
    return t * t * (3.0 - 2.0 * t)


def ease_in_out(t: float) -> float:
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def set_rgb(ctx: cairo.Context, c: Sequence[float], a: float = 1.0):
    if a >= 1.0 - 1e-6:
        ctx.set_source_rgb(c[0], c[1], c[2])
    else:
        ctx.set_source_rgba(c[0], c[1], c[2], a)


def radial_fill(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    r0: float,
    r1: float,
    stops: Iterable[Tuple[float, Sequence[float], float]],
):
    """stops: (offset, rgb, alpha)"""
    g = cairo.RadialGradient(cx, cy, r0, cx, cy, r1)
    for off, rgb, a in stops:
        g.add_color_stop_rgba(off, rgb[0], rgb[1], rgb[2], a)
    ctx.set_source(g)
    ctx.paint()


def linear_fill(
    ctx: cairo.Context,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    stops: Iterable[Tuple[float, Sequence[float], float]],
):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for off, rgb, a in stops:
        g.add_color_stop_rgba(off, rgb[0], rgb[1], rgb[2], a)
    ctx.set_source(g)
    ctx.paint()


def glow_disc(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    radius: float,
    color: Sequence[float],
    layers: int = 6,
    peak_alpha: float = 0.55,
):
    """Soft luminous disc via nested translucent circles."""
    for i in range(layers, 0, -1):
        t = i / layers
        a = peak_alpha * (1.0 - t) ** 1.4
        r = radius * (0.35 + 0.85 * t)
        set_rgb(ctx, color, a)
        ctx.arc(cx, cy, r, 0, math.tau)
        ctx.fill()


def stroke_ring(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    radius: float,
    color: Sequence[float],
    alpha: float,
    width: float,
    dash: Sequence[float] | None = None,
):
    ctx.save()
    set_rgb(ctx, color, alpha)
    ctx.set_line_width(width)
    if dash:
        ctx.set_dash(list(dash))
    ctx.arc(cx, cy, radius, 0, math.tau)
    ctx.stroke()
    ctx.restore()


def petal_path(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    inner: float,
    outer: float,
    angle: float,
    half_width: float,
):
    """Symmetric lotus petal as cubic Bézier pair."""
    ca, sa = math.cos(angle), math.sin(angle)
    # tip
    tip_x = cx + ca * outer
    tip_y = cy + sa * outer
    # base left/right
    perp = angle + math.pi / 2
    bx = cx + math.cos(angle) * inner
    by = cy + math.sin(angle) * inner
    lx = bx + math.cos(perp) * half_width
    ly = by + math.sin(perp) * half_width
    rx = bx - math.cos(perp) * half_width
    ry = by - math.sin(perp) * half_width
    # control points mid-petal
    mid = (inner + outer) * 0.55
    c1x = cx + math.cos(angle) * mid + math.cos(perp) * half_width * 1.35
    c1y = cy + math.sin(angle) * mid + math.sin(perp) * half_width * 1.35
    c2x = cx + math.cos(angle) * mid - math.cos(perp) * half_width * 1.35
    c2y = cy + math.sin(angle) * mid - math.sin(perp) * half_width * 1.35

    ctx.move_to(lx, ly)
    ctx.curve_to(c1x, c1y, tip_x + math.cos(perp) * half_width * 0.15, tip_y + math.sin(perp) * half_width * 0.15, tip_x, tip_y)
    ctx.curve_to(tip_x - math.cos(perp) * half_width * 0.15, tip_y - math.sin(perp) * half_width * 0.15, c2x, c2y, rx, ry)
    ctx.close_path()


def draw_lotus(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    radius: float,
    petals: int,
    rot: float,
    stroke_a: Sequence[float],
    stroke_b: Sequence[float],
    layers: int = 3,
):
    for layer in range(layers):
        scale = 1.0 - layer * 0.18
        r = radius * scale
        offset = rot + layer * (math.pi / petals)
        for i in range(petals):
            ang = offset + i * (math.tau / petals)
            petal_path(ctx, cx, cy, r * 0.18, r, ang, r * 0.22)
            # fill soft gold wash
            set_rgb(ctx, stroke_a, 0.08 + 0.04 * (layers - layer))
            ctx.fill_preserve()
            set_rgb(ctx, stroke_a if layer % 2 == 0 else stroke_b, 0.75 - layer * 0.12)
            ctx.set_line_width(1.2 - layer * 0.2)
            ctx.stroke()


def sine_spline(
    ctx: cairo.Context,
    y: float,
    amp: float,
    freq: float,
    phase: float,
    width: float,
    x0: float,
    x1: float,
    steps: int = 180,
):
    ctx.move_to(x0, y + math.sin(phase) * amp)
    for i in range(1, steps + 1):
        t = i / steps
        x = lerp(x0, x1, t)
        yy = y + math.sin(phase + t * freq * math.tau) * amp
        ctx.line_to(x, yy)
    ctx.set_line_width(width)
    ctx.stroke()


def dashed_spokes(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    count: int,
    rot: float,
    color: Sequence[float],
    alpha: float,
    width: float = 1.0,
):
    set_rgb(ctx, color, alpha)
    ctx.set_line_width(width)
    for i in range(count):
        a = rot + i * (math.tau / count)
        ctx.move_to(cx + math.cos(a) * r_inner, cy + math.sin(a) * r_inner)
        ctx.line_to(cx + math.cos(a) * r_outer, cy + math.sin(a) * r_outer)
    ctx.stroke()


def bezier_ribbon(
    ctx: cairo.Context,
    points: Sequence[Tuple[float, float]],
    color: Sequence[float],
    alpha: float,
    width: float,
):
    """Smooth ribbon through control waypoints (cubic chain)."""
    if len(points) < 2:
        return
    ctx.save()
    set_rgb(ctx, color, alpha)
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.move_to(points[0][0], points[0][1])
    if len(points) == 2:
        ctx.line_to(points[1][0], points[1][1])
    else:
        for i in range(1, len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            ctx.curve_to(x0, y0, x0, y0, mx, my)
        ctx.line_to(points[-1][0], points[-1][1])
    ctx.stroke()
    ctx.restore()


def log_spiral_points(
    cx: float,
    cy: float,
    a: float,
    b: float,
    turns: float,
    n: int,
    rot: float = 0.0,
) -> list[Tuple[float, float]]:
    pts = []
    for i in range(n):
        t = (i / max(n - 1, 1)) * turns * math.tau
        r = a * math.exp(b * t)
        pts.append((cx + math.cos(t + rot) * r, cy + math.sin(t + rot) * r))
    return pts


def paisley_path(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    size: float,
    angle: float,
    curl: float = 1.15,
):
    """Classic kalka / paisley teardrop with inner spiral hook."""
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(angle)
    # outer body
    ctx.move_to(0, -size)
    ctx.curve_to(size * 0.85, -size * 0.55, size * 0.95, size * 0.35, 0, size * 0.95)
    ctx.curve_to(-size * 0.55, size * 0.45, -size * 0.35, -size * 0.2, -size * 0.15, -size * 0.55)
    ctx.curve_to(-size * 0.05, -size * 0.85, size * 0.1, -size * 0.95, 0, -size)
    ctx.close_path()
    # leave path for caller fill/stroke; add inner hook as separate stroke after
    ctx.restore()


def draw_paisley(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    size: float,
    angle: float,
    fill: Sequence[float],
    stroke: Sequence[float],
    fill_a: float = 0.35,
    stroke_a: float = 0.85,
):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(angle)
    ctx.move_to(0, -size)
    ctx.curve_to(size * 0.9, -size * 0.5, size * 1.0, size * 0.4, 0.05 * size, size)
    ctx.curve_to(-0.55 * size, size * 0.5, -0.4 * size, -0.15 * size, -0.18 * size, -0.55 * size)
    ctx.curve_to(-0.08 * size, -0.82 * size, 0.12 * size, -0.95 * size, 0, -size)
    ctx.close_path()
    set_rgb(ctx, fill, fill_a)
    ctx.fill_preserve()
    set_rgb(ctx, stroke, stroke_a)
    ctx.set_line_width(max(1.0, size * 0.035))
    ctx.stroke()

    # inner logarithmic spiral
    pts = log_spiral_points(0.05 * size, 0.05 * size, size * 0.08, 0.18, 2.2, 48, -0.4)
    if pts:
        ctx.move_to(pts[0][0], pts[0][1])
        for p in pts[1:]:
            ctx.line_to(p[0], p[1])
        set_rgb(ctx, stroke, stroke_a * 0.7)
        ctx.set_line_width(max(0.7, size * 0.02))
        ctx.stroke()
    ctx.restore()


def sri_yantra(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    scale: float,
    rot: float,
    color_a: Sequence[float],
    color_b: Sequence[float],
    vib: float = 0.0,
):
    """Interlocking triangles approximating a Sri Yantra (9 interlocking)."""
    # Simplified but visually dense: 4 upward + 5 downward triangles of varying scales
    ups = [1.00, 0.78, 0.58, 0.38]
    downs = [0.92, 0.70, 0.52, 0.34, 0.22]
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    jitter = 1.0 + vib * 0.04

    def tri(s: float, up: bool, col: Sequence[float], a: float, w: float):
        h = s * scale * jitter
        sign = -1 if up else 1
        ctx.move_to(0, sign * h)
        ctx.line_to(-h * 0.866, -sign * h * 0.5)
        ctx.line_to(h * 0.866, -sign * h * 0.5)
        ctx.close_path()
        set_rgb(ctx, col, a * 0.12)
        ctx.fill_preserve()
        set_rgb(ctx, col, a)
        ctx.set_line_width(w)
        ctx.stroke()

    for i, s in enumerate(ups):
        tri(s, True, color_a, 0.85 - i * 0.08, 1.6 - i * 0.15)
    for i, s in enumerate(downs):
        tri(s, False, color_b, 0.8 - i * 0.07, 1.5 - i * 0.12)

    # bindu
    set_rgb(ctx, color_a, 0.95)
    ctx.arc(0, 0, scale * 0.04, 0, math.tau)
    ctx.fill()
    ctx.restore()


def sudarshana_chakra(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    radius: float,
    blades: int,
    rot: float,
    collapse: float,
    color: Sequence[float],
    accent: Sequence[float],
):
    """Serrated disc with triangular blades + ornate perimeter hooks."""
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    r_blade = radius * (0.55 + 0.45 * collapse)
    # disc body
    set_rgb(ctx, color, 0.25)
    ctx.arc(0, 0, radius * 0.42, 0, math.tau)
    ctx.fill()
    stroke_ring(ctx, 0, 0, radius * 0.42, accent, 0.9, 2.0)

    for i in range(blades):
        a0 = i * (math.tau / blades)
        a1 = (i + 0.5) * (math.tau / blades)
        a2 = (i + 1.0) * (math.tau / blades)
        # triangular blade
        ctx.move_to(math.cos(a0) * radius * 0.38, math.sin(a0) * radius * 0.38)
        ctx.line_to(math.cos(a1) * r_blade, math.sin(a1) * r_blade)
        ctx.line_to(math.cos(a2) * radius * 0.38, math.sin(a2) * radius * 0.38)
        ctx.close_path()
        set_rgb(ctx, accent if i % 2 == 0 else color, 0.55)
        ctx.fill_preserve()
        set_rgb(ctx, accent, 0.95)
        ctx.set_line_width(1.1)
        ctx.stroke()

        # ornate hook at tip
        hx = math.cos(a1) * r_blade
        hy = math.sin(a1) * r_blade
        tang = a1 + math.pi / 2
        ctx.move_to(hx, hy)
        ctx.curve_to(
            hx + math.cos(tang) * 12,
            hy + math.sin(tang) * 12,
            hx + math.cos(a1) * 18 + math.cos(tang) * 8,
            hy + math.sin(a1) * 18 + math.sin(tang) * 8,
            hx + math.cos(a1) * 10,
            hy + math.sin(a1) * 10,
        )
        set_rgb(ctx, accent, 0.8)
        ctx.set_line_width(1.4)
        ctx.stroke()

    # inner rings
    for rr in (0.18, 0.28, 0.35):
        stroke_ring(ctx, 0, 0, radius * rr, accent, 0.7, 1.0)
    ctx.restore()


def lissajous_points(
    cx: float,
    cy: float,
    ax: float,
    ay: float,
    a: float,
    b: float,
    delta: float,
    n: int = 400,
) -> list[Tuple[float, float]]:
    pts = []
    for i in range(n):
        t = (i / n) * math.tau
        x = cx + ax * math.sin(a * t + delta)
        y = cy + ay * math.sin(b * t)
        pts.append((x, y))
    return pts


def feather_spline(
    ctx: cairo.Context,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    bulge: float,
    side: float,
):
    """Single feather outline from root to tip with barb bulge."""
    mx = (x0 + x1) / 2 + side * bulge
    my = (y0 + y1) / 2
    ctx.move_to(x0, y0)
    ctx.curve_to(mx, my - bulge * 0.3, mx, my + bulge * 0.3, x1, y1)


def peacock_eye(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    size: float,
    rot: float,
):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    # outer teal oval
    ctx.scale(1.0, 1.35)
    rings = [
        ((0.08, 0.55, 0.45), size * 1.0, 0.55),
        ((0.12, 0.35, 0.65), size * 0.72, 0.7),
        ((0.85, 0.65, 0.12), size * 0.42, 0.85),
        ((0.05, 0.08, 0.18), size * 0.2, 0.95),
    ]
    for col, r, a in rings:
        set_rgb(ctx, col, a)
        ctx.arc(0, 0, r, 0, math.tau)
        ctx.fill()
    ctx.restore()


def mughal_arch(
    ctx: cairo.Context,
    x: float,
    base_y: float,
    w: float,
    h: float,
    color: Sequence[float],
    alpha: float = 1.0,
):
    """Silhouette of a pointed Mughal / Indo-Islamic arch."""
    set_rgb(ctx, color, alpha)
    ctx.move_to(x, base_y)
    ctx.line_to(x, base_y - h * 0.55)
    # pointed horseshoe
    ctx.curve_to(x, base_y - h * 0.85, x + w * 0.5, base_y - h * 1.05, x + w * 0.5, base_y - h)
    ctx.curve_to(x + w * 0.5, base_y - h * 1.05, x + w, base_y - h * 0.85, x + w, base_y - h * 0.55)
    ctx.line_to(x + w, base_y)
    ctx.close_path()
    ctx.fill()


def minaret(
    ctx: cairo.Context,
    x: float,
    base_y: float,
    h: float,
    color: Sequence[float],
    alpha: float = 1.0,
):
    set_rgb(ctx, color, alpha)
    tw = h * 0.08
    ctx.rectangle(x - tw / 2, base_y - h * 0.75, tw, h * 0.75)
    ctx.fill()
    # balcony ring
    ctx.rectangle(x - tw * 1.1, base_y - h * 0.78, tw * 2.2, h * 0.04)
    ctx.fill()
    # dome
    ctx.arc(x, base_y - h * 0.78, tw * 1.1, math.pi, math.tau)
    ctx.fill()
    # finial
    ctx.set_line_width(1.5)
    ctx.move_to(x, base_y - h * 0.78 - tw * 1.1)
    ctx.line_to(x, base_y - h)
    ctx.stroke()


def jali_pattern(
    ctx: cairo.Context,
    x0: float,
    y0: float,
    w: float,
    h: float,
    cell: float,
    offset: float,
    color: Sequence[float],
    alpha: float,
):
    """Mughal geometric lattice (octagon + square tiling)."""
    set_rgb(ctx, color, alpha)
    ctx.set_line_width(1.2)
    cols = int(w / cell) + 3
    rows = int(h / cell) + 3
    for j in range(rows):
        for i in range(cols):
            cx = x0 + i * cell + (offset % cell) + (cell * 0.5 if j % 2 else 0)
            cy = y0 + j * cell
            r = cell * 0.28
            # octagon-ish diamond
            ctx.move_to(cx, cy - r)
            ctx.line_to(cx + r * 0.7, cy - r * 0.7)
            ctx.line_to(cx + r, cy)
            ctx.line_to(cx + r * 0.7, cy + r * 0.7)
            ctx.line_to(cx, cy + r)
            ctx.line_to(cx - r * 0.7, cy + r * 0.7)
            ctx.line_to(cx - r, cy)
            ctx.line_to(cx - r * 0.7, cy - r * 0.7)
            ctx.close_path()
            ctx.stroke()
            # center star cross
            ctx.move_to(cx - r * 0.35, cy)
            ctx.line_to(cx + r * 0.35, cy)
            ctx.move_to(cx, cy - r * 0.35)
            ctx.line_to(cx, cy + r * 0.35)
            ctx.stroke()


class SeededParticles:
    """Deterministic particle field for reproducible frames."""

    def __init__(self, n: int, seed: int = 42):
        rng = random.Random(seed)
        self.parts = [
            {
                "x": rng.random(),
                "y": rng.random(),
                "vx": (rng.random() - 0.5) * 0.02,
                "vy": (rng.random() - 0.5) * 0.02,
                "s": rng.uniform(0.6, 2.4),
                "p": rng.random() * math.tau,
            }
            for _ in range(n)
        ]

    def positions(self, t: float, w: float, h: float, drift: float = 1.0):
        out = []
        for p in self.parts:
            x = (p["x"] + p["vx"] * t * drift + 0.02 * math.sin(t * 0.3 + p["p"])) % 1.0
            y = (p["y"] + p["vy"] * t * drift + 0.02 * math.cos(t * 0.25 + p["p"])) % 1.0
            out.append((x * w, y * h, p["s"], p["p"]))
        return out
