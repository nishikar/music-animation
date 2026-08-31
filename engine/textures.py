"""Procedural textures via NumPy + Pillow — no external image files."""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _noise2d(w: int, h: int, scale: float = 8.0, seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    gw = max(2, int(w / scale) + 2)
    gh = max(2, int(h / scale) + 2)
    grid = rng.rand(gh, gw).astype(np.float32)
    ys = np.linspace(0, gh - 2, h)
    xs = np.linspace(0, gw - 2, w)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    # smoothstep
    sy = fy * fy * (3 - 2 * fy)
    sx = fx * fx * (3 - 2 * fx)
    n00 = grid[y0][:, x0]
    n10 = grid[y0][:, x0 + 1]
    n01 = grid[y0 + 1][:, x0]
    n11 = grid[y0 + 1][:, x0 + 1]
    return (n00 * (1 - sx) + n10 * sx) * (1 - sy) + (n01 * (1 - sx) + n11 * sx) * sy


def ripple_normal_map(size: int = 256, seed: int = 7) -> np.ndarray:
    """RGB normal map as uint8 HxWx3."""
    n1 = _noise2d(size, size, 12.0, seed)
    n2 = _noise2d(size, size, 5.0, seed + 3)
    hmap = n1 * 0.65 + n2 * 0.35
    dy, dx = np.gradient(hmap)
    nx = -dx * 4.0
    ny = -dy * 4.0
    nz = np.ones_like(nx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length
    rgb = np.stack([(nx + 1) * 0.5, (ny + 1) * 0.5, (nz + 1) * 0.5], axis=-1)
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


def brick_texture(size: int = 256) -> np.ndarray:
    img = Image.new("RGBA", (size, size), (140, 70, 55, 255))
    draw = ImageDraw.Draw(img)
    bh, bw = size // 8, size // 4
    for row in range(0, size, bh):
        off = (bw // 2) if (row // bh) % 2 else 0
        for col in range(-bw, size + bw, bw):
            x0 = col + off
            shade = 120 + ((row * 3 + col * 7) % 40)
            draw.rectangle([x0 + 1, row + 1, x0 + bw - 2, row + bh - 2], fill=(shade, shade // 2, shade // 3, 255))
    return np.array(img, dtype=np.uint8)


def mosaic_texture(size: int = 256) -> np.ndarray:
    img = Image.new("RGBA", (size, size), (20, 60, 90, 255))
    draw = ImageDraw.Draw(img)
    colors = [(30, 90, 140), (40, 140, 150), (200, 160, 50), (25, 70, 110), (180, 50, 40)]
    cell = size // 16
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            c = colors[(x // cell + y // cell * 3) % len(colors)]
            draw.rectangle([x + 1, y + 1, x + cell - 2, y + cell - 2], fill=(*c, 255))
            # diamond overlay
            if (x // cell + y // cell) % 3 == 0:
                cx, cy = x + cell // 2, y + cell // 2
                r = cell // 3
                draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=(220, 180, 60, 200))
    return np.array(img, dtype=np.uint8)


def noise_texture(size: int = 256, seed: int = 1) -> np.ndarray:
    n = _noise2d(size, size, 6.0, seed)
    rgb = np.stack([n, n, n], axis=-1)
    return (rgb * 255).astype(np.uint8)


def color_grade_lut(size: int = 32) -> np.ndarray:
    """3D LUT pushing toward warm amber / terracotta 1970s grade. RGBA optional — RGB only."""
    lut = np.zeros((size, size, size, 3), dtype=np.float32)
    for b in range(size):
        for g in range(size):
            for r in range(size):
                rf, gf, bf = r / (size - 1), g / (size - 1), b / (size - 1)
                # lift shadows slightly warm, compress blues, lift reds/ambers
                rr = rf * 1.08 + 0.02
                gg = gf * 0.98 + 0.01
                bb = bf * 0.88
                # soft contrast
                def soft(x):
                    return x * x * (3 - 2 * x) * 0.35 + x * 0.65

                rr, gg, bb = soft(rr), soft(gg), soft(bb)
                # terracotta push
                rr = min(1.0, rr * 1.05 + gg * 0.03)
                gg = min(1.0, gg * 0.95 + rr * 0.04)
                bb = min(1.0, bb * 0.9)
                lut[b, g, r] = (rr, gg, bb)
    return (lut * 255).astype(np.uint8)


def crawl_text_texture(text: str, width: int = 2048, height: int = 2048) -> np.ndarray:
    """Golden Star-Wars-style crawl text — large, centered, fills most of the atlas."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def _font(size: int):
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
        ):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    # Pick the largest size that still fits with margins.
    font = _font(120)
    for size in (140, 120, 100, 84, 72):
        font = _font(size)
        widths = []
        ok = True
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            widths.append(tw)
            if tw > width * 0.92:
                ok = False
                break
        if ok:
            break

    line_gap = int(font.size * 1.55)
    total_h = line_gap * len(lines)
    y = (height - total_h) // 2
    gold = (255, 232, 31, 255)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        for ox, oy, a in ((0, 0, 110), (3, 3, 70), (-3, -2, 50), (6, 0, 40)):
            draw.text((x + ox, y + oy), line, font=font, fill=(255, 200, 40, a))
        draw.text((x, y), line, font=font, fill=gold)
        y += line_gap
    return np.array(img, dtype=np.uint8)


def cloud_texture(size: int = 512, seed: int = 11) -> np.ndarray:
    n = _noise2d(size, size, 18.0, seed) * 0.55 + _noise2d(size, size, 7.0, seed + 2) * 0.45
    alpha = np.clip((n - 0.35) * 2.5, 0, 1)
    rgb = np.stack([n * 0.55 + 0.25, n * 0.5 + 0.28, n * 0.65 + 0.4], axis=-1)
    rgba = np.concatenate([rgb, alpha[..., None]], axis=-1)
    return (np.clip(rgba, 0, 1) * 255).astype(np.uint8)
