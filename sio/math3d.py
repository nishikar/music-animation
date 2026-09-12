"""3D math helpers (column-major, OpenGL-friendly)."""

from __future__ import annotations

import math
import numpy as np


def identity() -> np.ndarray:
    return np.eye(4, dtype=np.float32)


def translate(x: float, y: float, z: float) -> np.ndarray:
    m = identity()
    m[0, 3] = x
    m[1, 3] = y
    m[2, 3] = z
    return m


def scale(x: float, y: float | None = None, z: float | None = None) -> np.ndarray:
    if y is None:
        y = x
    if z is None:
        z = x
    m = identity()
    m[0, 0] = x
    m[1, 1] = y
    m[2, 2] = z
    return m


def rotate_x(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    m = identity()
    m[1, 1] = c
    m[1, 2] = -s
    m[2, 1] = s
    m[2, 2] = c
    return m


def rotate_y(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    m = identity()
    m[0, 0] = c
    m[0, 2] = s
    m[2, 0] = -s
    m[2, 2] = c
    return m


def rotate_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    m = identity()
    m[0, 0] = c
    m[0, 1] = -s
    m[1, 0] = s
    m[1, 1] = c
    return m


def mul(*mats: np.ndarray) -> np.ndarray:
    out = mats[0]
    for m in mats[1:]:
        out = out @ m
    return out.astype(np.float32)


def perspective(fovy_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(math.radians(fovy_deg) * 0.5)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, target, up=(0.0, 1.0, 0.0)) -> np.ndarray:
    eye = np.asarray(eye, dtype=np.float32)
    target = np.asarray(target, dtype=np.float32)
    up = np.asarray(up, dtype=np.float32)
    f = target - eye
    f = f / (np.linalg.norm(f) + 1e-8)
    s = np.cross(f, up)
    s = s / (np.linalg.norm(s) + 1e-8)
    u = np.cross(s, f)
    m = identity()
    m[0, 0:3] = s
    m[1, 0:3] = u
    m[2, 0:3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def as_bytes(mat: np.ndarray) -> bytes:
    return np.ascontiguousarray(mat.T, dtype=np.float32).tobytes()
