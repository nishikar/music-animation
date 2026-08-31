"""Procedural mesh builders — positions, normals, uvs, colors."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class MeshData:
    positions: np.ndarray  # float32 Nx3
    normals: np.ndarray
    uvs: np.ndarray
    colors: np.ndarray
    indices: np.ndarray  # uint32

    def interleaved(self) -> np.ndarray:
        """pos3 + n3 + uv2 + color3 = 11 floats."""
        n = len(self.positions)
        out = np.empty((n, 11), dtype=np.float32)
        out[:, 0:3] = self.positions
        out[:, 3:6] = self.normals
        out[:, 6:8] = self.uvs
        out[:, 8:11] = self.colors
        return out


def _empty() -> Tuple[List, List, List, List, List]:
    return [], [], [], [], []


def _add_tri(pos, nrm, uvs, cols, idx, a, b, c, color, normal=None):
    base = len(pos)
    for p, uv in ((a, (0, 0)), (b, (1, 0)), (c, (0.5, 1))):
        pos.append(p)
        uvs.append(uv)
        cols.append(color)
    if normal is None:
        ab = np.array(b) - np.array(a)
        ac = np.array(c) - np.array(a)
        n = np.cross(ab, ac)
        ln = np.linalg.norm(n) + 1e-9
        normal = (n / ln).tolist()
    for _ in range(3):
        nrm.append(normal)
    idx.extend([base, base + 1, base + 2])


def _add_quad(pos, nrm, uvs, cols, idx, p0, p1, p2, p3, color, uv_rect=(0, 0, 1, 1)):
    u0, v0, u1, v1 = uv_rect
    base = len(pos)
    for p, uv in ((p0, (u0, v0)), (p1, (u1, v0)), (p2, (u1, v1)), (p3, (u0, v1))):
        pos.append(p)
        uvs.append(uv)
        cols.append(color)
    ab = np.array(p1) - np.array(p0)
    ad = np.array(p3) - np.array(p0)
    n = np.cross(ab, ad)
    ln = np.linalg.norm(n) + 1e-9
    normal = (n / ln).tolist()
    for _ in range(4):
        nrm.append(normal)
    idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])


def box(sx=1.0, sy=1.0, sz=1.0, color=(0.7, 0.7, 0.7), center=(0, 0, 0)) -> MeshData:
    cx, cy, cz = center
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
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
    faces = [
        (0, 1, 2, 3),  # -Z
        (5, 4, 7, 6),  # +Z
        (4, 0, 3, 7),  # -X
        (1, 5, 6, 2),  # +X
        (4, 5, 1, 0),  # -Y
        (3, 2, 6, 7),  # +Y
    ]
    pos, nrm, uvs, cols, idx = _empty()
    for f in faces:
        _add_quad(pos, nrm, uvs, cols, idx, corners[f[0]], corners[f[1]], corners[f[2]], corners[f[3]], color)
    return MeshData(
        np.array(pos, np.float32),
        np.array(nrm, np.float32),
        np.array(uvs, np.float32),
        np.array(cols, np.float32),
        np.array(idx, np.uint32),
    )


def ground_grid(
    size: float = 80.0,
    divisions: int = 64,
    color_a=(0.35, 0.4, 0.28),
    color_b=(0.3, 0.34, 0.24),
    height_fn=None,
    color_fn=None,
) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    step = size / divisions
    half = size * 0.5
    verts = []
    for z in range(divisions + 1):
        row = []
        for x in range(divisions + 1):
            wx = -half + x * step
            wz = -half + z * step
            wy = 0.0 if height_fn is None else float(height_fn(wx, wz))
            row.append((wx, wy, wz))
        verts.append(row)

    for z in range(divisions):
        for x in range(divisions):
            p00 = verts[z][x]
            p10 = verts[z][x + 1]
            p11 = verts[z + 1][x + 1]
            p01 = verts[z + 1][x]
            if color_fn is not None:
                mx = 0.25 * (p00[0] + p10[0] + p11[0] + p01[0])
                my = 0.25 * (p00[1] + p10[1] + p11[1] + p01[1])
                mz = 0.25 * (p00[2] + p10[2] + p11[2] + p01[2])
                c = color_fn(mx, my, mz)
            else:
                # Soft blend instead of harsh checker
                t = 0.5 + 0.5 * math.sin(x * 0.35) * math.cos(z * 0.35)
                c = (
                    color_a[0] * (1 - t) + color_b[0] * t,
                    color_a[1] * (1 - t) + color_b[1] * t,
                    color_a[2] * (1 - t) + color_b[2] * t,
                )
            _add_quad(
                pos, nrm, uvs, cols, idx,
                p00, p01, p11, p10, c,
                (x / divisions, z / divisions, (x + 1) / divisions, (z + 1) / divisions),
            )
    return MeshData(
        np.array(pos, np.float32),
        np.array(nrm, np.float32),
        np.array(uvs, np.float32),
        np.array(cols, np.float32),
        np.array(idx, np.uint32),
    )


def road_ribbon(length=110.0, width=5.6, color=(0.14, 0.14, 0.16), y=0.12) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    hl, hw = length * 0.5, width * 0.5
    _add_quad(
        pos, nrm, uvs, cols, idx,
        (-hw, y, -hl), (-hw, y, hl), (hw, y, hl), (hw, y, -hl),
        color,
    )
    stripe = (0.92, 0.82, 0.25)
    dash, gap = 2.2, 1.6
    z = -hl + 1.0
    while z < hl - 1.0:
        z1 = min(z + dash, hl - 1.0)
        _add_quad(
            pos, nrm, uvs, cols, idx,
            (-0.1, y + 0.02, z), (-0.1, y + 0.02, z1), (0.1, y + 0.02, z1), (0.1, y + 0.02, z),
            stripe,
        )
        z = z1 + gap
    edge = (0.88, 0.88, 0.9)
    for s in (-hw + 0.2, hw - 0.2):
        _add_quad(
            pos, nrm, uvs, cols, idx,
            (s - 0.07, y + 0.015, -hl), (s - 0.07, y + 0.015, hl), (s + 0.07, y + 0.015, hl), (s + 0.07, y + 0.015, -hl),
            edge,
        )
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def canal(length=40.0, width=8.0, color=(0.15, 0.28, 0.38)) -> MeshData:
    return ground_grid(size=max(length, width), divisions=32, color_a=color, color_b=(color[0] * 0.9, color[1] * 0.95, color[2] * 1.05))


def gabled_house(w=3.0, d=4.0, h=4.0, brick=(0.55, 0.28, 0.22), roof=(0.35, 0.18, 0.14)) -> MeshData:
    """Amsterdam-style merchant house with windows and door."""
    body = box(w, h * 0.72, d, brick, (0, h * 0.36, 0))
    pos, nrm, uvs, cols, idx = _empty()
    y0 = h * 0.72
    peak = h * 1.05
    hw, hd = w * 0.55, d * 0.52
    _add_quad(
        pos, nrm, uvs, cols, idx,
        (-hw, y0, -hd), (-hw, y0, hd), (0.0, peak, hd * 0.15), (0.0, peak, -hd * 0.15),
        roof,
    )
    _add_quad(
        pos, nrm, uvs, cols, idx,
        (hw, y0, hd), (hw, y0, -hd), (0.0, peak, -hd * 0.15), (0.0, peak, hd * 0.15),
        roof,
    )
    _add_tri(pos, nrm, uvs, cols, idx, (-hw, y0, hd), (hw, y0, hd), (0.0, peak, hd * 0.15), roof)
    _add_tri(pos, nrm, uvs, cols, idx, (hw, y0, -hd), (-hw, y0, -hd), (0.0, peak, -hd * 0.15), roof)
    roof_mesh = MeshData(
        np.array(pos, np.float32),
        np.array(nrm, np.float32),
        np.array(uvs, np.float32),
        np.array(cols, np.float32),
        np.array(idx, np.uint32),
    )
    # Windows / door on front face (+Z)
    glass = (0.55, 0.7, 0.82)
    sill = (0.75, 0.7, 0.55)
    parts = [body, roof_mesh]
    win_h, win_w = 0.55, 0.45
    for wx, wy in ((-0.7, 1.5), (0.7, 1.5), (-0.7, 2.4), (0.7, 2.4)):
        parts.append(box(win_w, win_h, 0.08, glass, (wx, wy, d * 0.51)))
        parts.append(box(win_w + 0.08, 0.06, 0.1, sill, (wx, wy - win_h * 0.55, d * 0.52)))
    parts.append(box(0.55, 1.15, 0.1, (0.25, 0.15, 0.1), (0.0, 0.58, d * 0.52)))
    return merge_meshes(parts)


def stone_arch_bridge(span=16.0, width=5.0, color=(0.45, 0.42, 0.38)) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    # deck
    _add_quad(pos, nrm, uvs, cols, idx, (-width / 2, 2.2, -span / 2), (width / 2, 2.2, -span / 2), (width / 2, 2.2, span / 2), (-width / 2, 2.2, span / 2), color)
    # arch ring
    segs = 16
    for i in range(segs):
        a0 = math.pi * i / segs
        a1 = math.pi * (i + 1) / segs
        r_in, r_out = 4.0, 5.2
        for side in (-width / 2, width / 2 - 0.3):
            p0 = (side, 2.2 - math.sin(a0) * r_in, math.cos(a0) * r_in)
            p1 = (side + 0.3, 2.2 - math.sin(a0) * r_in, math.cos(a0) * r_in)
            p2 = (side + 0.3, 2.2 - math.sin(a1) * r_in, math.cos(a1) * r_in)
            p3 = (side, 2.2 - math.sin(a1) * r_in, math.cos(a1) * r_in)
            _add_quad(pos, nrm, uvs, cols, idx, p0, p1, p2, p3, (color[0] * 0.9, color[1] * 0.9, color[2] * 0.9))
    # railings
    rail = (0.35, 0.33, 0.3)
    for x in (-width / 2, width / 2):
        _add_quad(pos, nrm, uvs, cols, idx, (x - 0.08, 2.2, -span / 2), (x + 0.08, 2.2, -span / 2), (x + 0.08, 3.0, -span / 2), (x - 0.08, 3.0, -span / 2), rail)
        _add_quad(pos, nrm, uvs, cols, idx, (x - 0.08, 2.2, -span / 2), (x + 0.08, 2.2, -span / 2), (x + 0.08, 2.2, span / 2), (x - 0.08, 2.2, span / 2), rail)
        _add_quad(pos, nrm, uvs, cols, idx, (x - 0.05, 2.9, -span / 2), (x + 0.05, 2.9, -span / 2), (x + 0.05, 2.9, span / 2), (x - 0.05, 2.9, span / 2), rail)
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def pine_tree(height=6.0, color=(0.12, 0.28, 0.14)) -> MeshData:
    trunk = box(0.32, height * 0.38, 0.32, (0.38, 0.24, 0.14), (0, height * 0.19, 0))
    pos, nrm, uvs, cols, idx = _empty()
    layers = [
        (height * 0.22, 2.35, 0.72),
        (height * 0.34, 2.05, 0.80),
        (height * 0.46, 1.70, 0.88),
        (height * 0.58, 1.30, 0.96),
        (height * 0.70, 0.92, 1.04),
        (height * 0.80, 0.58, 1.10),
        (height * 0.88, 0.28, 1.16),
    ]
    for y, r, shade in layers:
        tip = y + height * 0.14
        segs = 14
        for k in range(segs):
            a0 = k * math.pi * 2 / segs
            a1 = (k + 1) * math.pi * 2 / segs
            rr = r * (0.90 + 0.10 * math.sin(k * 2.1 + y))
            p0 = (0.0, tip, 0.0)
            p1 = (math.cos(a0) * rr, y, math.sin(a0) * rr)
            p2 = (math.cos(a1) * rr, y, math.sin(a1) * rr)
            edge = 0.82 + 0.18 * abs(math.cos(a0 * 0.5))
            c = (color[0] * shade * edge, color[1] * shade * edge, color[2] * shade * edge)
            _add_tri(pos, nrm, uvs, cols, idx, p0, p1, p2, c)
    foliage = MeshData(
        np.array(pos, np.float32),
        np.array(nrm, np.float32),
        np.array(uvs, np.float32),
        np.array(cols, np.float32),
        np.array(idx, np.uint32),
    )
    return merge_meshes([trunk, foliage])


def deciduous_tree(height=5.5, color=(0.22, 0.42, 0.18)) -> MeshData:
    """Irregular canopy tree for Europe / town stretches."""
    trunk = box(0.28, height * 0.42, 0.28, (0.4, 0.26, 0.14), (0, height * 0.21, 0))
    canopy_y = height * 0.58
    layers = []
    blobs = (
        (1.05, 0.75, -0.05, 0.15, 0.0),
        (0.85, 0.9, 0.2, -0.25, 0.1),
        (0.7, 1.0, 0.55, 0.2, -0.15),
        (0.55, 1.08, 0.85, -0.1, 0.2),
        (0.95, 0.82, 0.15, 0.35, 0.25),
        (0.6, 0.95, 0.4, -0.3, -0.2),
    )
    for sc, shade, yo, xo, zo in blobs:
        c = (color[0] * shade, color[1] * shade, color[2] * shade)
        layers.append(
            transform_mesh(
                sphere(height * 0.26 * sc, stacks=9, slices=12, color=c),
                translate=(xo * height * 0.12, canopy_y + yo * height * 0.18, zo * height * 0.12),
            )
        )
    return merge_meshes([trunk] + layers)


def iwan_arch(width=10.0, height=16.0, depth=4.0) -> MeshData:
    """Persian ceremonial pointed arch portal with mosaic colors."""
    pos, nrm, uvs, cols, idx = _empty()
    mosaic = [
        (0.1, 0.35, 0.55),
        (0.15, 0.55, 0.6),
        (0.75, 0.62, 0.18),
        (0.2, 0.45, 0.5),
    ]
    # outer frame
    hw, hh, hd = width * 0.5, height, depth * 0.5
    brick = (0.72, 0.45, 0.28)
    # left pillar
    _add_quad(pos, nrm, uvs, cols, idx, (-hw, 0, -hd), (-hw + 1.5, 0, -hd), (-hw + 1.5, hh * 0.75, -hd), (-hw, hh * 0.75, -hd), brick)
    _add_quad(pos, nrm, uvs, cols, idx, (hw - 1.5, 0, -hd), (hw, 0, -hd), (hw, hh * 0.75, -hd), (hw - 1.5, hh * 0.75, -hd), brick)
    # pointed arch
    segs = 20
    for i in range(segs):
        t0 = i / segs
        t1 = (i + 1) / segs
        # pointed: two circular arcs
        def arch_y(t):
            if t < 0.5:
                a = t * 2
                return hh * 0.75 + math.sin(a * math.pi * 0.5) * hh * 0.35
            a = (t - 0.5) * 2
            return hh * 0.75 + math.sin((1 - a) * math.pi * 0.5) * hh * 0.35

        def arch_x(t):
            return -hw + 1.5 + t * (width - 3.0)

        c = mosaic[i % len(mosaic)]
        p0 = (arch_x(t0), arch_y(t0), -hd)
        p1 = (arch_x(t1), arch_y(t1), -hd)
        p2 = (arch_x(t1), arch_y(t1), hd)
        p3 = (arch_x(t0), arch_y(t0), hd)
        _add_quad(pos, nrm, uvs, cols, idx, p0, p1, p2, p3, c)
        # inner face tiles
        p0i = (arch_x(t0), 0, -hd + 0.1)
        p1i = (arch_x(t1), 0, -hd + 0.1)
        p2i = (arch_x(t1), arch_y(t1), -hd + 0.1)
        p3i = (arch_x(t0), arch_y(t0), -hd + 0.1)
        if i % 2 == 0:
            _add_quad(pos, nrm, uvs, cols, idx, p0i, p1i, p2i, p3i, mosaic[(i + 1) % 4])
    # top crown
    _add_quad(pos, nrm, uvs, cols, idx, (-hw, hh * 0.95, -hd), (hw, hh * 0.95, -hd), (hw, hh, -hd), (-hw, hh, -hd), (0.85, 0.7, 0.25))
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def suspension_bridge(span=50.0, width=6.0, towers=2) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    deck_c = (0.4, 0.4, 0.42)
    cable_c = (0.7, 0.68, 0.6)
    tower_c = (0.55, 0.52, 0.48)
    hw = width * 0.5
    # deck with slight sag
    segs = 40
    for i in range(segs):
        z0 = -span / 2 + span * i / segs
        z1 = -span / 2 + span * (i + 1) / segs
        sag0 = 0.8 * (1 - ((z0) / (span / 2)) ** 2)
        sag1 = 0.8 * (1 - ((z1) / (span / 2)) ** 2)
        y0, y1 = 4.0 + sag0, 4.0 + sag1
        _add_quad(pos, nrm, uvs, cols, idx, (-hw, y0, z0), (hw, y0, z0), (hw, y1, z1), (-hw, y1, z1), deck_c)
    # towers
    for tz in (-span * 0.35, span * 0.35):
        for x in (-hw - 0.5, hw + 0.5):
            _add_quad(pos, nrm, uvs, cols, idx, (x - 0.4, 0, tz - 0.4), (x + 0.4, 0, tz - 0.4), (x + 0.4, 14, tz - 0.4), (x - 0.4, 14, tz - 0.4), tower_c)
            _add_quad(pos, nrm, uvs, cols, idx, (x - 0.4, 0, tz + 0.4), (x + 0.4, 0, tz + 0.4), (x + 0.4, 14, tz + 0.4), (x - 0.4, 14, tz + 0.4), tower_c)
    # main cables
    for x in (-hw, hw):
        for i in range(segs):
            z0 = -span / 2 + span * i / segs
            z1 = -span / 2 + span * (i + 1) / segs
            # parabola between towers
            def cy(z):
                t = abs(z) / (span * 0.35)
                return 12.0 - 6.0 * min(t, 1.0) ** 2

            y0, y1 = cy(z0), cy(z1)
            _add_quad(pos, nrm, uvs, cols, idx, (x - 0.05, y0, z0), (x + 0.05, y0, z0), (x + 0.05, y1, z1), (x - 0.05, y1, z1), cable_c)
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def fairy_chimney(height=8.0, color=(0.72, 0.55, 0.4)) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    rings = 10
    for i in range(rings):
        t0, t1 = i / rings, (i + 1) / rings
        y0, y1 = t0 * height, t1 * height
        r0 = 1.4 * (1.0 - t0 * 0.7) + (0.3 if i == rings - 1 else 0)
        r1 = 1.4 * (1.0 - t1 * 0.7) + (0.5 if i >= rings - 2 else 0)
        segs = 10
        for k in range(segs):
            a0 = k * 2 * math.pi / segs
            a1 = (k + 1) * 2 * math.pi / segs
            p0 = (math.cos(a0) * r0, y0, math.sin(a0) * r0)
            p1 = (math.cos(a1) * r0, y0, math.sin(a1) * r0)
            p2 = (math.cos(a1) * r1, y1, math.sin(a1) * r1)
            p3 = (math.cos(a0) * r1, y1, math.sin(a0) * r1)
            shade = 0.75 + 0.25 * abs(math.cos(a0))
            c = (color[0] * shade, color[1] * shade, color[2] * shade)
            _add_quad(pos, nrm, uvs, cols, idx, p0, p1, p2, p3, c)
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def hot_air_balloon(envelope_color=(0.85, 0.25, 0.2)) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    # striped sphere
    stacks, slices = 12, 16
    for i in range(stacks):
        v0 = i / stacks
        v1 = (i + 1) / stacks
        phi0 = v0 * math.pi
        phi1 = v1 * math.pi
        for j in range(slices):
            u0 = j / slices
            u1 = (j + 1) / slices
            th0 = u0 * 2 * math.pi
            th1 = u1 * 2 * math.pi
            r = 1.2

            def sph(phi, th):
                return (r * math.sin(phi) * math.cos(th), r * math.cos(phi) + 1.5, r * math.sin(phi) * math.sin(th))

            stripe = (j % 4) / 4.0
            c = (
                envelope_color[0] * (0.6 + 0.4 * stripe),
                envelope_color[1] * (0.5 + 0.5 * (1 - stripe)),
                envelope_color[2] * (0.7 + 0.3 * stripe),
            )
            _add_quad(pos, nrm, uvs, cols, idx, sph(phi0, th0), sph(phi0, th1), sph(phi1, th1), sph(phi1, th0), c)
    basket = box(0.5, 0.4, 0.5, (0.45, 0.3, 0.15), (0, -0.1, 0))
    return merge_meshes([MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32)), basket])


def pagoda(tiers=3, base=6.0) -> MeshData:
    meshes = []
    brick = (0.55, 0.22, 0.16)
    roof = (0.65, 0.15, 0.12)
    wood = (0.35, 0.2, 0.12)
    y = 0.0
    for t in range(tiers):
        scale = 1.0 - t * 0.22
        w = base * scale
        h = 1.8 * scale
        meshes.append(box(w * 0.7, h, w * 0.7, brick, (0, y + h * 0.5, 0)))
        # flared roof
        pos, nrm, uvs, cols, idx = _empty()
        rw = w * 0.55
        rh = 0.9 * scale
        y0 = y + h
        peak = y0 + rh
        for k in range(4):
            a0 = k * math.pi / 2 - math.pi / 4
            a1 = (k + 1) * math.pi / 2 - math.pi / 4
            # eave flare
            p0 = (math.cos(a0) * rw, y0, math.sin(a0) * rw)
            p1 = (math.cos(a1) * rw, y0, math.sin(a1) * rw)
            overhang = rw * 1.25
            e0 = (math.cos(a0) * overhang, y0 - 0.25 * scale, math.sin(a0) * overhang)
            e1 = (math.cos(a1) * overhang, y0 - 0.25 * scale, math.sin(a1) * overhang)
            _add_quad(pos, nrm, uvs, cols, idx, e0, e1, p1, p0, roof)
            _add_tri(pos, nrm, uvs, cols, idx, (0, peak, 0), p0, p1, roof)
        meshes.append(MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32)))
        # struts
        meshes.append(box(0.15, h * 0.4, 0.15, wood, (w * 0.25, y + h * 0.3, w * 0.25)))
        y += h + rh * 0.55
    # pinnacle
    meshes.append(box(0.2, 1.2, 0.2, (0.85, 0.7, 0.2), (0, y + 0.6, 0)))
    return merge_meshes(meshes)


def ghat_steps(width=48.0, steps=12, step_h=0.42, step_d=1.2, color=(0.62, 0.5, 0.4)) -> MeshData:
    """Stone bathing steps descending toward -X (river), extending along Z."""
    meshes = []
    stone_a = color
    stone_b = (color[0] * 0.88, color[1] * 0.88, color[2] * 0.9)
    for i in range(steps):
        y = i * step_h
        x = -i * step_d
        c = stone_a if i % 2 == 0 else stone_b
        meshes.append(box(step_d * 0.98, step_h * 0.92, width, c, (x - step_d * 0.5, y + step_h * 0.5, 0)))
    # top promenade (toward road / +X)
    top_y = steps * step_h
    meshes.append(box(5.5, 0.3, width + 6, (0.55, 0.44, 0.34), (3.2, top_y + 0.05, 0)))
    # short wall on promenade edge facing river
    meshes.append(box(0.25, 0.85, width + 4, (0.48, 0.36, 0.28), (0.6, top_y + 0.5, 0)))
    return merge_meshes(meshes)


def river_plane(size=70.0, color=(0.1, 0.32, 0.42)) -> MeshData:
    """Calm Ganges surface — kept narrow so it stays west of the road."""

    def h(x, z):
        return 0.03 * math.sin(x * 0.4) * math.cos(z * 0.3)

    def col(x, y, z):
        t = 0.5 + 0.5 * math.sin(x * 0.2 + z * 0.12)
        return (
            color[0] * (0.85 + 0.2 * t),
            color[1] * (0.9 + 0.15 * t),
            color[2] * (1.0 + 0.08 * t),
        )

    return ground_grid(size=size, divisions=64, height_fn=h, color_fn=col)


def river_bank(size=80.0) -> MeshData:
    """Stone/dust bank between road and water."""

    def h(x, z):
        # gentle slope toward river (-X)
        return max(0.0, 0.35 - 0.04 * max(0.0, -x))

    def col(x, y, z):
        return (0.42 + 0.04 * y, 0.34 + 0.03 * y, 0.26)

    return ground_grid(size=size, divisions=80, height_fn=h, color_fn=col)


def temple_cluster() -> MeshData:
    """Small riverside temple / shrine cluster for Varanasi banks."""
    parts = [
        box(3.2, 4.5, 3.2, (0.72, 0.55, 0.35), (0, 2.25, 0)),
        box(4.0, 0.35, 4.0, (0.55, 0.25, 0.18), (0, 4.6, 0)),
        transform_mesh(sphere(1.1, 10, 14, (0.85, 0.7, 0.35)), (0, 5.5, 0)),
        box(1.6, 2.8, 1.6, (0.65, 0.48, 0.3), (4.5, 1.4, 1.5)),
        box(2.0, 0.25, 2.0, (0.5, 0.22, 0.15), (4.5, 2.95, 1.5)),
        box(1.4, 2.2, 1.4, (0.7, 0.52, 0.32), (-4.0, 1.1, -1.2)),
    ]
    return merge_meshes(parts)


def boat(length=3.0, color=(0.4, 0.25, 0.12)) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    hl = length * 0.5
    # simple canoe hull
    pts = [(-hl, 0.1, 0), (-hl * 0.5, 0, 0.6), (hl * 0.5, 0, 0.6), (hl, 0.1, 0), (hl * 0.5, 0, -0.6), (-hl * 0.5, 0, -0.6)]
    _add_quad(pos, nrm, uvs, cols, idx, pts[1], pts[2], (pts[2][0], 0.5, pts[2][2]), (pts[1][0], 0.5, pts[1][2]), color)
    _add_quad(pos, nrm, uvs, cols, idx, pts[5], pts[4], (pts[4][0], 0.5, pts[4][2]), (pts[5][0], 0.5, pts[5][2]), color)
    _add_tri(pos, nrm, uvs, cols, idx, pts[0], pts[1], pts[5], color)
    _add_tri(pos, nrm, uvs, cols, idx, pts[3], pts[4], pts[2], color)
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def diya_lamp() -> MeshData:
    bowl = box(0.35, 0.08, 0.35, (0.2, 0.45, 0.15), (0, 0.04, 0))
    flame = box(0.06, 0.25, 0.06, (1.0, 0.7, 0.2), (0, 0.22, 0))
    return merge_meshes([bowl, flame])


def prayer_flag() -> MeshData:
    """Single rectangular flag in local space (hangs along +X)."""
    pos, nrm, uvs, cols, idx = _empty()
    _add_quad(pos, nrm, uvs, cols, idx, (0, -0.15, 0), (0.6, -0.15, 0), (0.6, 0.15, 0), (0, 0.15, 0), (1, 1, 1))
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def star_quad() -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    _add_quad(pos, nrm, uvs, cols, idx, (-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0), (1, 1, 1))
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def billboard_quad() -> Tuple[np.ndarray, np.ndarray]:
    """Unit quad centered, bottom at y=0: pos3 + uv2."""
    # x from -0.5..0.5, y from 0..1
    verts = np.array(
        [
            [-0.5, 0.0, 0.0, 0.0, 1.0],
            [0.5, 0.0, 0.0, 1.0, 1.0],
            [0.5, 1.0, 0.0, 1.0, 0.0],
            [-0.5, 0.0, 0.0, 0.0, 1.0],
            [0.5, 1.0, 0.0, 1.0, 0.0],
            [-0.5, 1.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    return verts, np.arange(6, dtype=np.uint32)


def sphere(radius=1.0, stacks=16, slices=24, color=(0.8, 0.8, 0.85)) -> MeshData:
    pos, nrm, uvs, cols, idx = _empty()
    for i in range(stacks):
        for j in range(slices):
            def sph(ii, jj):
                phi = ii / stacks * math.pi
                th = jj / slices * 2 * math.pi
                x = radius * math.sin(phi) * math.cos(th)
                y = radius * math.cos(phi)
                z = radius * math.sin(phi) * math.sin(th)
                return (x, y, z)

            p00, p10, p11, p01 = sph(i, j), sph(i, j + 1), sph(i + 1, j + 1), sph(i + 1, j)
            _add_quad(pos, nrm, uvs, cols, idx, p00, p10, p11, p01, color)
    return MeshData(np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uvs, np.float32), np.array(cols, np.float32), np.array(idx, np.uint32))


def mountain_range(width=140.0, depth=40.0, peaks=9, color=(0.75, 0.8, 0.88), snow=True) -> MeshData:
    def h(x, z):
        n = 0.0
        for i in range(peaks):
            cx = -width * 0.42 + i * (width * 0.84 / max(peaks - 1, 1))
            amp = 20.0 + (i % 3) * 9.0
            n += amp * math.exp(-((x - cx) ** 2) / (70.0 + i * 12) - (z ** 2) / 180.0)
            n += 1.2 * math.sin(x * 0.08 + i) * math.cos(z * 0.1)
        return max(0.0, n)

    def col(x, y, z):
        rock = (0.42 + 0.02 * math.sin(x * 0.2), 0.4, 0.38)
        if y > 14:
            t = min(1.0, (y - 14) / 12)
            return (
                rock[0] * (1 - t) + 0.95 * t,
                rock[1] * (1 - t) + 0.96 * t,
                rock[2] * (1 - t) + 0.98 * t,
            )
        return (0.48 + 0.02 * y, 0.5 + 0.015 * y, 0.52)

    base = ground_grid(size=width, divisions=96, color_fn=col, height_fn=h)
    return base


def _road_corridor(x: float, half_width: float = 4.2) -> float:
    """0 on road, 1 far from road — keeps the driving lane flat."""
    ax = abs(x)
    if ax <= half_width:
        return 0.0
    return min(1.0, (ax - half_width) / 5.5)


def _fbm2(x: float, z: float) -> float:
    return (
        1.00 * math.sin(x * 0.045) * math.cos(z * 0.038)
        + 0.50 * math.sin(x * 0.11 + z * 0.07)
        + 0.25 * math.sin(x * 0.23 - z * 0.19)
        + 0.12 * math.sin(x * 0.47 + z * 0.31)
        + 0.06 * math.sin(x * 0.91 - z * 0.73)
    )


def europe_hills(size=140.0) -> MeshData:
    def h(x, z):
        c = _road_corridor(x, 4.0)
        if c <= 0.0:
            return 0.0
        return c * (
            2.4 * _fbm2(x, z)
            + 0.55 * math.sin((x * 0.7 + z) * 0.09)
            + 0.2 * math.sin(x * 0.55) * math.sin(z * 0.4)
        )

    def col(x, y, z):
        soil = 0.04 * math.sin(x * 0.35) * math.cos(z * 0.28)
        g = 0.28 + 0.1 * math.sin(x * 0.12) + 0.06 * y + soil
        return (
            0.16 + 0.05 * y + soil * 0.5,
            min(0.58, 0.34 + g),
            0.14 + 0.04 * y,
        )

    return ground_grid(size=size, divisions=200, height_fn=h, color_fn=col)


def dune_terrain(size=140.0, color=(0.72, 0.48, 0.32)) -> MeshData:
    def h(x, z):
        c = _road_corridor(x, 4.2)
        if c <= 0.0:
            return 0.0
        return c * (
            3.6 * math.sin(x * 0.048 + 0.4) * math.cos(z * 0.036)
            + 1.6 * math.sin(x * 0.10 - z * 0.06)
            + 0.7 * math.sin(z * 0.18 + x * 0.05)
            + 0.25 * math.sin(x * 0.4) * math.cos(z * 0.35)
        )

    def col(x, y, z):
        t = min(1.0, max(0.0, y / 4.5))
        ripple = 0.04 * math.sin(x * 0.5 + z * 0.2)
        return (0.70 + 0.12 * t + ripple, 0.46 + 0.1 * t, 0.28 + 0.06 * t)

    return ground_grid(size=size, divisions=210, height_fn=h, color_fn=col)


def canyon_walls(length=100.0, height=30.0, gap=12.0, color=(0.45, 0.32, 0.25)) -> MeshData:
    def h(x, z):
        # Wide flat canyon floor for the road, steep walls outside
        ax = abs(x)
        if ax < 5.0:
            return 0.0
        edge = min(1.0, (ax - 5.0) / 3.5)
        wall = edge * edge * 18.0
        strata = 0.55 * math.sin(z * 0.09) * edge
        detail = 0.25 * math.sin(x * 0.35) * math.cos(z * 0.22) * edge
        return wall + strata + detail

    def col(x, y, z):
        band = 0.05 * math.sin(y * 1.1 + z * 0.05)
        return (
            min(0.75, 0.42 + 0.04 * y + band),
            min(0.55, 0.30 + 0.03 * y),
            min(0.4, 0.22 + 0.02 * y),
        )

    return ground_grid(size=max(length, 120.0), divisions=180, height_fn=h, color_fn=col)


def terrace_hills(size=150.0) -> MeshData:
    def h(x, z):
        c = _road_corridor(x, 4.5)
        if c <= 0.0:
            return 0.0
        base = c * (2.4 * math.sin(z * 0.038) + 1.4 * math.sin(x * 0.075) + 0.4 * _fbm2(x * 1.2, z))
        terr = math.floor((abs(x) - 8) * 0.28) * 0.9 if abs(x) > 8 else 0.0
        return max(0.0, base + max(0.0, terr) * c)

    def col(x, y, z):
        if y > 7:
            return (0.86, 0.89, 0.94)
        patch = 0.03 * math.sin(x * 0.3) * math.cos(z * 0.25)
        return (0.18 + 0.035 * y + patch, 0.40 + 0.05 * y, 0.16 + 0.02 * y)

    return ground_grid(size=size, divisions=190, height_fn=h, color_fn=col)


def merge_meshes(meshes: Sequence[MeshData]) -> MeshData:
    if not meshes:
        return box(0.1, 0.1, 0.1)
    pos, nrm, uvs, cols, idx = [], [], [], [], []
    offset = 0
    for m in meshes:
        pos.append(m.positions)
        nrm.append(m.normals)
        uvs.append(m.uvs)
        cols.append(m.colors)
        idx.append(m.indices + offset)
        offset += len(m.positions)
    return MeshData(
        np.concatenate(pos),
        np.concatenate(nrm),
        np.concatenate(uvs),
        np.concatenate(cols),
        np.concatenate(idx).astype(np.uint32),
    )


def transform_mesh(mesh: MeshData, translate=(0, 0, 0), scale=1.0) -> MeshData:
    pos = mesh.positions * scale + np.array(translate, np.float32)
    return MeshData(pos.astype(np.float32), mesh.normals.copy(), mesh.uvs.copy(), mesh.colors.copy(), mesh.indices.copy())
