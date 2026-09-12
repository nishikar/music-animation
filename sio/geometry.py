"""Geometry builders for wireframe / solid meshes."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def _append_line(buf: list, a, b, color):
    buf.extend([*a, *color, *b, *color])


def grid_valley(width=40, depth=80, scale=1.0, height_fn=None) -> np.ndarray:
    """Return interleaved pos+color line vertices for a wireframe valley."""
    verts: list[float] = []
    half_w = width // 2
    for z in range(depth):
        for x in range(-half_w, half_w):
            def h(xx, zz):
                if height_fn:
                    return height_fn(xx, zz)
                # valley floor near 0, peaks at edges
                edge = abs(xx) / half_w
                mountain = max(0.0, edge - 0.35) ** 2 * 14.0
                mountain *= 1.0 + 0.35 * math.sin(xx * 0.7 + zz * 0.15)
                mountain *= 1.0 + 0.25 * math.cos(zz * 0.4 + xx * 0.2)
                return mountain

            p00 = (x * scale, h(x, z), -z * scale)
            p10 = ((x + 1) * scale, h(x + 1, z), -z * scale)
            p01 = (x * scale, h(x, z + 1), -(z + 1) * scale)

            # color: cyan floor -> magenta peaks
            def col(p):
                t = min(1.0, p[1] / 10.0)
                return (
                    0.15 + 0.7 * t,
                    0.85 - 0.55 * t,
                    0.95 - 0.35 * t,
                )

            _append_line(verts, p00, p10, col(p00))
            _append_line(verts, p00, p01, col(p00))
    return np.asarray(verts, dtype=np.float32)


def polyline(points: Iterable, color=(1, 1, 1)) -> np.ndarray:
    pts = list(points)
    verts: list[float] = []
    for a, b in zip(pts, pts[1:]):
        _append_line(verts, a, b, color)
    return np.asarray(verts, dtype=np.float32)


def circle_ring(radius, y=0.0, segments=64, color=(1, 0.3, 0.1), z=0.0) -> np.ndarray:
    verts: list[float] = []
    for i in range(segments):
        a0 = (i / segments) * math.tau
        a1 = ((i + 1) / segments) * math.tau
        p0 = (math.cos(a0) * radius, y, math.sin(a0) * radius + z)
        p1 = (math.cos(a1) * radius, y, math.sin(a1) * radius + z)
        _append_line(verts, p0, p1, color)
    return np.asarray(verts, dtype=np.float32)


def regular_polygon(sides, radius, y=0.0, color=(1, 0.8, 0.2), star=False) -> np.ndarray:
    verts: list[float] = []
    if star and sides >= 5:
        # star via every step-2 vertex
        idx = []
        for i in range(sides):
            idx.append(i)
            idx.append((i * 2) % sides)
        # simpler: connect i -> i+2
        for i in range(sides):
            a0 = (i / sides) * math.tau - math.pi / 2
            a1 = ((i + 2) / sides) * math.tau - math.pi / 2
            r0 = radius
            r1 = radius
            p0 = (math.cos(a0) * r0, y, math.sin(a0) * r0)
            p1 = (math.cos(a1) * r1, y, math.sin(a1) * r1)
            _append_line(verts, p0, p1, color)
        return np.asarray(verts, dtype=np.float32)

    for i in range(sides):
        a0 = (i / sides) * math.tau - math.pi / 2
        a1 = ((i + 1) / sides) * math.tau - math.pi / 2
        p0 = (math.cos(a0) * radius, y, math.sin(a0) * radius)
        p1 = (math.cos(a1) * radius, y, math.sin(a1) * radius)
        _append_line(verts, p0, p1, color)
    return np.asarray(verts, dtype=np.float32)


def box_wire(cx, cy, cz, sx, sy, sz, color=(1, 1, 1)) -> np.ndarray:
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    corners = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    verts: list[float] = []
    for a, b in edges:
        _append_line(verts, corners[a], corners[b], color)
    return np.asarray(verts, dtype=np.float32)


def cylinder_wire(radius, height, segments=24, color=(1, 0.8, 0.2), rings=4) -> np.ndarray:
    verts: list[float] = []
    for ri in range(rings):
        y = -height / 2 + height * ri / (rings - 1)
        for i in range(segments):
            a0 = (i / segments) * math.tau
            a1 = ((i + 1) / segments) * math.tau
            p0 = (math.cos(a0) * radius, y, math.sin(a0) * radius)
            p1 = (math.cos(a1) * radius, y, math.sin(a1) * radius)
            _append_line(verts, p0, p1, color)
    # verticals
    for i in range(0, segments, 2):
        a = (i / segments) * math.tau
        x, z = math.cos(a) * radius, math.sin(a) * radius
        _append_line(verts, (x, -height / 2, z), (x, height / 2, z), color)
    # mantra-ish chevrons
    for i in range(0, segments, 3):
        a = (i / segments) * math.tau
        x, z = math.cos(a) * radius * 1.02, math.sin(a) * radius * 1.02
        for k in range(3):
            y0 = -height / 2 + 0.15 + k * height / 4
            _append_line(verts, (x, y0, z), (x * 0.85, y0 + 0.12, z * 0.85), (1.0, 0.65, 0.15))
    return np.asarray(verts, dtype=np.float32)


def hex_ring(radius, segments=6, color=(0.1, 1.0, 0.6), y=0.0) -> np.ndarray:
    return regular_polygon(segments, radius, y=y, color=color)


def solid_lathe_bell(segments=48) -> tuple[np.ndarray, np.ndarray]:
    """Approximate temple bell as triangle mesh. Returns (pos_normal_color, indices)."""
    profile = [
        (0.05, 1.15),
        (0.12, 1.05),
        (0.18, 0.95),
        (0.35, 0.75),
        (0.55, 0.45),
        (0.62, 0.20),
        (0.58, 0.05),
        (0.50, -0.05),
        (0.55, -0.15),
        (0.48, -0.22),
        (0.20, -0.25),
        (0.0, -0.25),
    ]
    positions = []
    normals = []
    colors = []
    for yi, (r, y) in enumerate(profile):
        for i in range(segments):
            a = (i / segments) * math.tau
            x = math.cos(a) * r
            z = math.sin(a) * r
            # crude normal
            nx, ny, nz = math.cos(a), 0.35, math.sin(a)
            nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
            positions.append((x, y, z))
            normals.append((nx / nlen, ny / nlen, nz / nlen))
            # brass
            colors.append((0.85, 0.65, 0.18))

    indices = []
    for yi in range(len(profile) - 1):
        for i in range(segments):
            i0 = yi * segments + i
            i1 = yi * segments + (i + 1) % segments
            i2 = (yi + 1) * segments + i
            i3 = (yi + 1) * segments + (i + 1) % segments
            indices.extend([i0, i2, i1, i1, i2, i3])

    # pack interleaved pos, normal, color
    interleaved = []
    for p, n, c in zip(positions, normals, colors):
        interleaved.extend([*p, *n, *c])
    return np.asarray(interleaved, dtype=np.float32), np.asarray(indices, dtype=np.uint32)


def solid_cylinder(radius, height, segments=32, color=(0.9, 0.75, 0.2)) -> tuple[np.ndarray, np.ndarray]:
    positions = []
    normals = []
    colors = []
    # side
    for i in range(segments):
        a0 = (i / segments) * math.tau
        a1 = ((i + 1) / segments) * math.tau
        for a in (a0, a1):
            x, z = math.cos(a) * radius, math.sin(a) * radius
            for y in (-height / 2, height / 2):
                positions.append((x, y, z))
                normals.append((math.cos(a), 0.0, math.sin(a)))
                colors.append(color)

    # We build a simpler indexed mesh
    verts = []
    idxs = []
    # bottom center + top center
    base = 0
    # rings
    for y in (-height / 2, height / 2):
        for i in range(segments):
            a = (i / segments) * math.tau
            x, z = math.cos(a) * radius, math.sin(a) * radius
            nx, nz = math.cos(a), math.sin(a)
            verts.extend([x, y, z, nx, 0.0, nz, *color])
    # side faces
    for i in range(segments):
        i0 = i
        i1 = (i + 1) % segments
        i2 = segments + i
        i3 = segments + (i + 1) % segments
        idxs.extend([i0, i1, i3, i0, i3, i2])
    # caps
    bot_c = len(verts) // 9
    verts.extend([0, -height / 2, 0, 0, -1, 0, *color])
    top_c = len(verts) // 9
    verts.extend([0, height / 2, 0, 0, 1, 0, *color])
    for i in range(segments):
        i0 = i
        i1 = (i + 1) % segments
        idxs.extend([bot_c, i1, i0])
        idxs.extend([top_c, segments + i0, segments + i1])
    return np.asarray(verts, dtype=np.float32), np.asarray(idxs, dtype=np.uint32)


def mandala_tiers() -> list[dict]:
    """Describe concentric polygonal tiers for the sacred geometry stupa."""
    tiers = []
    specs = [
        (4, 3.2, 0.18, False, (0.9, 0.15, 0.15)),
        (8, 2.8, 0.16, False, (0.95, 0.8, 0.2)),
        (6, 2.4, 0.16, False, (0.85, 0.1, 0.18)),
        (5, 2.0, 0.15, True, (0.98, 0.75, 0.15)),
        (8, 1.6, 0.14, False, (0.9, 0.12, 0.16)),
        (3, 1.25, 0.14, False, (0.95, 0.78, 0.2)),
        (8, 0.95, 0.12, False, (0.88, 0.1, 0.15)),
        (5, 0.7, 0.12, True, (1.0, 0.82, 0.25)),
        (6, 0.45, 0.1, False, (0.9, 0.15, 0.15)),
    ]
    y = 0.0
    for sides, radius, thick, star, color in specs:
        tiers.append({
            "sides": sides,
            "radius": radius,
            "y": y,
            "thick": thick,
            "star": star,
            "color": color,
        })
        y += thick + 0.05
    return tiers


def pagoda_wireframe() -> np.ndarray:
    """Multi-tier Nepali pagoda as golden wireframe ribbons."""
    chunks = []
    # base platform
    chunks.append(box_wire(0, 0.1, 0, 4.5, 0.2, 4.5, (1.0, 0.82, 0.2)))
    chunks.append(box_wire(0, 0.35, 0, 3.8, 0.3, 3.8, (1.0, 0.78, 0.18)))
    y = 0.6
    for tier, width in enumerate([3.2, 2.6, 2.0, 1.45, 0.95]):
        # roof slab
        chunks.append(box_wire(0, y, 0, width, 0.12, width, (1.0, 0.85, 0.25)))
        # overhang eaves (larger)
        eaves = width + 0.55
        # pyramidal roof outline
        top_y = y + 0.55
        corners = [
            (-eaves / 2, y, -eaves / 2),
            (eaves / 2, y, -eaves / 2),
            (eaves / 2, y, eaves / 2),
            (-eaves / 2, y, eaves / 2),
        ]
        apexes = [
            (0, top_y, -width * 0.15),
            (0, top_y, width * 0.15),
        ]
        roof = []
        for i in range(4):
            a = corners[i]
            b = corners[(i + 1) % 4]
            c = (0, top_y, 0)
            roof_lines = polyline([a, b, c, a], (1.0, 0.8, 0.15))
            chunks.append(roof_lines)
            # roof slats
            for k in range(1, 5):
                t = k / 5
                p0 = (
                    a[0] + (c[0] - a[0]) * t,
                    a[1] + (c[1] - a[1]) * t,
                    a[2] + (c[2] - a[2]) * t,
                )
                p1 = (
                    b[0] + (c[0] - b[0]) * t,
                    b[1] + (c[1] - b[1]) * t,
                    b[2] + (c[2] - b[2]) * t,
                )
                chunks.append(polyline([p0, p1], (1.0, 0.75, 0.12)))
        # railing
        chunks.append(box_wire(0, y - 0.25, 0, width * 0.85, 0.35, width * 0.85, (0.95, 0.7, 0.15)))
        y = top_y + 0.15
    # finial
    chunks.append(box_wire(0, y + 0.2, 0, 0.15, 0.5, 0.15, (1.0, 0.9, 0.3)))
    chunks.append(circle_ring(0.25, y=y + 0.5, segments=16, color=(1.0, 0.85, 0.2)))
    return np.concatenate(chunks)


def lowpoly_stupa(x=0.0, z=0.0, scale=1.0) -> np.ndarray:
    chunks = []
    c_white = (0.92, 0.92, 0.9)
    c_gold = (0.95, 0.78, 0.2)
    # dome as stacked rings
    for i, (r, y) in enumerate([(0.8, 0.0), (0.95, 0.25), (0.85, 0.5), (0.55, 0.75), (0.25, 0.95)]):
        chunks.append(circle_ring(r * scale, y=y * scale, segments=20, color=c_white, z=0))
    # harmika
    chunks.append(box_wire(0, 1.15 * scale, 0, 0.45 * scale, 0.25 * scale, 0.45 * scale, c_gold))
    # spire
    for i in range(8):
        w = (0.35 - i * 0.035) * scale
        chunks.append(box_wire(0, (1.35 + i * 0.08) * scale, 0, w, 0.05 * scale, w, c_gold))
    data = np.concatenate(chunks)
    # translate xz
    data = data.reshape(-1, 6)
    data[:, 0] += x
    data[:, 2] += z
    return data.reshape(-1)


def tea_glass_wire() -> np.ndarray:
    """Stylized wireframe tea glass / cup."""
    chunks = []
    c = (0.2, 0.75, 1.0)
    # cup body taper
    for yi, (r, y) in enumerate([
        (0.55, 0.0), (0.52, 0.25), (0.48, 0.55), (0.45, 0.85), (0.5, 1.05),
    ]):
        chunks.append(circle_ring(r, y=y, segments=28, color=c))
    # verticals
    for i in range(12):
        a = (i / 12) * math.tau
        pts = []
        for r, y in [(0.55, 0.0), (0.52, 0.25), (0.48, 0.55), (0.45, 0.85), (0.5, 1.05)]:
            pts.append((math.cos(a) * r, y, math.sin(a) * r))
        chunks.append(polyline(pts, c))
    # liquid line
    chunks.append(circle_ring(0.46, y=0.72, segments=28, color=(1.0, 0.55, 0.15)))
    # steam ribbons (base curves; animated in scene)
    steam = (1.0, 0.25, 0.1)
    for s in range(3):
        pts = []
        for k in range(16):
            yy = 1.1 + k * 0.12
            xx = math.sin(k * 0.55 + s) * (0.15 + k * 0.02) + s * 0.12 - 0.12
            zz = math.cos(k * 0.4 + s * 1.3) * 0.1
            pts.append((xx, yy, zz))
        chunks.append(polyline(pts, steam))
    # saucer
    chunks.append(circle_ring(0.75, y=-0.05, segments=32, color=c))
    chunks.append(circle_ring(0.55, y=-0.08, segments=32, color=c))
    return np.concatenate(chunks)


def lattice_structure() -> np.ndarray:
    """Geometric lattice for arcade right panel."""
    chunks = []
    colors = [(1.0, 0.2, 0.1), (1.0, 0.5, 0.1), (1.0, 0.85, 0.15)]
    rng = np.random.default_rng(3)
    for i in range(18):
        color = colors[i % 3]
        x = rng.uniform(-1.2, 1.2)
        y = rng.uniform(-1.0, 1.2)
        z = rng.uniform(-1.2, 1.2)
        kind = i % 3
        if kind == 0:
            chunks.append(box_wire(x, y, z, 0.35, 0.35, 0.35, color))
        elif kind == 1:
            chunks.append(circle_ring(0.25, y=y, segments=16, color=color, z=z))
            # shift x
            data = chunks[-1].reshape(-1, 6)
            data[:, 0] += x
            chunks[-1] = data.reshape(-1)
        else:
            chunks.append(regular_polygon(3, 0.3, y=y, color=color))
            data = chunks[-1].reshape(-1, 6)
            data[:, 0] += x
            data[:, 2] += z
            chunks[-1] = data.reshape(-1)
    # connecting lines
    for i in range(20):
        a = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
        b = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
        chunks.append(polyline([a, b], (1.0, 0.4, 0.1)))
    return np.concatenate(chunks)
