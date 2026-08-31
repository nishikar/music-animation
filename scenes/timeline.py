"""Scene timeline — simplified travel film as pure functions of t."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import glm

from engine.camera import CameraState
from engine.config import SCENES
from engine.mathutil import clamp, ease_in_out, lerp, lerp_vec3, orbit_pos, smoothstep


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
    stage: str
    props: Dict[str, float] = field(default_factory=dict)
    billboards: List[dict] = field(default_factory=list)
    crawl_offset: float = 0.0
    landscape: str = "europe"  # europe|bridge|desert|canyon|alpine|city|rooftop|cosmos


def scene_at(t: float) -> Tuple[str, float, float, float, float]:
    for name, a, b in SCENES:
        if a <= t < b or (name == SCENES[-1][0] and t >= a):
            local = t - a
            norm = clamp(local / max(1e-6, b - a))
            return name, local, norm, a, b
    name, a, b = SCENES[-1]
    return name, max(0.0, t - a), 1.0, a, b


def _cam(eye, target, fovy=45.0, up=(0, 1, 0)) -> CameraState:
    return CameraState(
        eye=glm.vec3(*eye) if not isinstance(eye, glm.vec3) else eye,
        target=glm.vec3(*target) if not isinstance(target, glm.vec3) else target,
        up=glm.vec3(*up),
        fovy=fovy,
    )


def _travel_cam(bus: glm.vec3, side: float = 8.5, height: float = 3.6, back: float = 7.5, fovy: float = 40.0) -> CameraState:
    """Consistent 3/4 chase camera locked to the bus."""
    return _cam(
        (bus.x + side, bus.y + height, bus.z - back),
        (bus.x, bus.y + 1.15, bus.z + 5.0),
        fovy=fovy,
    )


def _band_on_bus(bus_pos: glm.vec3, bus_yaw: float, t: float) -> List[dict]:
    c, s = math.cos(bus_yaw), math.sin(bus_yaw)

    def local(lx, ly, lz):
        return (
            bus_pos.x + lx * c + lz * s,
            bus_pos.y + ly,
            bus_pos.z - lx * s + lz * c,
        )

    hair = 0.04 * math.sin(t * 7.0)
    nod = 0.025 * math.sin(t * 4.5)
    # Roof / window seats — characters sit ON the bus body
    return [
        {"sprite": "anthony", "pos": local(1.55, 1.05 + hair, 0.35), "size": (1.2, 1.75), "sway": 0.04},
        {"sprite": "chad", "pos": local(-1.05, 1.0 + nod, 0.45), "size": (1.15, 1.7), "sway": 0.03},
        {"sprite": "john", "pos": local(0.15, 1.05, -1.55), "size": (1.15, 1.7), "sway": 0.03},
        {"sprite": "flea", "pos": local(0.05, 2.45 + nod, 0.05), "size": (1.2, 1.6), "sway": 0.05},
    ]


def evaluate_frame(t: float) -> SceneFrame:
    sid, local, norm, start, end = scene_at(t)

    sky_top = (0.35, 0.55, 0.85)
    sky_horizon = (0.85, 0.75, 0.55)
    sky_bottom = (0.4, 0.45, 0.35)
    sun_elev = 0.45
    sun_color = (1.0, 0.92, 0.75)
    light_dir = (0.4, -0.8, -0.25)
    light_color = (1.0, 0.95, 0.88)
    ambient = (0.28, 0.30, 0.34)
    fog_density = 0.08
    fog_color = sky_horizon
    stars = False
    bus_pos = glm.vec3(0, 0.06, 0)
    bus_yaw = 0.0
    bus_visible = True
    kaleido = 0.0
    film_burn = 0.0
    gate_jitter = 0.25
    bloom = 0.35
    grain = 0.035
    stage = sid
    props: Dict[str, float] = {}
    billboards: List[dict] = []
    crawl_offset = 0.0
    landscape = "europe"
    camera = _cam((0, 3, 12), (0, 1, 0))

    if sid == "crawl":
        stars = True
        bus_visible = False
        landscape = "cosmos"
        sky_top = (0.01, 0.015, 0.06)
        sky_horizon = (0.06, 0.04, 0.14)
        sky_bottom = (0.1, 0.06, 0.18)
        sun_elev = -0.35
        sun_color = (0.4, 0.28, 0.6)
        light_color = (0.35, 0.3, 0.45)
        ambient = (0.05, 0.05, 0.09)
        fog_density = 0.015
        fog_color = (0.02, 0.02, 0.05)
        bloom = 0.42
        grain = 0.028
        crawl_offset = local * 1.35
        # Frontal crawl plate — text fills frame; stars dominate the sky
        if local < 12.0:
            camera = _cam((0.0, 2.2, 9.5), (0.0, 1.0, -4.0), fovy=42)
        else:
            dive = smoothstep(12.0, 14.0, local)
            eye = glm.vec3(0.0, 2.2 - dive * 4.0, 9.5 - dive * 10.0)
            target = glm.vec3(0.0, 1.0 - dive * 8.0, -4.0 - dive * 20.0)
            camera = _cam(eye, target, fovy=lerp(42, 50, dive))
            props["cloud_deck"] = dive
            if dive > 0.35:
                u = (dive - 0.35) / 0.65
                sky_horizon = (lerp(0.08, 0.55, u), lerp(0.05, 0.62, u), lerp(0.16, 0.78, u))
                sky_top = (lerp(0.02, 0.35, u), lerp(0.02, 0.55, u), lerp(0.08, 0.85, u))
                stars = dive < 0.85

    elif sid in ("europe", "istanbul", "persia", "khyber", "varanasi", "himalaya", "kathmandu"):
        # Continuous road trip — bus always advances with global time
        trip_t = t - 14.0
        bus_z = trip_t * 1.55
        bus_y = 0.06
        bus_pos = glm.vec3(0.0, bus_y, bus_z)
        bus_yaw = 0.0
        bus_visible = True
        camera = _travel_cam(bus_pos)
        billboards = _band_on_bus(bus_pos, bus_yaw, t)
        grain = 0.028

        if sid == "europe":
            landscape = "europe" if local > 18 else "europe"
            # Amsterdam then Bavaria lighting
            bav = smoothstep(18.0, 22.0, local)
            props["bavaria"] = bav
            if bav < 0.5:
                landscape = "town"
                sky_top = (0.55, 0.66, 0.8)
                sky_horizon = (0.78, 0.8, 0.84)
                sky_bottom = (0.45, 0.48, 0.42)
                sun_elev = 0.4
                ambient = (0.34, 0.36, 0.4)
                fog_density = 0.06
            else:
                landscape = "europe"
                sky_top = (0.32, 0.55, 0.88)
                sky_horizon = (1.0, 0.78, 0.48)
                sky_bottom = (0.3, 0.48, 0.28)
                sun_elev = 0.28
                sun_color = (1.0, 0.85, 0.55)
                light_dir = (0.5, -0.55, -0.35)
                light_color = (1.0, 0.88, 0.65)
                ambient = (0.3, 0.28, 0.24)
                fog_density = 0.05
                bloom = 0.4

        elif sid == "istanbul":
            landscape = "bridge"
            bus_pos = glm.vec3(0.0, 4.05, bus_z)
            camera = _travel_cam(bus_pos, side=9.5, height=4.2, back=8.0)
            billboards = _band_on_bus(bus_pos, bus_yaw, t)
            sky_top = (0.32, 0.18, 0.38)
            sky_horizon = (0.98, 0.4, 0.18)
            sky_bottom = (0.6, 0.28, 0.22)
            sun_elev = 0.06
            sun_color = (1.0, 0.5, 0.2)
            light_dir = (0.25, -0.3, -0.9)
            light_color = (1.0, 0.6, 0.35)
            ambient = (0.28, 0.18, 0.15)
            fog_density = 0.05
            bloom = 0.5
            props["balloons"] = 1.0

        elif sid == "persia":
            landscape = "desert"
            sky_top = (0.4, 0.65, 0.92)
            sky_horizon = (0.98, 0.72, 0.42)
            sky_bottom = (0.78, 0.55, 0.35)
            sun_elev = 0.75
            light_dir = (0.35, -0.9, 0.1)
            ambient = (0.36, 0.3, 0.22)
            fog_density = 0.07
            if 12.0 < local < 26.0:
                kaleido = smoothstep(12.0, 15.0, local) * (1.0 - smoothstep(23.0, 26.0, local)) * 0.45

        elif sid == "khyber":
            landscape = "canyon"
            path = local * 0.3
            bus_x = math.sin(path * 0.7) * 1.8
            bus_yaw = math.cos(path * 0.7) * 0.28
            bus_pos = glm.vec3(bus_x, bus_y, bus_z)
            camera = _cam(
                (bus_x + 7.5, 3.8, bus_z - 8.0),
                (bus_x, 1.2, bus_z + 3.0),
                fovy=42,
            )
            billboards = _band_on_bus(bus_pos, bus_yaw, t)
            sky_top = (0.42, 0.62, 0.88)
            sky_horizon = (0.75, 0.78, 0.82)
            sky_bottom = (0.5, 0.4, 0.32)
            sun_elev = 0.7
            ambient = (0.26, 0.26, 0.28)
            fog_density = 0.06
            props["trucks"] = 1.0

        elif sid == "varanasi":
            # Treat as riverside approach — keep bus on road beside ghats
            landscape = "river"
            sky_top = (0.55, 0.42, 0.65)
            sky_horizon = (1.0, 0.72, 0.55)
            sky_bottom = (0.85, 0.58, 0.45)
            sun_elev = 0.12
            sun_color = (1.0, 0.72, 0.48)
            light_dir = (0.3, -0.35, -0.8)
            ambient = (0.32, 0.26, 0.28)
            fog_density = 0.1
            bloom = 0.55
            props["diyas"] = 1.0

        elif sid == "himalaya":
            landscape = "alpine"
            sky_top = (0.28, 0.52, 0.9)
            sky_horizon = (0.78, 0.86, 0.95)
            sky_bottom = (0.32, 0.5, 0.32)
            sun_elev = 0.6
            ambient = (0.36, 0.38, 0.42)
            fog_density = 0.04
            props["flags"] = 1.0

        else:  # kathmandu arrival
            landscape = "city"
            arrive = smoothstep(0.0, 0.4, norm)
            bus_z = lerp(bus_z - 8.0, 2.0, ease_in_out(arrive)) if False else bus_z
            # Slow to a stop near the end of the scene
            stop = smoothstep(0.55, 0.85, norm)
            speed_scale = 1.0 - 0.85 * stop
            bus_z = (t - 14.0) * 1.55 * (1.0 - 0.5 * stop) 
            # smoother: freeze near square
            if norm > 0.7:
                bus_z = lerp((245 - 14) * 1.55, 1.5, smoothstep(0.7, 0.95, norm))
            bus_pos = glm.vec3(0.0, bus_y, bus_z)
            camera = _travel_cam(bus_pos, side=7.5, height=3.2, back=7.0)
            if stop > 0.5:
                billboards = [
                    {"sprite": "anthony", "pos": (-1.8, 0.0, bus_z + 2.5), "size": (1.7, 2.6), "sway": 0.02},
                    {"sprite": "flea", "pos": (-0.3, 0.0, bus_z + 3.2), "size": (1.6, 2.45), "sway": 0.03},
                    {"sprite": "john", "pos": (1.4, 0.0, bus_z + 2.8), "size": (1.6, 2.5), "sway": 0.02},
                    {"sprite": "chad", "pos": (2.8, 0.0, bus_z + 3.5), "size": (1.65, 2.5), "sway": 0.02},
                ]
            else:
                billboards = _band_on_bus(bus_pos, bus_yaw, t)
            sky_top = (0.38, 0.52, 0.78)
            sky_horizon = (0.95, 0.7, 0.45)
            sky_bottom = (0.48, 0.38, 0.32)
            sun_elev = 0.32
            ambient = (0.3, 0.26, 0.22)
            fog_density = 0.06
            props["pagodas"] = 1.0

    elif sid == "rooftop":
        bus_visible = False
        landscape = "rooftop"
        ang = norm * math.pi * 2.0
        eye = orbit_pos((0, 1.1, 0), 6.8, ang, height=2.7)
        camera = _cam(eye, (0, 1.45, 0), fovy=40)
        sky_top = (0.04, 0.05, 0.14)
        sky_horizon = (0.35, 0.18, 0.22)
        sky_bottom = (0.18, 0.1, 0.12)
        sun_elev = -0.2
        sun_color = (1.0, 0.55, 0.22)
        light_dir = (0.15, -0.25, -0.95)
        light_color = (1.0, 0.75, 0.48)
        ambient = (0.32, 0.24, 0.2)
        fog_density = 0.03
        bloom = 0.52
        grain = 0.022
        stars = True
        props["lamps"] = 1.0
        bob = 0.03 * math.sin(t * 3.8)
        billboards = [
            {"sprite": "narayan", "pos": (0.0, 0.12 + bob, 0.0), "size": (2.25, 3.35), "sway": 0.02},
            {"sprite": "john", "pos": (-2.25, 0.12, 0.9), "size": (1.85, 2.7), "sway": 0.025},
            {"sprite": "flea", "pos": (2.35, 0.2, 0.6), "size": (1.75, 2.55), "sway": 0.03},
            {"sprite": "anthony", "pos": (-1.2, 0.12, -1.7), "size": (1.75, 2.55), "sway": 0.02},
            {"sprite": "chad", "pos": (1.4, 0.12, -1.5), "size": (1.75, 2.55), "sway": 0.025},
        ]

    else:  # outro
        bus_visible = False
        landscape = "outro"
        stars = True
        pull = ease_in_out(norm)
        eye = glm.vec3(0, lerp(5.0, 20.0, pull), lerp(18.0, 6.0, pull))
        target = glm.vec3(0, lerp(4.0, 28.0, pull), 0)
        camera = _cam(eye, target, fovy=lerp(46, 38, pull))
        sky_top = (0.04, 0.05, 0.14)
        sky_horizon = (0.22, 0.14, 0.32)
        sky_bottom = (0.1, 0.08, 0.16)
        sun_elev = -0.08
        sun_color = (0.55, 0.35, 0.5)
        light_color = (0.35, 0.28, 0.4)
        ambient = (0.1, 0.1, 0.14)
        fog_density = 0.05
        fog_color = (0.06, 0.05, 0.1)
        bloom = 0.45
        props["everest"] = 1.0
        if local >= 15.0:
            film_burn = smoothstep(15.0, 16.5, local)
        if local >= 16.5:
            film_burn = 1.0
        gate_jitter = 0.35 + film_burn * 2.0
        grain = 0.04 + film_burn * 0.15

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
        landscape=landscape,
    )
