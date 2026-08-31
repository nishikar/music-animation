"""Procedural 2D billboard sprite art — production cutouts with soft shading."""

from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _img(w: int, h: int) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _soft(im: Image.Image) -> Image.Image:
    return im.filter(ImageFilter.SMOOTH_MORE)


def _shade(c: Tuple[int, int, int], k: float) -> Tuple[int, int, int, int]:
    return (
        max(0, min(255, int(c[0] * k))),
        max(0, min(255, int(c[1] * k))),
        max(0, min(255, int(c[2] * k))),
        255,
    )


def make_vw_bus(w: int = 896, h: int = 512) -> np.ndarray:
    im, d = _img(w, h)
    cream = (248, 240, 220)
    orange = (204, 82, 32)
    chrome = (190, 195, 200)
    shade = (150, 50, 20)

    d.ellipse([80, 448, 820, 492], fill=(0, 0, 0, 75))

    # body
    d.rounded_rectangle([56, 230, 840, 410], radius=22, fill=_shade(orange, 1.0))
    d.rounded_rectangle([56, 108, 840, 242], radius=16, fill=_shade(cream, 1.0))
    d.rectangle([60, 378, 836, 410], fill=_shade(shade, 1.0))
    # subtle body highlight
    d.rectangle([70, 250, 200, 310], fill=(255, 140, 80, 40))
    d.rectangle([70, 120, 200, 170], fill=(255, 255, 255, 35))

    # split windshield with reflections
    for x0, x1 in ((82, 200), (214, 332)):
        d.rounded_rectangle([x0, 126, x1, 222], radius=7, fill=(105, 160, 195, 235))
        d.polygon([(x0 + 8, 132), (x1 - 18, 132), (x1 - 40, 168), (x0 + 8, 155)], fill=(200, 230, 245, 90))
    d.line([(207, 126), (207, 222)], fill=(70, 55, 40, 255), width=6)

    for x in (370, 485, 600, 710):
        d.rounded_rectangle([x, 134, x + 90, 216], radius=6, fill=(95, 150, 185, 215))
        d.rectangle([x + 8, 142, x + 82, 168], fill=(175, 210, 230, 85))

    colors = [(220, 40, 40), (240, 140, 30), (240, 220, 50), (40, 180, 70), (40, 100, 220), (120, 60, 180)]
    y = 238
    for c in colors:
        d.rectangle([60, y, 836, y + 8], fill=(*c, 255))
        y += 9

    for cx, cy in ((410, 330), (550, 342), (690, 325)):
        d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(245, 210, 80, 255))
        for a in range(0, 360, 36):
            px = cx + int(math.cos(math.radians(a)) * 26)
            py = cy + int(math.sin(math.radians(a)) * 26)
            d.ellipse([px - 11, py - 11, px + 11, py + 11], fill=(65, 145, 215, 255))
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(210, 55, 120, 255))

    d.rectangle([48, 400, 850, 422], fill=_shade(chrome, 1.0))
    d.ellipse([64, 250, 100, 286], fill=(255, 240, 170, 255))
    d.ellipse([72, 258, 92, 278], fill=(255, 255, 220, 255))

    for wx in (185, 680):
        d.ellipse([wx - 48, 380, wx + 48, 476], fill=(22, 22, 26, 255))
        d.ellipse([wx - 22, 404, wx + 22, 452], fill=_shade(chrome, 1.0))
        d.ellipse([wx - 8, 418, wx + 8, 438], fill=(40, 40, 45, 255))
        for a in range(0, 360, 60):
            px = wx + int(math.cos(math.radians(a)) * 14)
            py = 428 + int(math.sin(math.radians(a)) * 14)
            d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(120, 120, 125, 255))

    d.rectangle([140, 82, 760, 102], fill=_shade(chrome, 0.95))
    d.rounded_rectangle([160, 42, 290, 90], radius=7, fill=(70, 45, 30, 255))
    d.rounded_rectangle([310, 48, 500, 90], radius=7, fill=(95, 55, 32, 255))
    d.rounded_rectangle([520, 44, 650, 90], radius=7, fill=(45, 55, 75, 255))
    d.rounded_rectangle([670, 50, 740, 90], radius=5, fill=(60, 40, 25, 255))

    return np.array(_soft(im), dtype=np.uint8)


