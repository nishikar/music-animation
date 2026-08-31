"""World renderer — advanced SDF raymarcher landscapes + sprite overlays."""

from __future__ import annotations

import math
from typing import Dict

import moderngl
import numpy as np

from engine import shaders as S
from engine.camera import CameraUBO
from engine.config import CRAWL_TEXT
from engine.gpu import BillboardGPU, compile_program, upload_rgba
from engine.postprocess import PostParams, PostStack
from engine.raymarch import RAYMARCH_FS, RAYMARCH_VS
from engine.sprites import build_sprite_atlas
from engine.textures import crawl_text_texture
from scenes.timeline import SceneFrame

# landscape string → shader mode
_LAND_MODE = {
    "cosmos": 0,
    "town": 1,
    "europe": 2,
    "bridge": 3,
    "desert": 4,
    "canyon": 5,
    "river": 6,
    "alpine": 7,
    "city": 8,
    "rooftop": 9,
    "outro": 10,
}


def _setu(prog, name, value) -> None:
    if name in prog:
        prog[name].value = value


class WorldRenderer:
    def __init__(self, ctx: moderngl.Context, width: int, height: int):
        self.ctx = ctx
        self.width = width
        self.height = height
        self.aspect = width / max(height, 1)

        self.cam = CameraUBO(ctx)
        self.post = PostStack(ctx, width, height)

        self.prog_rm = compile_program(ctx, RAYMARCH_VS, RAYMARCH_FS)
        self.vao_rm = ctx.vertex_array(self.prog_rm, [])

        self.prog_bill = compile_program(ctx, S.BILLBOARD_VS, S.BILLBOARD_FS)
        self.cam.bind_program(self.prog_bill)
        self.billboard = BillboardGPU(ctx, self.prog_bill)

        self.prog_crawl = compile_program(ctx, S.CRAWL_VS, S.CRAWL_FS)
        self.cam.bind_program(self.prog_crawl)
        crawl_verts = np.array(
            [
                [-10.5, 0.0, 0.0, 0.0, 1.0],
                [10.5, 0.0, 0.0, 1.0, 1.0],
                [10.5, 15.0, 0.0, 1.0, 0.0],
                [-10.5, 0.0, 0.0, 0.0, 1.0],
                [10.5, 15.0, 0.0, 1.0, 0.0],
                [-10.5, 15.0, 0.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )
        self.crawl_vbo = ctx.buffer(crawl_verts.tobytes())
        self.crawl_vao = ctx.vertex_array(self.prog_crawl, [(self.crawl_vbo, "3f 2f", "in_pos", "in_uv")])

        self.tex_crawl = upload_rgba(ctx, crawl_text_texture(CRAWL_TEXT))
        atlas = build_sprite_atlas()
        self.sprites: Dict[str, moderngl.Texture] = {k: upload_rgba(ctx, v) for k, v in atlas.items()}

    def _draw_raymarch(self, frame: SceneFrame) -> None:
        cam = frame.camera
        eye = cam.eye
        target = cam.target
        up = cam.up
        mode = _LAND_MODE.get(frame.landscape, 2)
        if frame.scene_id == "crawl":
            mode = 0

        p = self.prog_rm
        _setu(p, "u_resolution", (float(self.width), float(self.height)))
        _setu(p, "u_time", float(frame.t))
        _setu(p, "u_cam_pos", (float(eye.x), float(eye.y), float(eye.z)))
        _setu(p, "u_cam_target", (float(target.x), float(target.y), float(target.z)))
        _setu(p, "u_cam_up", (float(up.x), float(up.y), float(up.z)))
        _setu(p, "u_fovy", float(cam.fovy))
        _setu(p, "u_near", float(cam.near))
        _setu(p, "u_far", float(cam.far))
        _setu(p, "u_landscape", int(mode))
        _setu(p, "u_bus_z", float(frame.bus_pos.z))
        _setu(p, "u_stars", 1 if frame.stars else 0)
        _setu(p, "u_sun_elev", float(frame.sun_elev))
        _setu(p, "u_sky_top", tuple(float(x) for x in frame.sky_top))
        _setu(p, "u_sky_horizon", tuple(float(x) for x in frame.sky_horizon))
        _setu(p, "u_sky_bottom", tuple(float(x) for x in frame.sky_bottom))
        _setu(p, "u_sun_color", tuple(float(x) for x in frame.sun_color))
        _setu(p, "u_light_dir", tuple(float(x) for x in frame.light_dir))
        _setu(p, "u_light_color", tuple(float(x) for x in frame.light_color))
        _setu(p, "u_ambient", tuple(float(x) for x in frame.ambient))
        _setu(p, "u_fog_density", float(frame.fog_density))
        _setu(p, "u_fog_color", tuple(float(x) for x in frame.fog_color))

        self.ctx.disable(moderngl.BLEND)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.vao_rm.render(moderngl.TRIANGLES, vertices=3)

    def _draw_billboard(
        self,
        name: str,
        pos,
        size,
        frame: SceneFrame,
        sway: float = 0.0,
        face_cam: bool = True,
        yaw: float = 0.0,
        alpha: float = 1.0,
    ) -> None:
        tex = self.sprites.get(name)
        if tex is None:
            return
        if hasattr(pos, "x"):
            px, py, pz = float(pos.x), float(pos.y), float(pos.z)
        else:
            px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])
        p = self.prog_bill
        _setu(p, "u_position", (px, py, pz))
        _setu(p, "u_size", (float(size[0]), float(size[1])),)
        _setu(p, "u_yaw", float(yaw))
        _setu(p, "u_face_cam", 1 if face_cam else 0)
        _setu(p, "u_time", float(frame.t))
        _setu(p, "u_sway", float(sway))
        _setu(p, "u_alpha", float(alpha))
        _setu(p, "u_tint", (1.0, 1.0, 1.0))
        tex.use(0)
        _setu(p, "u_tex", 0)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        # Sprites always composite over the raymarched plate (avoid depth fights / cull)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)
        self.billboard.render()
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.CULL_FACE)

    def _draw_bus(self, frame: SceneFrame) -> None:
        if not frame.bus_visible:
            return
        bp = frame.bus_pos
        self._draw_billboard(
            "vw_bus",
            (bp.x, bp.y, bp.z),
            (5.4, 3.1),
            frame,
            face_cam=False,
            yaw=math.pi * 0.5,
        )

    def _draw_oncoming_trucks(self, frame: SceneFrame, bz: float) -> None:
        for i in range(6):
            cycle = 70.0
            tz = bz + 8.0 + ((i * 12.0) - (frame.t * 22.0)) % cycle
            # Keep clear of the hero bus so sprites do not stack
            if tz < bz + 14.0:
                continue
            self._draw_billboard(
                "jingle_truck",
                (-3.15, 0.06, tz),
                (5.9, 3.9),
                frame,
                face_cam=False,
                yaw=-math.pi * 0.5,
            )

    def _draw_crawl(self, frame: SceneFrame) -> None:
        # Star Wars crawl plate drifting up / into distance
        y = -2.0 + frame.crawl_offset * 0.85
        z = -6.0 - frame.crawl_offset * 0.35
        pitch = -0.95
        import glm
        from engine.mathutil import mat4_bytes

        m = glm.translate(glm.mat4(1.0), glm.vec3(0.0, y, z))
        m = glm.rotate(m, pitch, glm.vec3(1, 0, 0))
        p = self.prog_crawl
        if "u_model" in p:
            p["u_model"].write(mat4_bytes(m))
        _setu(p, "u_glow", 0.55)
        self.tex_crawl.use(0)
        _setu(p, "u_tex", 0)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)
        self.crawl_vao.render()
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.CULL_FACE)

    def render_frame(self, frame: SceneFrame, display: bool = True) -> None:
        self.cam.update(frame.camera, self.aspect)
        self.post.begin_scene(clear_color=(*frame.sky_bottom, 1.0))

        self._draw_raymarch(frame)

        if frame.landscape == "cosmos" or frame.scene_id == "crawl":
            self._draw_crawl(frame)
        elif frame.landscape == "rooftop":
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0.0))
        elif frame.landscape == "outro":
            pass
        else:
            if frame.landscape == "canyon" and frame.props.get("trucks"):
                self._draw_oncoming_trucks(frame, frame.bus_pos.z)
            self._draw_bus(frame)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0.0))

        params = PostParams(
            grain=frame.grain,
            ca=0.0008 + frame.kaleido * 0.0015,
            vignette=0.18,
            bloom_str=frame.bloom,
            bloom_threshold=0.72,
            gate_jitter=frame.gate_jitter,
            film_burn=frame.film_burn,
            kaleido=frame.kaleido,
        )
        self.post.end_scene_and_post(frame.t, params, display=display)
