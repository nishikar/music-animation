"""Geometry builders for wireframe / solid meshes."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def _append_line(buf: list, a, b, color):
    buf.extend([*a, *color, *b, *color])


def _cat(chunks):
    return np.concatenate([c for c in chunks if len(c)])


def grid_valley(width=40, depth=80, scale=1.0, height_fn=None) -> np.ndarray:
    """Interleaved pos+color line vertices for a wireframe Himalayan valley."""
    verts: list[float] = []
    half_w = width // 2
    for z in range(depth):
        for x in range(-half_w, half_w):
            def h(xx, zz):
                if height_fn:
                    return height_fn(xx, zz)
                edge = abs(xx) / half_w
                mountain = max(0.0, edge - 0.35) ** 2 * 14.0
                mountain *= 1.0 + 0.35 * math.sin(xx * 0.7 + zz * 0.15)
                mountain *= 1.0 + 0.25 * math.cos(zz * 0.4 + xx * 0.2)
                return mountain

            p00 = (x * scale, h(x, z), -z * scale)
            p10 = ((x + 1) * scale, h(x + 1, z), -z * scale)
            p01 = (x * scale, h(x, z + 1), -(z + 1) * scale)

            def col(p):
                t = min(1.0, p[1] / 10.0)
                return (0.15 + 0.7 * t, 0.85 - 0.55 * t, 0.95 - 0.35 * t)

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
        for i in range(sides):
            a0 = (i / sides) * math.tau - math.pi / 2
            a1 = ((i + 2) / sides) * math.tau - math.pi / 2
            p0 = (math.cos(a0) * radius, y, math.sin(a0) * radius)
            p1 = (math.cos(a1) * radius, y, math.sin(a1) * radius)
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


def _lathe_profile(profile, segments, color_fn) -> tuple[np.ndarray, np.ndarray]:
    """Revolution solid from (radius, y) profile with analytic-ish normals."""
    positions = []
    normals = []
    colors = []
    for yi, (r, y) in enumerate(profile):
        # tangent along profile
        if yi == 0:
            dr = profile[1][0] - r
            dy = profile[1][1] - y
        elif yi == len(profile) - 1:
            dr = r - profile[yi - 1][0]
            dy = y - profile[yi - 1][1]
        else:
            dr = profile[yi + 1][0] - profile[yi - 1][0]
            dy = profile[yi + 1][1] - profile[yi - 1][1]
        # normal in radial-y plane, then spin
        nr, ny = dy, -dr
        nlen = math.sqrt(nr * nr + ny * ny) + 1e-8
        nr, ny = nr / nlen, ny / nlen
        for i in range(segments):
            a = (i / segments) * math.tau
            ca, sa = math.cos(a), math.sin(a)
            positions.append((ca * r, y, sa * r))
            normals.append((ca * nr, ny, sa * nr))
            colors.append(color_fn(yi, i, r, y))
    indices = []
    for yi in range(len(profile) - 1):
        for i in range(segments):
            i0 = yi * segments + i
            i1 = yi * segments + (i + 1) % segments
            i2 = (yi + 1) * segments + i
            i3 = (yi + 1) * segments + (i + 1) % segments
            indices.extend([i0, i2, i1, i1, i2, i3])
    interleaved = []
    for p, n, c in zip(positions, normals, colors):
        interleaved.extend([*p, *n, *c])
    return np.asarray(interleaved, dtype=np.float32), np.asarray(indices, dtype=np.uint32)


def solid_lathe_bell(segments=72) -> tuple[np.ndarray, np.ndarray]:
    """Detailed brass temple bell with crown, waist bands, and flared lip."""
    # denser classic ghanta silhouette with crown jewel + thick lip
    profile = [
        (0.0, 1.42),    # tip
        (0.04, 1.38),
        (0.1, 1.32),
        (0.16, 1.24),   # crown bulb
        (0.12, 1.16),
        (0.1, 1.1),
        (0.14, 1.04),   # neck collar
        (0.2, 0.98),
        (0.3, 0.92),
        (0.42, 0.84),
        (0.52, 0.74),
        (0.6, 0.62),
        (0.66, 0.5),
        (0.7, 0.38),
        (0.72, 0.28),   # upper waist
        (0.7, 0.18),
        (0.68, 0.1),
        (0.74, 0.04),   # decorative ridge
        (0.7, -0.02),
        (0.66, -0.08),
        (0.7, -0.14),
        (0.78, -0.22),  # flare
        (0.86, -0.3),
        (0.9, -0.34),
        (0.84, -0.37),  # lip roll out
        (0.7, -0.38),
        (0.5, -0.385),
        (0.28, -0.39),
        (0.1, -0.392),
        (0.0, -0.393),
    ]

    def color_fn(yi, i, r, y):
        # warmer brass with subtle band darkening + crown highlight
        band = 0.82 if abs(y - 0.04) < 0.05 or abs(y - 0.28) < 0.04 else 1.0
        if y > 1.15:
            band *= 1.08  # crown brighter
        if y < -0.3:
            band *= 0.92  # lip slightly darker
        # faint engraved striation
        stripe = 0.94 if (i % 8) == 0 else 1.0
        return (0.95 * band * stripe, 0.74 * band * stripe, 0.24 * band * stripe)

    verts, idxs = _lathe_profile(profile, segments, color_fn)
    return verts, idxs


def solid_cylinder(radius, height, segments=32, color=(0.9, 0.75, 0.2)) -> tuple[np.ndarray, np.ndarray]:
    verts = []
    idxs = []
    for y in (-height / 2, height / 2):
        for i in range(segments):
            a = (i / segments) * math.tau
            x, z = math.cos(a) * radius, math.sin(a) * radius
            nx, nz = math.cos(a), math.sin(a)
            verts.extend([x, y, z, nx, 0.0, nz, *color])
    for i in range(segments):
        i0, i1 = i, (i + 1) % segments
        i2, i3 = segments + i, segments + (i + 1) % segments
        idxs.extend([i0, i1, i3, i0, i3, i2])
    bot_c = len(verts) // 9
    verts.extend([0, -height / 2, 0, 0, -1, 0, *color])
    top_c = len(verts) // 9
    verts.extend([0, height / 2, 0, 0, 1, 0, *color])
    for i in range(segments):
        i0, i1 = i, (i + 1) % segments
        idxs.extend([bot_c, i1, i0, top_c, segments + i0, segments + i1])
    return np.asarray(verts, dtype=np.float32), np.asarray(idxs, dtype=np.uint32)


def cylinder_wire(radius, height, segments=24, color=(1, 0.8, 0.2), rings=4) -> np.ndarray:
    verts: list[float] = []
    for ri in range(rings):
        y = -height / 2 + height * ri / max(1, rings - 1)
        for i in range(segments):
            a0 = (i / segments) * math.tau
            a1 = ((i + 1) / segments) * math.tau
            p0 = (math.cos(a0) * radius, y, math.sin(a0) * radius)
            p1 = (math.cos(a1) * radius, y, math.sin(a1) * radius)
            _append_line(verts, p0, p1, color)
    for i in range(0, segments, 2):
        a = (i / segments) * math.tau
        x, z = math.cos(a) * radius, math.sin(a) * radius
        _append_line(verts, (x, -height / 2, z), (x, height / 2, z), color)
    return np.asarray(verts, dtype=np.float32)


def hex_ring(radius, segments=6, color=(0.1, 1.0, 0.6), y=0.0) -> np.ndarray:
    return regular_polygon(segments, radius, y=y, color=color)


def prayer_wheel_wire(radius=0.7, height=2.6, segments=36) -> np.ndarray:
    """Detailed cylindrical prayer wheel with hubs, mantra band, and axle."""
    chunks = []
    gold = (1.0, 0.82, 0.22)
    dark = (0.85, 0.55, 0.12)
    ruby = (0.95, 0.2, 0.15)

    # main barrel rings (dense)
    for ri, y in enumerate(np.linspace(-height / 2 + 0.15, height / 2 - 0.25, 12)):
        c = gold if ri % 2 == 0 else dark
        chunks.append(circle_ring(radius, y=float(y), segments=segments, color=c))

    # vertical staves
    for i in range(segments):
        a = (i / segments) * math.tau
        x, z = math.cos(a) * radius, math.sin(a) * radius
        chunks.append(polyline(
            [(x, -height / 2 + 0.15, z), (x, height / 2 - 0.25, z)],
            gold if i % 3 else dark,
        ))

    # mantra band (middle chevron script)
    mid_y = 0.05
    for i in range(segments):
        a0 = (i / segments) * math.tau
        a1 = ((i + 0.5) / segments) * math.tau
        x0, z0 = math.cos(a0) * (radius * 1.02), math.sin(a0) * (radius * 1.02)
        x1, z1 = math.cos(a1) * (radius * 1.06), math.sin(a1) * (radius * 1.06)
        chunks.append(polyline(
            [(x0, mid_y - 0.12, z0), (x1, mid_y, z1), (x0, mid_y + 0.12, z0)],
            ruby,
        ))

    # top / bottom decorative flanges
    for y, r in ((height / 2 - 0.2, radius * 1.08), (-height / 2 + 0.12, radius * 1.08)):
        chunks.append(circle_ring(r, y=y, segments=segments, color=gold))
        chunks.append(circle_ring(r * 0.85, y=y + 0.08 * (1 if y > 0 else -1), segments=segments, color=dark))

    # axle + hubs
    chunks.append(cylinder_wire(0.08, height + 0.6, segments=10, color=dark, rings=3))
    chunks.append(circle_ring(0.22, y=height / 2 + 0.15, segments=16, color=gold))
    chunks.append(circle_ring(0.22, y=-height / 2 - 0.15, segments=16, color=gold))
    # jewel tip
    chunks.append(circle_ring(0.12, y=height / 2 + 0.35, segments=12, color=ruby))
    return _cat(chunks)


def mandala_tiers() -> list[dict]:
    """Concentric ornamental rings that spin around a central stupa."""
    tiers = []
    specs = [
        (12, 3.4, 0.12, False, (0.95, 0.75, 0.2)),
        (8, 2.9, 0.14, False, (0.9, 0.15, 0.15)),
        (10, 2.45, 0.12, False, (0.98, 0.8, 0.25)),
        (5, 2.05, 0.14, True, (0.95, 0.2, 0.18)),
        (8, 1.65, 0.12, False, (1.0, 0.82, 0.28)),
        (6, 1.25, 0.12, False, (0.9, 0.15, 0.15)),
        (8, 0.9, 0.1, False, (0.98, 0.78, 0.22)),
    ]
    y = 0.15
    for sides, radius, thick, star, color in specs:
        tiers.append({
            "sides": sides, "radius": radius, "y": y,
            "thick": thick, "star": star, "color": color,
        })
        y += thick + 0.04
    return tiers


def detailed_stupa_wire(scale=1.0) -> np.ndarray:
    """Architectural Nepali/Tibetan stupa: plinth, dome, harmika, 13 rings, pinnacle."""
    chunks = []
    white = (0.95, 0.95, 0.92)
    gold = (1.0, 0.82, 0.22)
    red = (0.9, 0.15, 0.15)
    blue = (0.2, 0.45, 0.95)

    # stepped plinth
    for i, (w, y, h) in enumerate([(3.6, 0.0, 0.18), (3.1, 0.2, 0.16), (2.7, 0.38, 0.14)]):
        chunks.append(box_wire(0, (y + h / 2) * scale, 0, w * scale, h * scale, w * scale, gold if i == 0 else white))

    # dome (anda) — lathed wire rings + meridians
    dome_profile = [
        (1.15, 0.55), (1.35, 0.75), (1.4, 1.0), (1.3, 1.25),
        (1.05, 1.5), (0.7, 1.7), (0.35, 1.85), (0.15, 1.95),
    ]
    for r, y in dome_profile:
        chunks.append(circle_ring(r * scale, y=y * scale, segments=40, color=white))
    for i in range(16):
        a = (i / 16) * math.tau
        pts = [(math.cos(a) * r * scale, y * scale, math.sin(a) * r * scale) for r, y in dome_profile]
        chunks.append(polyline(pts, white if i % 2 == 0 else (0.85, 0.85, 0.9)))

    # harmika (square shrine)
    chunks.append(box_wire(0, 2.15 * scale, 0, 0.7 * scale, 0.35 * scale, 0.7 * scale, gold))
    # Buddha eyes
    for sx in (-0.18, 0.18):
        chunks.append(circle_ring(0.08 * scale, y=2.2 * scale, segments=10, color=blue, z=0.36 * scale))
        data = chunks[-1].reshape(-1, 6)
        data[:, 0] += sx * scale
        chunks[-1] = data.reshape(-1)

    # 13 umbrella disks (chatravali)
    for i in range(13):
        w = (0.55 - i * 0.03) * scale
        y = (2.4 + i * 0.09) * scale
        chunks.append(box_wire(0, y, 0, w, 0.04 * scale, w, gold))
        chunks.append(circle_ring(w * 0.55, y=y + 0.02 * scale, segments=16, color=red))

    # pinnacle
    tip_y = 2.4 + 13 * 0.09
    chunks.append(circle_ring(0.08 * scale, y=(tip_y + 0.15) * scale, segments=12, color=gold))
    chunks.append(polyline([
        (0, tip_y * scale, 0),
        (0, (tip_y + 0.35) * scale, 0),
    ], gold))
    chunks.append(circle_ring(0.12 * scale, y=(tip_y + 0.4) * scale, segments=10, color=red))
    return _cat(chunks)


def pagoda_wireframe() -> np.ndarray:
    """Multi-tier Nepali pagoda with detailed eaves, pillars, windows, and bells."""
    chunks = []
    gold = (1.0, 0.85, 0.25)
    dark = (0.9, 0.65, 0.15)
    wood = (0.75, 0.45, 0.2)
    red = (0.9, 0.2, 0.15)

    # plinth + stairs
    chunks.append(box_wire(0, 0.12, 0, 5.2, 0.24, 5.2, wood))
    chunks.append(box_wire(0, 0.35, 0, 4.4, 0.22, 4.4, gold))
    for step in range(4):
        chunks.append(box_wire(0, 0.05 + step * 0.08, 2.7 + step * 0.08, 1.2 - step * 0.1, 0.06, 0.35, wood))

    y = 0.55
    widths = [3.6, 2.95, 2.35, 1.8, 1.25]
    for ti, width in enumerate(widths):
        # story body
        body_h = 0.55
        chunks.append(box_wire(0, y + body_h * 0.35, 0, width * 0.72, body_h * 0.7, width * 0.72, wood))
        # pillars at corners
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            px = sx * width * 0.32
            pz = sz * width * 0.32
            chunks.append(box_wire(px, y + body_h * 0.35, pz, 0.08, body_h * 0.7, 0.08, gold))
        # windows
        for face in range(4):
            ang = face * math.pi / 2
            wx = math.cos(ang) * width * 0.36
            wz = math.sin(ang) * width * 0.36
            chunks.append(box_wire(wx, y + body_h * 0.4, wz, 0.22, 0.28, 0.06, red))

        # roof eaves (upswept)
        eaves = width + 0.75
        roof_y = y + body_h
        apex_y = roof_y + 0.62
        corners = [
            (-eaves / 2, roof_y, -eaves / 2),
            (eaves / 2, roof_y, -eaves / 2),
            (eaves / 2, roof_y, eaves / 2),
            (-eaves / 2, roof_y, eaves / 2),
        ]
        # slightly upswept mid-edge points
        mids = [
            (0, roof_y + 0.08, -eaves / 2 - 0.12),
            (eaves / 2 + 0.12, roof_y + 0.08, 0),
            (0, roof_y + 0.08, eaves / 2 + 0.12),
            (-eaves / 2 - 0.12, roof_y + 0.08, 0),
        ]
        apex = (0, apex_y, 0)
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            m = mids[i]
            chunks.append(polyline([a, m, b, apex, a], gold))
            for k in range(1, 6):
                t = k / 6
                p0 = (a[0] + (apex[0] - a[0]) * t, a[1] + (apex[1] - a[1]) * t, a[2] + (apex[2] - a[2]) * t)
                p1 = (b[0] + (apex[0] - b[0]) * t, b[1] + (apex[1] - b[1]) * t, b[2] + (apex[2] - b[2]) * t)
                chunks.append(polyline([p0, p1], dark if k % 2 else gold))
            # hanging corner bell
            bx, by, bz = m[0] * 0.92, roof_y - 0.25, m[2] * 0.92
            chunks.append(polyline([(m[0], roof_y, m[2]), (bx, by, bz)], gold))
            chunks.append(circle_ring(0.08, y=by - 0.05, segments=10, color=gold, z=bz))
            data = chunks[-1].reshape(-1, 6)
            data[:, 0] += bx
            # circle_ring already at z offset via z= — fix by rebuild
            chunks[-1] = circle_ring(0.08, y=by - 0.05, segments=10, color=gold)
            data = chunks[-1].reshape(-1, 6)
            data[:, 0] += bx
            data[:, 2] += bz
            chunks[-1] = data.reshape(-1)

        # railing
        chunks.append(box_wire(0, roof_y - 0.15, 0, width * 0.85, 0.12, width * 0.85, gold))
        y = apex_y + 0.05

    # gajur finial
    chunks.append(box_wire(0, y + 0.15, 0, 0.18, 0.4, 0.18, gold))
    for i in range(5):
        chunks.append(circle_ring(0.22 - i * 0.03, y=y + 0.4 + i * 0.08, segments=14, color=gold if i % 2 == 0 else red))
    chunks.append(polyline([(0, y + 0.85, 0), (0, y + 1.15, 0)], gold))
    return _cat(chunks)


def lowpoly_stupa(x=0.0, z=0.0, scale=1.0) -> np.ndarray:
    """Detailed roadside stupa for the twilight ridge."""
    chunks = []
    white = (0.94, 0.94, 0.9)
    gold = (1.0, 0.8, 0.22)
    red = (0.88, 0.18, 0.15)

    # plinth
    chunks.append(box_wire(0, 0.08 * scale, 0, 1.6 * scale, 0.16 * scale, 1.6 * scale, gold))
    chunks.append(box_wire(0, 0.22 * scale, 0, 1.3 * scale, 0.12 * scale, 1.3 * scale, white))

    # dome rings + meridians
    dome = [(0.7, 0.35), (0.85, 0.55), (0.8, 0.8), (0.55, 1.0), (0.28, 1.15), (0.1, 1.25)]
    for r, y in dome:
        chunks.append(circle_ring(r * scale, y=y * scale, segments=28, color=white))
    for i in range(12):
        a = (i / 12) * math.tau
        pts = [(math.cos(a) * r * scale, y * scale, math.sin(a) * r * scale) for r, y in dome]
        chunks.append(polyline(pts, white))

    # harmika + spire
    chunks.append(box_wire(0, 1.4 * scale, 0, 0.4 * scale, 0.22 * scale, 0.4 * scale, gold))
    for i in range(9):
        w = (0.32 - i * 0.025) * scale
        chunks.append(box_wire(0, (1.55 + i * 0.07) * scale, 0, w, 0.035 * scale, w, gold))
    chunks.append(circle_ring(0.08 * scale, y=2.25 * scale, segments=10, color=red))

    data = _cat(chunks).reshape(-1, 6)
    data[:, 0] += x
    data[:, 2] += z
    return data.reshape(-1)


def prayer_flag_string(x0, z0, x1, z1, y=2.3, n_flags=10, sway=0.0) -> np.ndarray:
    """Colorful rectangular prayer flags along a rope between two poles."""
    chunks = []
    colors = [
        (0.2, 0.4, 1.0), (1.0, 1.0, 1.0), (0.9, 0.15, 0.12),
        (0.15, 0.7, 0.25), (1.0, 0.85, 0.15),
    ]
    # poles with tip finials
    wood = (0.45, 0.28, 0.12)
    gold = (1.0, 0.8, 0.2)
    for px, pz in ((x0, z0), (x1, z1)):
        chunks.append(polyline([(px, 0, pz), (px, y + 0.15, pz)], wood))
        chunks.append(polyline([(px, y + 0.15, pz), (px, y + 0.35, pz)], gold))
        ring = circle_ring(0.07, y=y + 0.22, segments=10, color=gold)
        data = ring.reshape(-1, 6)
        data[:, 0] += px
        data[:, 2] += pz
        chunks.append(data.reshape(-1))

    # sagging rope with wind ripples
    rope = []
    for i in range(32):
        t = i / 31
        x = x0 + (x1 - x0) * t
        z = z0 + (z1 - z0) * t
        yy = y + math.sin(t * math.pi) * -0.18 + math.sin(t * 10 + sway) * 0.05
        rope.append((x, yy, z))
    chunks.append(polyline(rope, (0.85, 0.75, 0.55)))

    # rectangular cloth flags with hem + diagonal fold lines
    for i in range(n_flags):
        t = (i + 0.5) / n_flags
        x = x0 + (x1 - x0) * t
        z = z0 + (z1 - z0) * t
        yy = y + math.sin(t * math.pi) * -0.18 + math.sin(t * 10 + sway) * 0.05
        c = colors[i % 5]
        fw, fh = 0.3, 0.42
        flutter = math.sin(sway * 2 + i * 0.9) * 0.08
        flutter2 = math.cos(sway * 1.5 + i) * 0.05
        # cloth as a small grid (more fabric-like)
        top_l = (x - fw / 2, yy, z)
        top_r = (x + fw / 2, yy, z)
        bot_l = (x - fw / 2 + flutter, yy - fh, z + flutter2)
        bot_r = (x + fw / 2 + flutter * 0.7, yy - fh * 0.92, z + flutter2 * 0.6)
        mid_l = (x - fw / 2 + flutter * 0.4, yy - fh * 0.5, z + flutter2 * 0.4)
        mid_r = (x + fw / 2 + flutter * 0.35, yy - fh * 0.48, z + flutter2 * 0.35)
        chunks.append(polyline([top_l, top_r, bot_r, bot_l, top_l], c))
        chunks.append(polyline([mid_l, mid_r], c))
        chunks.append(polyline([
            ((top_l[0] + top_r[0]) / 2, yy, z),
            ((bot_l[0] + bot_r[0]) / 2, (bot_l[1] + bot_r[1]) / 2, (bot_l[2] + bot_r[2]) / 2),
        ], c))
        # hanging thread at corners
        chunks.append(polyline([bot_l, (bot_l[0], bot_l[1] - 0.06, bot_l[2])], c))
        chunks.append(polyline([bot_r, (bot_r[0], bot_r[1] - 0.05, bot_r[2])], c))
    return _cat(chunks)


def utah_teapot_wire(scale=1.0) -> np.ndarray:
    """Classic wireframe teapot (body + spout + handle + lid) for the chai scene."""
    chunks = []
    c = (0.35, 0.9, 1.0)
    rim = (0.55, 0.95, 1.0)
    steam_c = (1.0, 0.5, 0.18)
    liquid = (1.0, 0.62, 0.22)
    brass = (1.0, 0.78, 0.35)

    # denser body profile (radius, y)
    body = [
        (0.12, 0.03), (0.32, 0.05), (0.52, 0.1), (0.68, 0.18),
        (0.8, 0.3), (0.88, 0.45), (0.92, 0.62), (0.9, 0.78),
        (0.84, 0.95), (0.72, 1.08), (0.58, 1.18), (0.42, 1.24),
        (0.32, 1.27),
    ]
    for r, y in body:
        chunks.append(circle_ring(r * scale, y=y * scale, segments=48, color=c))
    for i in range(24):
        a = (i / 24) * math.tau
        pts = [(math.cos(a) * r * scale, y * scale, math.sin(a) * r * scale) for r, y in body]
        chunks.append(polyline(pts, c if i % 2 == 0 else rim))

    # lid with stacked rings + knob
    lid = [(0.36, 1.29), (0.4, 1.33), (0.34, 1.38), (0.22, 1.44), (0.1, 1.49), (0.0, 1.52)]
    for r, y in lid:
        chunks.append(circle_ring(max(0.02, r) * scale, y=y * scale, segments=28, color=brass))
    for i in range(8):
        a = (i / 8) * math.tau
        pts = [(math.cos(a) * r * scale, y * scale, math.sin(a) * r * scale) for r, y in lid if r > 0]
        if len(pts) > 1:
            chunks.append(polyline(pts, brass))
    chunks.append(circle_ring(0.07 * scale, y=1.56 * scale, segments=14, color=liquid))
    chunks.append(circle_ring(0.04 * scale, y=1.6 * scale, segments=10, color=brass))

    # chai liquid surface + concentric ripples
    for rr in (0.58, 0.42, 0.28):
        chunks.append(circle_ring(rr * scale, y=1.06 * scale, segments=36, color=liquid))

    # spout — tapered curved tube with rings
    spout = []
    for i in range(18):
        t = i / 17
        x = (0.78 + t * 0.95) * scale
        y = (0.78 + math.sin(t * math.pi) * 0.38 + t * 0.12) * scale
        z = 0.0
        r = (0.15 - t * 0.08) * scale
        spout.append((x, y, z, r))
    for x, y, z, r in spout:
        chunks.append(circle_ring(r, y=y, segments=14, color=c, z=z))
        data = chunks[-1].reshape(-1, 6)
        data[:, 0] += x
        chunks[-1] = data.reshape(-1)
    chunks.append(polyline([(x, y, z) for x, y, z, r in spout], rim))
    # spout tip lip
    tip = spout[-1]
    chunks.append(circle_ring(tip[3] * 1.15, y=tip[1], segments=14, color=brass))
    data = chunks[-1].reshape(-1, 6)
    data[:, 0] += tip[0]
    chunks[-1] = data.reshape(-1)

    # handle — thick tube arc on -X with cross-section rings
    handle = []
    for i in range(20):
        t = i / 19
        ang = -math.pi * 0.12 + t * math.pi * 1.15
        x = (-0.52 + math.cos(ang) * 0.48) * scale
        y = (0.72 + math.sin(ang) * 0.42) * scale
        handle.append((x, y, 0.0))
    chunks.append(polyline(handle, rim))
    for i, (x, y, z) in enumerate(handle):
        if i % 2:
            continue
        chunks.append(circle_ring(0.08 * scale, y=y, segments=12, color=c))
        data = chunks[-1].reshape(-1, 6)
        data[:, 0] += x
        chunks[-1] = data.reshape(-1)
    # handle attachments
    for y_attach in (0.55, 0.95):
        chunks.append(polyline([
            (-0.55 * scale, y_attach * scale, 0),
            (-0.85 * scale, y_attach * scale, 0),
        ], brass))

    # foot / base rings
    for rr, yy in ((0.55, 0.02), (0.42, 0.0), (0.28, -0.01)):
        chunks.append(circle_ring(rr * scale, y=yy * scale, segments=36, color=brass if rr < 0.5 else c))

    # steam ribbons above lid
    for s in range(5):
        pts = []
        for k in range(20):
            yy = (1.58 + k * 0.09) * scale
            xx = (math.sin(k * 0.55 + s * 1.2) * (0.1 + k * 0.012) + (s - 2.0) * 0.08) * scale
            zz = (math.cos(k * 0.4 + s) * 0.09) * scale
            pts.append((xx, yy, zz))
        chunks.append(polyline(pts, steam_c))

    return _cat(chunks)


# Back-compat aliases used by scenes.py
tea_glass_wire = utah_teapot_wire


def lattice_structure() -> np.ndarray:
    """Kept for optional props; unused by default chai scene."""
    chunks = []
    colors = [(1.0, 0.2, 0.1), (1.0, 0.5, 0.1), (1.0, 0.85, 0.15)]
    rng = np.random.default_rng(3)
    for i in range(12):
        color = colors[i % 3]
        x, y, z = rng.uniform(-1, 1, 3)
        chunks.append(box_wire(x, y, z, 0.3, 0.3, 0.3, color))
    return _cat(chunks)