def _face(d, cx, cy, skin, hair, long_hair=False, glasses=False, topi=False, cap=False):
    skin_t = _shade(skin, 1.0)
    skin_s = _shade(skin, 0.82)
    d.rectangle([cx - 12, cy + 30, cx + 12, cy + 52], fill=skin_s)
    d.ellipse([cx - 36, cy - 42, cx + 36, cy + 36], fill=skin_t)
    # cheek / nose soft shade
    d.ellipse([cx - 8, cy + 2, cx + 8, cy + 22], fill=_shade(skin, 0.92))

    if long_hair:
        d.ellipse([cx - 40, cy - 48, cx + 40, cy + 10], fill=_shade(hair, 1.0))
        d.rectangle([cx - 42, cy - 6, cx - 26, cy + 62], fill=_shade(hair, 0.95))
        d.rectangle([cx + 26, cy - 6, cx + 42, cy + 62], fill=_shade(hair, 0.95))
        d.ellipse([cx - 38, cy - 50, cx + 38, cy - 8], fill=_shade(hair, 1.08 if hair[0] < 200 else 0.95))
    else:
        d.ellipse([cx - 38, cy - 50, cx + 38, cy + 6], fill=_shade(hair, 1.0))

    if topi:
        d.rectangle([cx - 38, cy - 56, cx + 38, cy - 24], fill=(165, 32, 42, 255))
        for i in range(5):
            d.rectangle([cx - 30 + i * 13, cy - 52, cx - 22 + i * 13, cy - 28], fill=(230, 190, 55, 255))
        d.rectangle([cx - 40, cy - 28, cx + 40, cy - 22], fill=(140, 25, 35, 255))
    if cap:
        d.ellipse([cx - 38, cy - 48, cx + 38, cy - 10], fill=(32, 32, 38, 255))
        d.rectangle([cx - 6, cy - 16, cx + 42, cy - 4], fill=(32, 32, 38, 255))

    # eyes with whites
    d.ellipse([cx - 16, cy - 6, cx - 2, cy + 8], fill=(245, 245, 248, 255))
    d.ellipse([cx + 2, cy - 6, cx + 16, cy + 8], fill=(245, 245, 248, 255))
    d.ellipse([cx - 12, cy - 2, cx - 5, cy + 5], fill=(35, 28, 22, 255))
    d.ellipse([cx + 6, cy - 2, cx + 13, cy + 5], fill=(35, 28, 22, 255))
    d.arc([cx - 12, cy + 14, cx + 12, cy + 28], 25, 155, fill=(130, 75, 65, 255), width=2)
    if glasses:
        d.rectangle([cx - 24, cy - 10, cx - 1, cy + 12], outline=(25, 25, 30, 255), width=3)
        d.rectangle([cx + 1, cy - 10, cx + 24, cy + 12], outline=(25, 25, 30, 255), width=3)
        d.line([(cx - 1, cy + 1), (cx + 1, cy + 1)], fill=(25, 25, 30, 255), width=2)


def _person(
    w: int = 320,
    h: int = 480,
    skin=(220, 180, 145),
    hair=(40, 30, 25),
    shirt=(180, 60, 40),
    pants=(40, 45, 60),
    long_hair=False,
    cap=False,
    glasses=False,
    topi=False,
    scarf=False,
    instrument: str | None = None,
    jacket=None,
) -> np.ndarray:
    im, d = _img(w, h)
    cx = w // 2
    d.ellipse([cx - 58, h - 34, cx + 58, h - 10], fill=(0, 0, 0, 60))

    # legs with crease
    d.rounded_rectangle([cx - 40, h - 155, cx - 6, h - 22], radius=7, fill=_shade(pants, 1.0))
    d.rounded_rectangle([cx + 6, h - 155, cx + 40, h - 22], radius=7, fill=_shade(pants, 1.0))
    d.rectangle([cx - 38, h - 120, cx - 10, h - 116], fill=_shade(pants, 0.75))
    d.rectangle([cx + 10, h - 120, cx + 38, h - 116], fill=_shade(pants, 0.75))
    d.ellipse([cx - 44, h - 34, cx - 2, h - 12], fill=(25, 25, 28, 255))
    d.ellipse([cx + 2, h - 34, cx + 44, h - 12], fill=(25, 25, 28, 255))

    top = jacket or shirt
    d.rounded_rectangle([cx - 56, h - 300, cx + 56, h - 140], radius=12, fill=_shade(top, 1.0))
    d.rectangle([cx - 52, h - 290, cx - 20, h - 150], fill=_shade(top, 1.12))
    if jacket:
        d.rectangle([cx - 24, h - 288, cx + 24, h - 150], fill=_shade(shirt, 1.0))
        d.line([(cx, h - 288), (cx, h - 150)], fill=_shade(jacket, 0.7), width=2)

    d.rounded_rectangle([cx - 82, h - 285, cx - 54, h - 165], radius=9, fill=_shade(skin, 1.0))
    d.rounded_rectangle([cx + 54, h - 285, cx + 82, h - 165], radius=9, fill=_shade(skin, 0.92))

    _face(d, cx, h - 345, skin, hair, long_hair=long_hair, glasses=glasses, topi=topi, cap=cap)

    if scarf:
        d.polygon(
            [(cx + 22, h - 298), (cx + 98, h - 235), (cx + 80, h - 218), (cx + 30, h - 280)],
            fill=(230, 150, 45, 255),
        )
        d.polygon(
            [(cx + 28, h - 275), (cx + 70, h - 245), (cx + 60, h - 235)],
            fill=(210, 120, 35, 255),
        )

    if instrument == "bass":
        d.rounded_rectangle([cx - 6, h - 250, cx + 110, h - 205], radius=5, fill=(22, 22, 26, 255))
        d.ellipse([cx + 78, h - 275, cx + 140, h - 185], fill=(32, 32, 38, 255))
        d.ellipse([cx + 100, h - 250, cx + 118, h - 210], fill=(12, 12, 14, 255))
        d.rectangle([cx + 20, h - 258, cx + 28, h - 198], fill=(180, 180, 185, 255))
    elif instrument == "guitar":
        d.ellipse([cx + 35, h - 275, cx + 130, h - 165], fill=(185, 115, 42, 255))
        d.ellipse([cx + 48, h - 255, cx + 118, h - 185], fill=(150, 90, 35, 255))
        d.rectangle([cx + 75, h - 335, cx + 90, h - 210], fill=(70, 45, 28, 255))
        d.ellipse([cx + 68, h - 235, cx + 96, h - 200], fill=(35, 22, 12, 255))
    elif instrument == "tabla":
        d.ellipse([cx - 82, h - 145, cx - 18, h - 80], fill=(150, 95, 55, 255))
        d.ellipse([cx + 18, h - 140, cx + 78, h - 80], fill=(130, 85, 50, 255))
        d.ellipse([cx - 68, h - 130, cx - 32, h - 100], fill=(240, 230, 210, 255))
        d.ellipse([cx + 30, h - 126, cx + 66, h - 98], fill=(240, 230, 210, 255))
    elif instrument == "harmonium":
        d.rounded_rectangle([cx - 85, h - 195, cx + 90, h - 110], radius=7, fill=(95, 58, 32, 255))
        d.rectangle([cx - 80, h - 188, cx + 85, h - 168], fill=(70, 42, 24, 255))
        for i in range(12):
            col = (245, 245, 235, 255) if i % 7 else (25, 25, 28, 255)
            d.rectangle([cx - 72 + i * 13, h - 185, cx - 64 + i * 13, h - 145], fill=col)
        d.rectangle([cx - 85, h - 110, cx + 90, h - 96], fill=(70, 40, 22, 255))
        # bellows hint
        for i in range(4):
            yy = h - 108 + i * 4
            d.line([(cx - 70, yy), (cx + 75, yy)], fill=(60, 35, 20, 180), width=1)

    return np.array(_soft(im), dtype=np.uint8)


