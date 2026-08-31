"""Procedural 2D billboard sprite art (characters, VW bus, jingle trucks)."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw


def _img(w: int, h: int) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _ellipse(d, box, fill):
    d.ellipse(box, fill=fill)


def _rect(d, box, fill):
    d.rectangle(box, fill=fill)


def _poly(d, pts, fill):
    d.polygon(pts, fill=fill)


def make_vw_bus(w: int = 512, h: int = 320) -> np.ndarray:
    im, d = _img(w, h)
    # body
    cream = (245, 235, 210, 255)
    orange = (196, 78, 28, 255)
    chrome = (180, 185, 190, 255)
    # bottom hull
    _rect(d, [40, 140, 460, 250], orange)
    # top
    _rect(d, [40, 70, 460, 140], cream)
    # split windshield
    _rect(d, [50, 80, 120, 135], (120, 170, 200, 220))
    _rect(d, [125, 80, 195, 135], (120, 170, 200, 220))
    d.line([(122, 80), (122, 135)], fill=(80, 60, 40, 255), width=4)
    # side windows
    for x in (210, 280, 350):
        _rect(d, [x, 85, x + 55, 130], (100, 150, 180, 200))
    # rainbow stripes
    colors = [(220, 40, 40), (240, 140, 30), (240, 220, 50), (40, 180, 70), (40, 100, 220)]
    y = 145
    for c in colors:
        _rect(d, [40, y, 460, y + 6], (*c, 255))
        y += 7
    # flower mandalas
    for cx, cy in ((240, 190), (330, 200), (400, 185)):
        _ellipse(d, [cx - 22, cy - 22, cx + 22, cy + 22], (240, 200, 80, 255))
        _ellipse(d, [cx - 10, cy - 10, cx + 10, cy + 10], (200, 60, 120, 255))
        for a in range(0, 360, 45):
            import math
            px = cx + int(math.cos(math.radians(a)) * 16)
            py = cy + int(math.sin(math.radians(a)) * 16)
            _ellipse(d, [px - 5, py - 5, px + 5, py + 5], (80, 160, 220, 255))
    # wheels
    for wx in (100, 380):
        _ellipse(d, [wx - 28, 230, wx + 28, 286], (30, 30, 35, 255))
        _ellipse(d, [wx - 12, 246, wx + 12, 270], chrome)
    # roof rack
    _rect(d, [80, 50, 420, 62], chrome)
    # duffels / guitars on roof
    _rect(d, [100, 28, 170, 55], (60, 40, 30, 255))
    _rect(d, [180, 32, 300, 55], (90, 50, 30, 255))
    _rect(d, [310, 30, 400, 54], (40, 50, 70, 255))
    # headlight
    _ellipse(d, [42, 155, 62, 175], (255, 240, 180, 255))
    return np.array(im, dtype=np.uint8)


def _person(
    w: int,
    h: int,
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
) -> np.ndarray:
    im, d = _img(w, h)
    cx = w // 2
    # legs
    _rect(d, [cx - 28, h - 90, cx - 5, h - 10], (*pants, 255))
    _rect(d, [cx + 5, h - 90, cx + 28, h - 10], (*pants, 255))
    # torso
    _rect(d, [cx - 35, h - 200, cx + 35, h - 85], (*shirt, 255))
    # arms
    _rect(d, [cx - 55, h - 190, cx - 35, h - 110], (*skin, 255))
    _rect(d, [cx + 35, h - 190, cx + 55, h - 110], (*skin, 255))
    # head
    _ellipse(d, [cx - 28, h - 265, cx + 28, h - 205], (*skin, 255))
    # hair
    if long_hair:
        _ellipse(d, [cx - 32, h - 270, cx + 32, h - 230], (*hair, 255))
        _rect(d, [cx - 34, h - 240, cx - 22, h - 180], (*hair, 255))
        _rect(d, [cx + 22, h - 240, cx + 34, h - 180], (*hair, 255))
    else:
        _ellipse(d, [cx - 30, h - 272, cx + 30, h - 235], (*hair, 255))
    if cap:
        _rect(d, [cx - 32, h - 255, cx + 32, h - 240], (30, 30, 35, 255))
        _rect(d, [cx - 10, h - 240, cx + 34, h - 232], (30, 30, 35, 255))  # brim back
    if topi:
        # Dhaka topi — flat top with geometric pattern
        _rect(d, [cx - 30, h - 278, cx + 30, h - 252], (160, 30, 40, 255))
        for i in range(5):
            _rect(d, [cx - 26 + i * 12, h - 274, cx - 18 + i * 12, h - 256], (220, 180, 50, 255))
    if glasses:
        _rect(d, [cx - 22, h - 245, cx - 4, h - 232], (20, 20, 25, 230))
        _rect(d, [cx + 4, h - 245, cx + 22, h - 232], (20, 20, 25, 230))
        d.line([(cx - 4, h - 238), (cx + 4, h - 238)], fill=(20, 20, 25, 255), width=2)
    if scarf:
        _poly(d, [(cx + 20, h - 200), (cx + 70, h - 160), (cx + 55, h - 150), (cx + 25, h - 185)], (220, 140, 40, 255))
    if instrument == "bass":
        _rect(d, [cx - 10, h - 170, cx + 70, h - 140], (20, 20, 25, 255))
        _ellipse(d, [cx + 50, h - 185, cx + 90, h - 125], (30, 30, 35, 255))
    elif instrument == "guitar":
        _ellipse(d, [cx + 20, h - 180, cx + 75, h - 110], (180, 110, 40, 255))
        _rect(d, [cx + 45, h - 220, cx + 55, h - 150], (60, 40, 25, 255))
        _ellipse(d, [cx + 38, h - 160, cx + 58, h - 140], (30, 20, 10, 255))
    elif instrument == "tabla":
        _ellipse(d, [cx - 50, h - 100, cx - 10, h - 55], (140, 90, 50, 255))
        _ellipse(d, [cx + 10, h - 95, cx + 45, h - 55], (120, 80, 45, 255))
    elif instrument == "harmonium":
        _rect(d, [cx - 50, h - 130, cx + 55, h - 70], (90, 55, 30, 255))
        for i in range(8):
            _rect(d, [cx - 45 + i * 12, h - 125, cx - 38 + i * 12, h - 100], (240, 240, 230, 255))
    return np.array(im, dtype=np.uint8)


def make_jingle_truck(w: int = 512, h: int = 360) -> np.ndarray:
    im, d = _img(w, h)
    # chassis
    _rect(d, [30, 180, 480, 280], (30, 80, 140, 255))
    # cab
    _rect(d, [30, 100, 160, 220], (200, 40, 50, 255))
    _rect(d, [45, 110, 140, 160], (100, 160, 200, 220))
    # wooden crown
    _poly(d, [(20, 100), (90, 40), (170, 100)], (160, 100, 50, 255))
    # floral side panels
    for i in range(6):
        x = 180 + i * 48
        _ellipse(d, [x, 200, x + 40, 250], (240, 180, 40, 255))
        _ellipse(d, [x + 10, 210, x + 30, 240], (200, 40, 120, 255))
    # peacock mural
    _ellipse(d, [300, 190, 400, 270], (30, 140, 90, 255))
    _ellipse(d, [330, 200, 370, 240], (40, 60, 160, 255))
    # chains
    for x in range(180, 460, 25):
        d.line([(x, 280), (x, 310)], fill=(200, 170, 60, 255), width=2)
        _ellipse(d, [x - 4, 308, x + 4, 320], (180, 150, 50, 255))
    # wheels
    for wx in (90, 400):
        _ellipse(d, [wx - 30, 260, wx + 30, 330], (25, 25, 30, 255))
        _ellipse(d, [wx - 12, 278, wx + 12, 310], (160, 160, 165, 255))
    return np.array(im, dtype=np.uint8)


def make_pigeon(w: int = 64, h: int = 48) -> np.ndarray:
    im, d = _img(w, h)
    _ellipse(d, [10, 18, 45, 40], (140, 140, 150, 255))
    _ellipse(d, [40, 14, 58, 32], (130, 130, 140, 255))
    _poly(d, [(5, 25), (20, 10), (30, 22)], (120, 125, 140, 255))
    return np.array(im, dtype=np.uint8)


def make_gazelle(w: int = 160, h: int = 120) -> np.ndarray:
    im, d = _img(w, h)
    body = (180, 140, 90, 255)
    _ellipse(d, [30, 45, 120, 90], body)
    _ellipse(d, [110, 30, 150, 70], body)
    _rect(d, [40, 80, 50, 115], body)
    _rect(d, [100, 80, 110, 115], body)
    # horns
    d.line([(130, 30), (125, 5)], fill=(40, 30, 20, 255), width=3)
    d.line([(140, 30), (145, 5)], fill=(40, 30, 20, 255), width=3)
    return np.array(im, dtype=np.uint8)


def make_cat(w: int = 80, h: int = 60) -> np.ndarray:
    im, d = _img(w, h)
    _ellipse(d, [15, 25, 60, 55], (40, 40, 45, 255))
    _ellipse(d, [50, 15, 75, 40], (40, 40, 45, 255))
    _poly(d, [(52, 18), (55, 5), (62, 18)], (40, 40, 45, 255))
    _poly(d, [(62, 18), (70, 5), (74, 18)], (40, 40, 45, 255))
    return np.array(im, dtype=np.uint8)


def make_sadhu(w: int = 180, h: int = 260) -> np.ndarray:
    return _person(w, h, skin=(210, 170, 130), hair=(230, 230, 235), shirt=(220, 120, 40), pants=(200, 100, 30), long_hair=True)


def build_sprite_atlas() -> Dict[str, np.ndarray]:
    return {
        "vw_bus": make_vw_bus(),
        "jingle_truck": make_jingle_truck(),
        "anthony": _person(180, 280, hair=(50, 35, 25), shirt=(220, 80, 50), long_hair=True, scarf=True),
        "chad": _person(180, 280, hair=(30, 30, 30), shirt=(40, 40, 50), pants=(50, 50, 55), cap=True, instrument="tabla"),
        "flea": _person(180, 280, hair=(30, 25, 20), shirt=(240, 240, 240), pants=(30, 30, 35), instrument="bass"),
        "john": _person(180, 280, hair=(40, 30, 25), shirt=(60, 80, 100), long_hair=True, instrument="guitar"),
        "narayan": _person(
            200,
            300,
            skin=(200, 160, 120),
            hair=(25, 20, 18),
            shirt=(240, 240, 245),
            pants=(30, 30, 35),
            glasses=True,
            topi=True,
            instrument="harmonium",
        ),
        "pigeon": make_pigeon(),
        "gazelle": make_gazelle(),
        "cat": make_cat(),
        "sadhu": make_sadhu(),
    }
