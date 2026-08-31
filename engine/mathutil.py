"""Pure math helpers — all animation is a function of t."""

from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple

import glm
import numpy as np


Vec3 = Tuple[float, float, float]


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = clamp((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def smootherstep(edge0: float, edge1: float, x: float) -> float:
    t = clamp((x - edge0) / (edge1 - edge0))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def lerp_vec3(a: Sequence[float], b: Sequence[float], t: float) -> glm.vec3:
    t = clamp(t)
    return glm.vec3(
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def mix_color(a: Sequence[float], b: Sequence[float], t: float) -> Tuple[float, float, float]:
    t = clamp(t)
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def hash01(n: int) -> float:
    """Deterministic pseudo-random in [0, 1)."""
    x = ((n * 374761393) + 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    return (x & 0xFFFFFF) / float(0x1000000)


def hash2(i: int, j: int = 0) -> float:
    return hash01(i * 73856093 ^ j * 19349663)


def ease_in_out(t: float) -> float:
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def remap(v: float, in0: float, in1: float, out0: float = 0.0, out1: float = 1.0) -> float:
    if abs(in1 - in0) < 1e-9:
        return out0
    return lerp(out0, out1, clamp((v - in0) / (in1 - in0)))


def orbit_pos(center: Sequence[float], radius: float, angle: float, height: float = 0.0) -> glm.vec3:
    return glm.vec3(
        center[0] + math.cos(angle) * radius,
        center[1] + height,
        center[2] + math.sin(angle) * radius,
    )


def look_at(eye: glm.vec3, target: glm.vec3, up: glm.vec3 = glm.vec3(0, 1, 0)) -> glm.mat4:
    return glm.lookAt(eye, target, up)


def perspective(fovy_deg: float, aspect: float, near: float = 0.1, far: float = 800.0) -> glm.mat4:
    return glm.perspective(glm.radians(fovy_deg), aspect, near, far)


def mat4_bytes(m: glm.mat4) -> bytes:
    """Column-major float32 bytes compatible with GLSL / std140."""
    return np.array(m, dtype=np.float32).tobytes(order="F")


def pack_camera_ubo(view: glm.mat4, proj: glm.mat4, cam_pos: glm.vec3) -> bytes:
    """Pack view, proj, cam_pos into std140 layout (144 bytes)."""
    data = np.zeros(36, dtype=np.float32)
    data[0:16] = np.array(view, dtype=np.float32).flatten(order="F")
    data[16:32] = np.array(proj, dtype=np.float32).flatten(order="F")
    data[32:36] = (cam_pos.x, cam_pos.y, cam_pos.z, 1.0)
    return data.tobytes()


def bezier3(p0: Sequence[float], p1: Sequence[float], p2: Sequence[float], p3: Sequence[float], t: float) -> glm.vec3:
    u = 1.0 - t
    uu = u * u
    tt = t * t
    return glm.vec3(
        uu * u * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + tt * t * p3[0],
        uu * u * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + tt * t * p3[1],
        uu * u * p0[2] + 3 * uu * t * p1[2] + 3 * u * tt * p2[2] + tt * t * p3[2],
    )


def catmull_rom(pts: Iterable[Sequence[float]], t: float) -> glm.vec3:
    pts = list(pts)
    n = len(pts)
    if n == 0:
        return glm.vec3(0)
    if n == 1:
        return glm.vec3(*pts[0])
    t = clamp(t)
    seg = t * (n - 1)
    i = int(seg)
    if i >= n - 1:
        return glm.vec3(*pts[-1])
    local = seg - i
    p0 = pts[max(i - 1, 0)]
    p1 = pts[i]
    p2 = pts[min(i + 1, n - 1)]
    p3 = pts[min(i + 2, n - 1)]
    t2 = local * local
    t3 = t2 * local
    return glm.vec3(
        0.5
        * (
            (2 * p1[0])
            + (-p0[0] + p2[0]) * local
            + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
            + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
        ),
        0.5
        * (
            (2 * p1[1])
            + (-p0[1] + p2[1]) * local
            + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
            + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
        ),
        0.5
        * (
            (2 * p1[2])
            + (-p0[2] + p2[2]) * local
            + (2 * p0[2] - 5 * p1[2] + 4 * p2[2] - p3[2]) * t2
            + (-p0[2] + 3 * p1[2] - 3 * p2[2] + p3[2]) * t3
        ),
    )