def make_jingle_truck(w: int = 800, h: int = 500) -> np.ndarray:
    im, d = _img(w, h)
    d.ellipse([50, 438, 760, 485], fill=(0, 0, 0, 65))
    d.rounded_rectangle([48, 240, 760, 395], radius=10, fill=(25, 90, 150, 255))
    d.rounded_rectangle([48, 130, 255, 300], radius=10, fill=(210, 45, 55, 255))
    d.rounded_rectangle([70, 148, 235, 228], radius=6, fill=(110, 170, 210, 220))
    d.polygon([(35, 135), (145, 48), (260, 135)], fill=(170, 110, 55, 255))
    for i in range(7):
        x = 280 + i * 62
        d.ellipse([x, 268, x + 52, 332], fill=(245, 190, 45, 255))
        d.ellipse([x + 14, 282, x + 40, 320], fill=(210, 45, 120, 255))
    d.ellipse([470, 250, 620, 370], fill=(35, 150, 100, 255))
    d.ellipse([510, 275, 580, 345], fill=(45, 70, 170, 255))
    for x in range(280, 740, 30):
        d.line([(x, 395), (x, 438)], fill=(210, 180, 70, 255), width=2)
        d.ellipse([x - 5, 432, x + 5, 448], fill=(190, 160, 55, 255))
    for wx in (135, 620):
        d.ellipse([wx - 44, 365, wx + 44, 460], fill=(25, 25, 30, 255))
        d.ellipse([wx - 16, 392, wx + 16, 436], fill=(165, 165, 170, 255))
    return np.array(_soft(im), dtype=np.uint8)


def build_sprite_atlas() -> Dict[str, np.ndarray]:
    return {
        "vw_bus": make_vw_bus(),
        "jingle_truck": make_jingle_truck(),
        "anthony": _person(
            shirt=(220, 75, 45), pants=(35, 35, 40), long_hair=True, scarf=True, hair=(45, 30, 22)
        ),
        "chad": _person(
            shirt=(45, 45, 55), pants=(50, 50, 58), cap=True, hair=(28, 28, 30), instrument="tabla"
        ),
        "flea": _person(
            shirt=(245, 245, 248), pants=(28, 28, 32), hair=(30, 25, 20), instrument="bass"
        ),
        "john": _person(
            shirt=(55, 85, 110), pants=(40, 40, 48), long_hair=True, hair=(38, 28, 22), instrument="guitar"
        ),
        "narayan": _person(
            w=360,
            h=540,
            skin=(205, 165, 125),
            hair=(22, 18, 15),
            shirt=(245, 245, 248),
            pants=(28, 28, 32),
            jacket=(40, 40, 45),
            glasses=True,
            topi=True,
            instrument="harmonium",
        ),
        "sadhu": _person(
            skin=(210, 170, 130),
            hair=(235, 235, 240),
            shirt=(225, 125, 45),
            pants=(210, 110, 40),
            long_hair=True,
        ),
    }
