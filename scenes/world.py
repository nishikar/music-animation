"""World renderer — draws every scene stage with shared GPU assets."""

from __future__ import annotations

import math
from typing import Dict

import glm
import moderngl
import numpy as np

from engine import mesh as M
from engine import shaders as S
from engine.camera import CameraUBO
from engine.config import CRAWL_TEXT
from engine.gpu import (
    BillboardGPU,
    InstancedMeshGPU,
    MeshGPU,
    compile_program,
    model_trs,
    upload_rgba,
)
from engine.mathutil import hash01, hash2
from engine.postprocess import PostParams, PostStack
from engine.sprites import build_sprite_atlas
from engine.textures import cloud_texture, crawl_text_texture, mosaic_texture, ripple_normal_map
from scenes.timeline import SceneFrame


class WorldRenderer:
    def __init__(self, ctx: moderngl.Context, width: int, height: int):
        self.ctx = ctx
        self.width = width
        self.height = height
        self.aspect = width / height

        self.cam = CameraUBO(ctx)
        self.post = PostStack(ctx, width, height)

        # Programs
        self.prog_mesh = compile_program(ctx, S.MESH_VS, S.MESH_FS)
        self.prog_inst = compile_program(ctx, S.INSTANCE_VS, S.INSTANCE_FS)
        self.prog_bill = compile_program(ctx, S.BILLBOARD_VS, S.BILLBOARD_FS)
        self.prog_sky = compile_program(ctx, S.SKY_VS, S.SKY_FS)
        self.prog_water = compile_program(ctx, S.WATER_VS, S.WATER_FS)
        self.prog_crawl = compile_program(ctx, S.CRAWL_VS, S.CRAWL_FS)

        for p in (self.prog_mesh, self.prog_inst, self.prog_bill, self.prog_sky, self.prog_water, self.prog_crawl):
            self.cam.bind_program(p)

        # Geometry — sky only needs positions
        sky_data = M.sphere(80.0, 24, 32)
        self.sky_vbo = ctx.buffer(sky_data.positions.astype(np.float32).tobytes())
        self.sky_ibo = ctx.buffer(sky_data.indices.tobytes())
        self.sky_vao = ctx.vertex_array(self.prog_sky, [(self.sky_vbo, "3f", "in_pos")], self.sky_ibo)

        self.meshes: Dict[str, MeshGPU] = {}
        self._build_static_meshes()

        self.inst_star = InstancedMeshGPU(ctx, self.prog_inst, M.star_quad())
        self.inst_flag = InstancedMeshGPU(ctx, self.prog_inst, M.prayer_flag())
        self.inst_tree = InstancedMeshGPU(ctx, self.prog_inst, M.pine_tree(5.0))
        self.inst_diya = InstancedMeshGPU(ctx, self.prog_inst, M.diya_lamp())
        self.inst_boat = InstancedMeshGPU(ctx, self.prog_inst, M.boat())
        self.inst_balloon = InstancedMeshGPU(ctx, self.prog_inst, M.hot_air_balloon())
        self.inst_chimney = InstancedMeshGPU(ctx, self.prog_inst, M.fairy_chimney())
        self.inst_lamp = InstancedMeshGPU(ctx, self.prog_inst, M.box(0.25, 0.4, 0.25, (1.0, 0.7, 0.3)))

        self._init_star_instances()
        self._init_flag_instances()
        self._init_tree_instances()
        self._init_diya_instances()
        self._init_boat_instances()
        self._init_balloon_instances()
        self._init_chimney_instances()
        self._init_lamp_instances()

        # Textures / sprites
        self.tex_normal = upload_rgba(ctx, ripple_normal_map(256))
        self.tex_mosaic = upload_rgba(ctx, mosaic_texture(256))
        self.tex_crawl = upload_rgba(ctx, crawl_text_texture(CRAWL_TEXT))
        self.tex_cloud = upload_rgba(ctx, cloud_texture(512))

        atlas = build_sprite_atlas()
        self.sprites = {k: upload_rgba(ctx, v) for k, v in atlas.items()}
        self.billboard = BillboardGPU(ctx, self.prog_bill)

        # Crawl quad
        # Crawl quad — large but within frame once perspective-tilted
        crawl_verts = np.array(
            [
                [-11.0, 0.0, 0.0, 0.0, 1.0],
                [11.0, 0.0, 0.0, 1.0, 1.0],
                [11.0, 16.0, 0.0, 1.0, 0.0],
                [-11.0, 0.0, 0.0, 0.0, 1.0],
                [11.0, 16.0, 0.0, 1.0, 0.0],
                [-11.0, 16.0, 0.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )
        self.crawl_vbo = ctx.buffer(crawl_verts.tobytes())
        self.crawl_vao = ctx.vertex_array(self.prog_crawl, [(self.crawl_vbo, "3f 2f", "in_pos", "in_uv")])

        # Water plane mesh with water program
        water = M.ground_grid(60, 48, color_a=(0.12, 0.25, 0.35), color_b=(0.1, 0.22, 0.32))
        self.water = MeshGPU(ctx, self.prog_water, water)

    def _build_static_meshes(self) -> None:
        ctx = self.ctx
        p = self.prog_mesh
        self.meshes["ground_cobble"] = MeshGPU(
            ctx, p, M.ground_grid(80, 40, color_a=(0.45, 0.42, 0.38), color_b=(0.38, 0.36, 0.32))
        )
        self.meshes["ground_grass"] = MeshGPU(
            ctx, p, M.ground_grid(100, 40, color_a=(0.22, 0.48, 0.18), color_b=(0.28, 0.55, 0.22))
        )
        self.meshes["road"] = MeshGPU(ctx, p, M.road_ribbon(90, 5.0))
        self.meshes["house"] = MeshGPU(ctx, p, M.gabled_house())
        self.meshes["bridge"] = MeshGPU(ctx, p, M.stone_arch_bridge())
        self.meshes["suspension"] = MeshGPU(ctx, p, M.suspension_bridge())
        self.meshes["iwan"] = MeshGPU(ctx, p, M.iwan_arch())
        self.meshes["dunes"] = MeshGPU(ctx, p, M.dune_terrain())
        self.meshes["canyon"] = MeshGPU(ctx, p, M.canyon_walls())
        self.meshes["ghats"] = MeshGPU(ctx, p, M.ghat_steps())
        self.meshes["pagoda"] = MeshGPU(ctx, p, M.pagoda(3, 7.0))
        self.meshes["pagoda2"] = MeshGPU(ctx, p, M.pagoda(4, 5.5))
        self.meshes["terraces"] = MeshGPU(ctx, p, M.terrace_hills())
        self.meshes["mountains"] = MeshGPU(ctx, p, M.mountain_range())
        self.meshes["pine"] = MeshGPU(ctx, p, M.pine_tree(5.5))
        self.meshes["skyline"] = MeshGPU(
            ctx,
            p,
            M.merge_meshes(
                [
                    M.transform_mesh(M.box(3, 8, 3, (0.35, 0.32, 0.3)), (x, 0, -40), 1.0)
                    for x in range(-30, 31, 8)
                ]
                + [M.transform_mesh(M.sphere(2.5, 10, 14, (0.4, 0.38, 0.36)), (x, 10, -40)) for x in (-12, 0, 14)]
                + [M.transform_mesh(M.box(0.4, 12, 0.4, (0.45, 0.4, 0.35)), (x, 6, -38)) for x in (-10, 2, 16)]
            ),
        )
        self.meshes["rooftop"] = MeshGPU(
            ctx,
            p,
            M.merge_meshes(
                [
                    M.box(14, 0.4, 14, (0.55, 0.35, 0.28), (0, -0.2, 0)),
                    M.box(0.4, 1.2, 14, (0.5, 0.3, 0.25), (-7, 0.4, 0)),
                    M.box(0.4, 1.2, 14, (0.5, 0.3, 0.25), (7, 0.4, 0)),
                    M.box(3, 0.15, 4, (0.6, 0.15, 0.15), (0, 0.05, 0)),  # rug
                ]
            ),
        )
        self.meshes["cloud_plane"] = MeshGPU(
            ctx, p, M.ground_grid(120, 24, color_a=(0.55, 0.58, 0.75), color_b=(0.5, 0.55, 0.72))
        )

    def _init_star_instances(self) -> None:
        n = 2200
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 160
            data[i, 1] = 10 + hash01(i + 3) * 70
            data[i, 2] = (hash01(i + 7) - 0.5) * 160
            data[i, 3] = 0.08 + hash01(i + 11) * 0.35
            data[i, 4:7] = (0.9 + hash01(i + 13) * 0.1, 0.9, 1.0)
            data[i, 7] = hash01(i + 17) * 6.28
            data[i, 8] = hash01(i + 19) * 6.28
        self.inst_star.set_instances(data)

    def _init_flag_instances(self) -> None:
        colors = [
            (0.15, 0.35, 0.85),
            (0.95, 0.95, 0.95),
            (0.85, 0.12, 0.12),
            (0.15, 0.65, 0.25),
            (0.9, 0.8, 0.15),
        ]
        n = 180
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            strand = i // 5
            idx = i % 5
            data[i, 0] = -20 + strand * 3.5 + idx * 0.7
            data[i, 1] = 8 + (strand % 3) * 2.5
            data[i, 2] = -10 + (strand % 7) * 4.0
            data[i, 3] = 1.2
            c = colors[idx]
            data[i, 4:7] = c
            data[i, 7] = hash01(i) * 6.28
            data[i, 8] = 0.2
        self.inst_flag.set_instances(data)

    def _init_tree_instances(self) -> None:
        n = 80
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            side = -1 if i % 2 == 0 else 1
            data[i, 0] = side * (6 + hash01(i) * 10)
            data[i, 1] = 0
            data[i, 2] = -40 + i * 1.2
            data[i, 3] = 0.8 + hash01(i + 2) * 0.6
            data[i, 4:7] = (0.9, 1.0, 0.9)
            data[i, 7] = hash01(i + 5)
            data[i, 8] = hash01(i + 8) * 6.28
        self.inst_tree.set_instances(data)

    def _init_diya_instances(self) -> None:
        n = 200
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 40
            data[i, 1] = 0.15
            data[i, 2] = (hash01(i + 9) - 0.5) * 40
            data[i, 3] = 0.8 + hash01(i + 3) * 0.5
            data[i, 4:7] = (1.0, 0.85, 0.4)
            data[i, 7] = hash01(i + 4) * 6.28
        self.inst_diya.set_instances(data)

    def _init_boat_instances(self) -> None:
        n = 28
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 35
            data[i, 1] = 0.2
            data[i, 2] = -15 + hash01(i + 2) * 35
            data[i, 3] = 1.0 + hash01(i + 6) * 0.8
            data[i, 4:7] = (1, 1, 1)
            data[i, 7] = hash01(i + 1) * 6.28
            data[i, 8] = hash01(i + 7) * 6.28
        self.inst_boat.set_instances(data)

    def _init_balloon_instances(self) -> None:
        n = 12
        data = np.zeros((n, 12), np.float32)
        palette = [
            (0.9, 0.2, 0.2),
            (0.2, 0.4, 0.9),
            (0.95, 0.7, 0.1),
            (0.2, 0.7, 0.4),
            (0.8, 0.3, 0.7),
        ]
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 50
            data[i, 1] = 8 + hash01(i + 3) * 12
            data[i, 2] = -25 - hash01(i + 5) * 30
            data[i, 3] = 1.5 + hash01(i + 2) * 1.2
            c = palette[i % len(palette)]
            data[i, 4:7] = c
            data[i, 7] = hash01(i) * 6.28
        self.inst_balloon.set_instances(data)

    def _init_chimney_instances(self) -> None:
        n = 18
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            data[i, 0] = -20 + (i % 6) * 8 + hash01(i) * 2
            data[i, 1] = 0
            data[i, 2] = -35 - (i // 6) * 10 - hash01(i + 2) * 4
            data[i, 3] = 0.8 + hash01(i + 4) * 0.8
            data[i, 4:7] = (1, 1, 1)
            data[i, 7] = hash01(i + 1)
            data[i, 8] = hash01(i + 6) * 0.5
        self.inst_chimney.set_instances(data)

    def _init_lamp_instances(self) -> None:
        n = 40
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 30
            data[i, 1] = 0.5 + hash01(i + 2) * 4
            data[i, 2] = (hash01(i + 5) - 0.5) * 30
            data[i, 3] = 0.6
            data[i, 4:7] = (1.0, 0.75, 0.35)
            data[i, 7] = hash01(i + 8) * 6.28
        self.inst_lamp.set_instances(data)

    # ------------------------------------------------------------------
    def _set_lighting(self, prog, frame: SceneFrame) -> None:
        if "u_light_dir" in prog:
            prog["u_light_dir"].value = frame.light_dir
        if "u_light_color" in prog:
            prog["u_light_color"].value = frame.light_color
        if "u_ambient" in prog:
            prog["u_ambient"].value = frame.ambient
        if "u_fog_density" in prog:
            prog["u_fog_density"].value = frame.fog_density
        if "u_fog_color" in prog:
            prog["u_fog_color"].value = frame.fog_color
        if "u_time" in prog:
            prog["u_time"].value = frame.t

    def _draw_mesh(self, name: str, frame: SceneFrame, model: bytes, emissive: float = 0.0, alpha: float = 1.0, tex=None) -> None:
        prog = self.prog_mesh
        prog["u_model"].write(model)
        self._set_lighting(prog, frame)
        prog["u_emissive"].value = emissive
        prog["u_alpha"].value = alpha
        if tex is not None:
            tex.use(0)
            prog["u_tex"] = 0
            prog["u_use_tex"].value = 1
        else:
            prog["u_use_tex"].value = 0
        self.meshes[name].render()

    def _draw_instances(self, inst: InstancedMeshGPU, frame: SceneFrame, mode: int, emissive: float = 0.0) -> None:
        prog = self.prog_inst
        self._set_lighting(prog, frame)
        prog["u_mode"].value = mode
        prog["u_emissive"].value = emissive
        prog["u_time"].value = frame.t
        inst.render()

    def _draw_sky(self, frame: SceneFrame) -> None:
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.disable(moderngl.DEPTH_TEST)
        # Prevent the sky sphere from polluting the depth buffer (xyww → depth 1).
        self.ctx.depth_mask = False
        p = self.prog_sky
        p["u_top"].value = frame.sky_top
        p["u_horizon"].value = frame.sky_horizon
        p["u_bottom"].value = frame.sky_bottom
        p["u_time"].value = frame.t
        p["u_sun_elev"].value = frame.sun_elev
        p["u_sun_color"].value = frame.sun_color
        p["u_stars"].value = 1 if frame.stars else 0
        self.sky_vao.render()
        self.ctx.depth_mask = True
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.CULL_FACE)

    def _draw_billboard(self, sprite: str, pos, size, frame: SceneFrame, sway: float = 0.0, face_cam: bool = True, yaw: float = 0.0) -> None:
        tex = self.sprites.get(sprite)
        if tex is None:
            return
        p = self.prog_bill
        tex.use(0)
        p["u_tex"] = 0
        p["u_position"].value = tuple(pos)
        p["u_size"].value = tuple(size)
        p["u_face_cam"].value = 1 if face_cam else 0
        p["u_yaw"].value = yaw
        p["u_time"].value = frame.t
        p["u_sway"].value = sway
        p["u_alpha"].value = 1.0
        p["u_tint"].value = (1.0, 1.0, 1.0)
        self.ctx.disable(moderngl.CULL_FACE)
        self.billboard.render()
        self.ctx.enable(moderngl.CULL_FACE)

    def _draw_bus(self, frame: SceneFrame) -> None:
        if not frame.bus_visible:
            return
        bp = frame.bus_pos
        # Side-profile cutout that faces the camera (readable from any dolly angle).
        self._draw_billboard(
            "vw_bus",
            (bp.x, bp.y, bp.z),
            (6.4, 3.6),
            frame,
            sway=0.0,
            face_cam=True,
        )

    def _draw_crawl(self, frame: SceneFrame) -> None:
        # Large inclined plane — starts filling most of the frame
        import glm as g
        from engine.mathutil import mat4_bytes

        m = g.mat4(1.0)
        z = 4.0 - frame.crawl_offset * 1.35
        y = -8.0 + frame.crawl_offset * 0.7
        m = g.translate(m, g.vec3(0.0, y, z))
        m = g.rotate(m, g.radians(-42.0), g.vec3(1, 0, 0))
        m = g.scale(m, g.vec3(1.15, 1.15, 1.15))
        p = self.prog_crawl
        p["u_model"].write(mat4_bytes(m))
        p["u_glow"].value = 1.0
        self.tex_crawl.use(0)
        p["u_tex"] = 0
        self.ctx.disable(moderngl.CULL_FACE)
        self.crawl_vao.render()
        self.ctx.enable(moderngl.CULL_FACE)

    def _draw_roadside_pines(self, frame: SceneFrame, bz: float) -> None:
        """Pines far from the camera path so they don't clip the lens."""
        for i in range(14):
            side = -1.0 if i % 2 == 0 else 1.0
            x = side * (11.0 + (i % 3) * 1.8)
            z = bz - 12.0 + i * 4.0
            scale = 0.7 + (i % 3) * 0.1
            self._draw_mesh("pine", frame, model_trs(x, 0.0, z, scale, scale, scale))

    def _draw_ground_strip(self, frame: SceneFrame, bz: float, mode: str = "grass") -> None:
        """Guaranteed-visible road + shoulders for travel scenes."""
        if mode == "grass":
            self._draw_mesh("ground_grass", frame, model_trs(0, -0.02, bz, 0.7, 1, 1))
        else:
            self._draw_mesh("ground_cobble", frame, model_trs(0, -0.02, bz, 0.7, 1, 1))
        self._draw_mesh("road", frame, model_trs(0, 0.05, bz, 1.15, 1, 1))
        # Shoulder strips as scaled roads tinted via separate draws aren't available —
        # use thin boxes from house-scale isn't ideal; rely on grass/cobble contrast.

    # ------------------------------------------------------------------
    def render_frame(self, frame: SceneFrame, display: bool = True) -> None:
        self.cam.update(frame.camera, self.aspect)
        self.post.begin_scene(clear_color=(*frame.sky_bottom, 1.0))

        self._draw_sky(frame)

        sid = frame.scene_id
        if sid == "crawl":
            self._draw_instances(self.inst_star, frame, mode=1, emissive=1.0)
            self._draw_crawl(frame)
            if frame.props.get("cloud_deck", 0) > 0:
                self._draw_mesh("cloud_plane", frame, model_trs(0, -5, -30, 1, 1, 1), alpha=0.85)

        elif sid == "europe":
            bz = frame.bus_pos.z
            bav = frame.props.get("bavaria", 0.0)
            if bav < 0.55:
                self._draw_ground_strip(frame, bz, mode="cobble")
                self._draw_mesh("bridge", frame, model_trs(0, 0, bz + 14, 0.9, 0.9, 0.9))
                for x in (-8.5, 8.5):
                    for row in range(5):
                        zz = bz - 10.0 + row * 6.5
                        self._draw_mesh("house", frame, model_trs(x, 0.0, zz, 0.75, 0.95, 0.75))
            if bav > 0.35:
                self._draw_ground_strip(frame, bz, mode="grass")
                self._draw_roadside_pines(frame, bz)
                self._draw_mesh("mountains", frame, model_trs(0, -2, bz - 50, 1.1, 0.8, 1.1))
            self._draw_bus(frame)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0))

        elif sid == "istanbul":
            bz = frame.bus_pos.z
            # Strait water + bridge deck reference
            self._draw_mesh("ground_cobble", frame, model_trs(0, 3.6, bz, 0.35, 1, 1.0))
            self._draw_mesh("suspension", frame, model_trs(0, 0, bz))
            self._draw_mesh("skyline", frame, model_trs(0, 0, bz - 8, 1.1, 1.1, 1.1))
            self._draw_instances(self.inst_chimney, frame, mode=0)
            self._draw_instances(self.inst_balloon, frame, mode=3, emissive=0.15)
            self._draw_bus(frame)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0))

        elif sid == "persia":
            bz = frame.bus_pos.z
            self._draw_mesh("dunes", frame, model_trs(0, 0, bz))
            self._draw_mesh("road", frame, model_trs(0, 0.35, bz, 1.1, 1, 1))
            for zoff in (10, 26, 42):
                self._draw_mesh("iwan", frame, model_trs(0, 0, bz + zoff), tex=self.tex_mosaic)
            self._draw_bus(frame)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0))

        elif sid == "khyber":
            bp = frame.bus_pos
            self._draw_mesh("canyon", frame, model_trs(bp.x * 0.15, 0, bp.z))
            self._draw_mesh("road", frame, model_trs(bp.x, 0.2, bp.z, 0.85, 1, 1, yaw=frame.bus_yaw))
            self._draw_bus(frame)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0))
            for i in range(3):
                tz = bp.z + 22 + i * 20 - (frame.t * 5.0) % 55
                self._draw_billboard(
                    "jingle_truck",
                    (bp.x - 4.0, 0.0, tz),
                    (5.2, 3.6),
                    frame,
                    face_cam=True,
                )

        elif sid == "varanasi":
            self._draw_mesh("ghats", frame, model_trs(0, 0, 5))
            self.prog_water["u_model"].write(model_trs(0, 0.0, -5, 1.2, 1, 1.2))
            self.prog_water["u_time"].value = frame.t
            self.prog_water["u_light_dir"].value = frame.light_dir
            self.prog_water["u_cam_world"].value = (frame.camera.eye.x, frame.camera.eye.y, frame.camera.eye.z)
            self.prog_water["u_fog_color"].value = frame.fog_color
            self.prog_water["u_fog_density"].value = frame.fog_density
            self.tex_normal.use(0)
            self.prog_water["u_normal_map"] = 0
            self.ctx.disable(moderngl.CULL_FACE)
            self.water.render()
            self.ctx.enable(moderngl.CULL_FACE)
            self._draw_instances(self.inst_diya, frame, mode=3, emissive=1.2)
            self._draw_instances(self.inst_boat, frame, mode=3)
            self._draw_mesh("pagoda", frame, model_trs(-12, 4, 18, 0.8, 0.8, 0.8))
            self._draw_mesh("pagoda2", frame, model_trs(14, 4, 22, 0.7, 0.7, 0.7))
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0))

        elif sid == "himalaya":
            self._draw_mesh("terraces", frame, model_trs(0, 0, 0))
            self._draw_mesh("mountains", frame, model_trs(0, 5, -40, 1.2, 1.2, 1.2))
            self._draw_mesh("suspension", frame, model_trs(0, 6, 10, 0.6, 0.6, 0.6))
            self._draw_instances(self.inst_flag, frame, mode=2)

        elif sid == "kathmandu":
            self._draw_mesh("ground_cobble", frame, model_trs(0, 0, 0))
            self._draw_mesh("pagoda", frame, model_trs(-8, 0, 12))
            self._draw_mesh("pagoda2", frame, model_trs(10, 0, 8))
            self._draw_mesh("pagoda", frame, model_trs(2, 0, 20, 0.7, 0.7, 0.7))
            for x in (-12, -4, 4, 12):
                self._draw_mesh("house", frame, model_trs(x, 0, -6, 0.7, 0.7, 0.9))
            self._draw_bus(frame)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0))

        elif sid == "rooftop":
            self._draw_mesh("rooftop", frame, model_trs(0, 0, 0))
            self._draw_mesh("pagoda", frame, model_trs(-15, -8, -20, 1.2, 1.2, 1.2))
            self._draw_mesh("pagoda2", frame, model_trs(12, -8, -18, 1.0, 1.0, 1.0))
            self._draw_mesh("mountains", frame, model_trs(0, 2, -60, 1.5, 1.3, 1.5))
            self._draw_instances(self.inst_lamp, frame, mode=3, emissive=1.5)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0))

        else:  # outro
            self._draw_mesh("mountains", frame, model_trs(0, 0, -30, 2.0, 1.8, 2.0))
            self._draw_instances(self.inst_star, frame, mode=1, emissive=1.0)
            self._draw_instances(self.inst_lamp, frame, mode=3, emissive=1.0)
            for i in range(10):
                self._draw_mesh(
                    "house",
                    frame,
                    model_trs(-20 + i * 5, 0, 10, 0.5, 0.4 + hash01(i) * 0.4, 0.5),
                    emissive=0.05,
                )

        # Post
        params = PostParams(
            grain=frame.grain,
            ca=0.0018 + frame.kaleido * 0.003,
            vignette=0.26,
            bloom_str=frame.bloom * 0.85,
            bloom_threshold=0.62,
            gate_jitter=frame.gate_jitter * 0.7,
            film_burn=frame.film_burn,
            kaleido=frame.kaleido * 0.85,
        )
        self.post.end_scene_and_post(frame.t, params, display=display)
