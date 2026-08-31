"""Scene timeline — camera, lighting, and stage flags as pure functions of t."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import glm

from engine.camera import CameraState
from engine.config import SCENES
from engine.mathutil import clamp, ease_in_out, hash01, lerp, lerp_vec3, orbit_pos, remap, smoothstep


@dataclass
class SceneFrame:
    t: float
    scene_id: str
    scene_local: float
    scene_norm: float
    camera: CameraState
    sky_top: Tuple[float, float, float]
    sky_horizon: Tuple[float, float, float]
    sky_bottom: Tuple[float, float, float]
    sun_elev: float
    sun_color: Tuple[float, float, float]
    light_dir: Tuple[float, float, float]
    light_color: Tuple[float, float, float]
    ambient: Tuple[float, float, float]
    fog_density: float
    fog_color: Tuple[float, float, float]
    stars: bool
    bus_pos: glm.vec3
    bus_yaw: float
    bus_visible: bool
    kaleido: float
    film_burn: float
    gate_jitter: float
    bloom: float
    grain: float
    stage: str  # environment key
    props: Dict[str, float] = field(default_factory=dict)
    billboards: List[dict] = field(default_factory=list)
    crawl_offset: float = 0.0


def scene_at(t: float) -> Tuple[str, float, float, float, float]:
    """Return (id, local_t, norm, start, end)."""
    for name, a, b in SCENES:
        if t < b or name == SCENES[-1][0]:
            if t >= a or name == SCENES[0][0]:
                if a <= t < b or (name == SCENES[-1][0] and t >= a):
                    local = t - a
                    norm = clamp(local / max(1e-6, b - a))
                    return name, local, norm, a, b
    name, a, b = SCENES[-1]
    return name, t - a, 1.0, a, b


def _cam(eye, target, fovy=50.0, up=(0, 1, 0)) -> CameraState:
    return CameraState(
        eye=glm.vec3(*eye) if not isinstance(eye, glm.vec3) else eye,
        target=glm.vec3(*target) if not isinstance(target, glm.vec3) else target,
        up=glm.vec3(*up),
        fovy=fovy,
    )


def evaluate_frame(t: float) -> SceneFrame:
    sid, local, norm, start, end = scene_at(t)
    # defaults
    sky_top = (0.25, 0.4, 0.7)
    sky_horizon = (0.7, 0.65, 0.55)
    sky_bottom = (0.35, 0.4, 0.35)
    sun_elev = 0.55
    sun_color = (1.0, 0.92, 0.75)
    light_dir = (0.35, -0.85, -0.3)
    light_color = (1.0, 0.95, 0.85)
    ambient = (0.22, 0.24, 0.28)
    fog_density = 0.6
    fog_color = sky_horizon
    stars = False
    bus_pos = glm.vec3(0, 0.6, 0)
    bus_yaw = 0.0
    bus_visible = True
    kaleido = 0.0
    film_burn = 0.0
    gate_jitter = 0.55
    bloom = 0.4
    grain = 0.07
    stage = sid
    props: Dict[str, float] = {}
    billboards: List[dict] = []
    crawl_offset = 0.0
    camera = _cam((0, 3, 12), (0, 1, 0))

    if sid == "crawl":
        stars = True
        sky_top = (0.01, 0.01, 0.05)
        sky_horizon = (0.05, 0.04, 0.12)
        sky_bottom = (0.08, 0.1, 0.22)
        sun_elev = -0.2
        sun_color = (0.2, 0.15, 0.3)
        light_dir = (0.2, -0.5, -0.8)
        light_color = (0.4, 0.35, 0.5)
        ambient = (0.08, 0.08, 0.14)
        fog_density = 0.05
        fog_color = (0.02, 0.02, 0.06)
        bus_visible = False
        bloom = 0.55
        grain = 0.1
        # Slow scroll — text stays large on screen longer
        crawl_offset = local * 1.6
        # Classic Star Wars framing: camera above, looking down the crawl plane
        if local < 12.5:
            camera = _cam((0.0, 4.0, 8.0), (0.0, -1.0, -12.0), fovy=50)
        else:
            dive = smoothstep(12.5, 14.0, local)
            eye = glm.vec3(0.0, 4.0 - dive * 12.0, 8.0 - dive * 16.0)
            target = glm.vec3(0.0, -1.0 - dive * 18.0, -12.0 - dive * 30.0)
            camera = _cam(eye, target, fovy=lerp(50, 58, dive))
            props["cloud_deck"] = dive
            sky_bottom = (0.15, 0.18, 0.35)
            if dive > 0.5:
                sky_horizon = lerp_vec3((0.05, 0.04, 0.12), (0.55, 0.6, 0.75), (dive - 0.5) * 2)
                sky_horizon = (sky_horizon.x, sky_horizon.y, sky_horizon.z)

    elif sid == "europe":
        # Amsterdam 0-18s local, Bavaria after
        bavaria = smoothstep(18.0, 22.0, local)
        stage = "bavaria" if bavaria > 0.5 else "amsterdam"
        props["bavaria"] = bavaria
        bus_z = -20.0 + local * 1.6
        bus_pos = glm.vec3(0.0, 0.0, bus_z)
        bus_yaw = 0.0
        # 3/4 tracking shot — elevated, looking down the road for real perspective
        camera = _cam((9.0, 4.5, bus_z - 8.0), (0.0, 0.4, bus_z + 5.0), fovy=40)
        if bavaria < 0.5:
            sky_top = (0.55, 0.65, 0.78)
            sky_horizon = (0.75, 0.78, 0.82)
            sky_bottom = (0.42, 0.45, 0.40)
            sun_elev = 0.35
            light_color = (0.9, 0.92, 0.95)
            ambient = (0.35, 0.36, 0.38)
            fog_density = 0.15
            fog_color = (0.7, 0.74, 0.78)
        else:
            sky_top = (0.35, 0.55, 0.85)
            sky_horizon = (1.0, 0.78, 0.48)
            sky_bottom = (0.28, 0.42, 0.22)
            sun_elev = 0.25
            sun_color = (1.0, 0.85, 0.55)
            light_dir = (0.5, -0.6, -0.4)
            light_color = (1.0, 0.85, 0.6)
            ambient = (0.32, 0.30, 0.26)
            fog_density = 0.12
            fog_color = (0.85, 0.72, 0.52)
            bloom = 0.5
        # Bus only during travel — cutout characters read poorly at this scale
        billboards = []

    elif sid == "istanbul":
        bus_z = -15 + local * 1.4
        bus_pos = glm.vec3(0.0, 4.0, bus_z)
        bus_yaw = 0.0
        # Side-tracking along the bridge so deck + span stay in frame
        camera = _cam((10.0, 7.0, bus_z - 6.0), (0.0, 4.0, bus_z + 4.0), fovy=40)
        sky_top = (0.35, 0.2, 0.35)
        sky_horizon = (0.95, 0.35, 0.15)
        sky_bottom = (0.55, 0.25, 0.2)
        sun_elev = 0.08
        sun_color = (1.0, 0.45, 0.15)
        light_dir = (0.2, -0.25, -0.9)
        light_color = (1.0, 0.55, 0.3)
        ambient = (0.28, 0.18, 0.14)
        fog_density = 0.12
        fog_color = (0.9, 0.4, 0.25)
        bloom = 0.6
        billboards = []
        props["balloons"] = 1.0

    elif sid == "persia":
        bus_z = local * 1.5
        bus_pos = glm.vec3(0.0, 0.0, bus_z)
        # Low 3/4 looking along the road under the iwans
        camera = _cam((-5.5, 2.2, bus_z - 8.0), (0.0, 2.5, bus_z + 6.0), fovy=48)
        sky_top = (0.45, 0.65, 0.9)
        sky_horizon = (0.95, 0.7, 0.4)
        sky_bottom = (0.75, 0.5, 0.3)
        sun_elev = 0.7
        light_dir = (0.4, -0.9, 0.1)
        light_color = (1.0, 0.9, 0.7)
        ambient = (0.38, 0.32, 0.24)
        fog_density = 0.18
        fog_color = (0.85, 0.65, 0.4)
        if 12.0 < local < 28.0:
            kaleido = smoothstep(12.0, 16.0, local) * (1.0 - smoothstep(24.0, 28.0, local)) * 0.65
        billboards = []
        props["heat_haze"] = 0.5 + 0.5 * math.sin(t * 2.0)

    elif sid == "khyber":
        path_t = local * 0.35
        bus_x = math.sin(path_t * 0.8) * 3.0
        bus_z = path_t * 4.0
        bus_yaw = math.cos(path_t * 0.8) * 0.45
        bus_pos = glm.vec3(bus_x, 0.0, bus_z)
        cam_x = math.sin(path_t * 0.8 - 0.35) * 3.0
        cam_z = bus_z - 9.0
        camera = _cam((cam_x + 4.0, 4.0, cam_z), (bus_x, 1.2, bus_z + 3.0), fovy=45)
        sky_top = (0.4, 0.6, 0.85)
        sky_horizon = (0.7, 0.75, 0.8)
        sky_bottom = (0.45, 0.35, 0.28)
        sun_elev = 0.8
        light_dir = (0.6, -0.7, -0.2)
        light_color = (1.0, 0.95, 0.8)
        ambient = (0.25, 0.25, 0.26)
        fog_density = 0.12
        fog_color = (0.55, 0.5, 0.45)
        grain = 0.09
        billboards = []
        props["trucks"] = 1.0
        props["dust"] = 1.0

    elif sid == "varanasi":
        bus_visible = False
        rise = smoothstep(0.0, 1.0, norm)
        eye_y = lerp(2.0, 7.0, ease_in_out(rise))
        eye_z = -8 + local * 0.9
        camera = _cam((5.0, eye_y, eye_z), (0.0, 1.5 + rise * 2.0, eye_z + 10.0), fovy=48)
        sky_top = (0.55, 0.45, 0.65)
        sky_horizon = (1.0, 0.7, 0.55)
        sky_bottom = (0.85, 0.55, 0.45)
        sun_elev = 0.12
        sun_color = (1.0, 0.7, 0.45)
        light_dir = (0.3, -0.3, -0.8)
        light_color = (1.0, 0.75, 0.55)
        ambient = (0.32, 0.25, 0.26)
        fog_density = 0.25
        fog_color = (0.9, 0.65, 0.55)
        bloom = 0.65
        props["diyas"] = 1.0
        props["boats"] = 1.0
        props["ghats"] = 1.0
        billboards = [
            {"sprite": "chad", "pos": (3.5, 2.2, 8.0), "size": (2.0, 3.0), "sway": 0.02},
            {"sprite": "sadhu", "pos": (-2.5, 2.8, 11.0), "size": (1.7, 2.5), "sway": 0.01},
        ]

    elif sid == "himalaya":
        bus_visible = False
        ang = norm * math.pi * 1.2
        radius = 28.0 - norm * 8.0
        eye = orbit_pos((0, 6, 5), radius, ang, height=12.0 - math.sin(norm * math.pi) * 5.0)
        camera = _cam(eye, (0, 4, 8), fovy=50)
        sky_top = (0.3, 0.55, 0.9)
        sky_horizon = (0.75, 0.85, 0.95)
        sky_bottom = (0.35, 0.55, 0.35)
        sun_elev = 0.65
        light_color = (1.0, 0.98, 0.95)
        ambient = (0.38, 0.40, 0.44)
        fog_density = 0.1
        fog_color = (0.8, 0.85, 0.9)
        bloom = 0.45
        props["flags"] = 1.0
        props["bridges"] = 1.0

    elif sid == "kathmandu":
        arrive = smoothstep(0.0, 0.35, norm)
        bus_z = lerp(-20.0, 2.0, ease_in_out(min(1.0, arrive * 1.2)))
        stopped = norm > 0.35
        bus_pos = glm.vec3(0.0, 0.0, bus_z)
        bus_visible = True
        camera = _cam((8.0 - norm * 2.0, 3.5, bus_z - 9.0 + norm * 8.0), (0, 2.0, 4.0), fovy=44)
        sky_top = (0.4, 0.55, 0.8)
        sky_horizon = (0.95, 0.7, 0.45)
        sky_bottom = (0.45, 0.35, 0.3)
        sun_elev = 0.3
        sun_color = (1.0, 0.8, 0.5)
        light_dir = (0.45, -0.55, -0.5)
        light_color = (1.0, 0.85, 0.6)
        ambient = (0.30, 0.26, 0.22)
        fog_density = 0.15
        fog_color = (0.75, 0.6, 0.45)
        props["pagodas"] = 1.0
        props["steam"] = 1.0 if stopped else 0.0
        if stopped:
            step = smoothstep(0.35, 0.55, norm)
            billboards = [
                {"sprite": "anthony", "pos": (-2.0 * step, 0.0, 3.0), "size": (1.8, 2.8), "sway": 0.02},
                {"sprite": "flea", "pos": (-0.5 * step, 0.0, 4.0), "size": (1.7, 2.6), "sway": 0.03},
                {"sprite": "john", "pos": (1.5 * step, 0.0, 3.5), "size": (1.7, 2.7), "sway": 0.02},
                {"sprite": "chad", "pos": (3.0 * step, 0.0, 4.5), "size": (1.8, 2.7), "sway": 0.02},
            ]
        else:
            billboards = []

    elif sid == "rooftop":
        bus_visible = False
        ang = norm * math.pi * 2.0
        eye = orbit_pos((0, 1.0, 0), 7.5, ang, height=3.2)
        camera = _cam(eye, (0, 1.3, 0), fovy=42)
        sky_top = (0.35, 0.4, 0.7)
        sky_horizon = (1.0, 0.55, 0.25)
        sky_bottom = (0.55, 0.35, 0.25)
        sun_elev = 0.05
        sun_color = (1.0, 0.55, 0.2)
        light_dir = (0.1, -0.2, -0.95)
        light_color = (1.0, 0.7, 0.4)
        ambient = (0.28, 0.20, 0.16)
        fog_density = 0.1
        fog_color = (0.9, 0.55, 0.35)
        bloom = 0.75
        grain = 0.06
        props["rooftop"] = 1.0
        props["lamps"] = 1.0
        bob = 0.04 * math.sin(t * 4.0)
        billboards = [
            {"sprite": "narayan", "pos": (0.0, 0.0 + bob, 0.0), "size": (2.0, 2.9), "sway": 0.03},
            {"sprite": "john", "pos": (-2.2, 0.0, 0.8), "size": (1.7, 2.5), "sway": 0.04},
            {"sprite": "flea", "pos": (2.3, 0.15, 0.5), "size": (1.6, 2.4), "sway": 0.05},
            {"sprite": "anthony", "pos": (-1.2, 0.0, -1.8), "size": (1.6, 2.4), "sway": 0.02},
            {"sprite": "chad", "pos": (1.4, 0.0, -1.6), "size": (1.6, 2.4), "sway": 0.04},
        ]

    else:  # outro
        bus_visible = False
        pull = ease_in_out(norm)
        eye = glm.vec3(0, lerp(5.0, 22.0, pull), lerp(22.0, 6.0, pull))
        target = glm.vec3(0, lerp(5.0, 35.0, pull), 0)
        camera = _cam(eye, target, fovy=lerp(48, 38, pull))
        sky_top = (0.05, 0.05, 0.15)
        sky_horizon = (0.25, 0.15, 0.35)
        sky_bottom = (0.1, 0.08, 0.18)
        sun_elev = -0.05
        sun_color = (0.6, 0.35, 0.5)
        light_color = (0.4, 0.3, 0.45)
        ambient = (0.1, 0.1, 0.16)
        fog_density = 0.1
        fog_color = (0.08, 0.06, 0.12)
        stars = True
        bloom = 0.5
        props["everest"] = 1.0
        props["lanterns"] = 1.0
        if local >= 15.0:
            film_burn = smoothstep(15.0, 16.5, local)
        if local >= 16.5:
            film_burn = 1.0
        gate_jitter = 0.6 + film_burn * 2.5
        grain = 0.08 + film_burn * 0.2

    return SceneFrame(
        t=t,
        scene_id=sid,
        scene_local=local,
        scene_norm=norm,
        camera=camera,
        sky_top=sky_top,
        sky_horizon=tuple(sky_horizon) if not isinstance(sky_horizon, tuple) else sky_horizon,
        sky_bottom=sky_bottom,
        sun_elev=sun_elev,
        sun_color=sun_color,
        light_dir=light_dir,
        light_color=light_color,
        ambient=ambient,
        fog_density=fog_density,
        fog_color=tuple(fog_color) if not isinstance(fog_color, tuple) else fog_color,
        stars=stars,
        bus_pos=bus_pos,
        bus_yaw=bus_yaw,
        bus_visible=bus_visible,
        kaleido=kaleido,
        film_burn=film_burn,
        gate_jitter=gate_jitter,
        bloom=bloom,
        grain=grain,
        stage=stage,
        props=props,
        billboards=billboards,
        crawl_offset=crawl_offset,
    )


def _band_on_bus(bus_pos: glm.vec3, bus_yaw: float, t: float, mode: str) -> List[dict]:
    """Place band members relative to the VW bus."""
    c, s = math.cos(bus_yaw), math.sin(bus_yaw)

    def local(lx, ly, lz):
        return (bus_pos.x + lx * c + lz * s, bus_pos.y + ly, bus_pos.z - lx * s + lz * c)

    hair = 0.05 * math.sin(t * 8.0)
    nod = 0.03 * math.sin(t * 5.0)
    out = [
        {"sprite": "anthony", "pos": local(1.4, 0.9 + hair, 0.3), "size": (1.3, 1.9), "sway": 0.06},
        {"sprite": "chad", "pos": local(-0.9, 0.85 + nod, 0.5), "size": (1.2, 1.8), "sway": 0.04},
        {"sprite": "john", "pos": local(0.2, 0.9, -1.6), "size": (1.2, 1.8), "sway": 0.03},
    ]
    if mode in ("travel", "sunglasses", "desert", "khyber"):
        out.append({"sprite": "flea", "pos": local(0.0, 2.3 + nod, 0.0), "size": (1.3, 1.7), "sway": 0.08})
    if mode == "desert":
        out[2] = {"sprite": "john", "pos": local(0.1, 2.2, 0.2), "size": (1.4, 1.9), "sway": 0.05}
    if mode == "khyber":
        out[0]["sway"] = 0.1
    return out
