"""World renderer — simplified production travel film."""

from __future__ import annotations

import math
from typing import Dict

import moderngl
import numpy as np

from engine import mesh as M
from engine import shaders as S
from engine.camera import CameraUBO
from engine.config import CRAWL_TEXT
from engine.gpu import BillboardGPU, InstancedMeshGPU, MeshGPU, compile_program, model_trs, upload_rgba
from engine.mathutil import hash01
from engine.postprocess import PostParams, PostStack
from engine.sprites import build_sprite_atlas
from engine.textures import crawl_text_texture, mosaic_texture, ripple_normal_map
from scenes.timeline import SceneFrame


class WorldRenderer:
    def __init__(self, ctx: moderngl.Context, width: int, height: int):
        self.ctx = ctx
        self.width = width
        self.height = height
        self.aspect = width / max(height, 1)

        self.cam = CameraUBO(ctx)
        self.post = PostStack(ctx, width, height)

        self.prog_mesh = compile_program(ctx, S.MESH_VS, S.MESH_FS)
        self.prog_inst = compile_program(ctx, S.INSTANCE_VS, S.INSTANCE_FS)
        self.prog_bill = compile_program(ctx, S.BILLBOARD_VS, S.BILLBOARD_FS)
        self.prog_sky = compile_program(ctx, S.SKY_VS, S.SKY_FS)
        self.prog_water = compile_program(ctx, S.WATER_VS, S.WATER_FS)
        self.prog_crawl = compile_program(ctx, S.CRAWL_VS, S.CRAWL_FS)

        for p in (self.prog_mesh, self.prog_inst, self.prog_bill, self.prog_sky, self.prog_water, self.prog_crawl):
            self.cam.bind_program(p)

        sky_data = M.sphere(90.0, 28, 36)
        self.sky_vbo = ctx.buffer(sky_data.positions.astype(np.float32).tobytes())
        self.sky_ibo = ctx.buffer(sky_data.indices.tobytes())
        self.sky_vao = ctx.vertex_array(self.prog_sky, [(self.sky_vbo, "3f", "in_pos")], self.sky_ibo)

        self.meshes: Dict[str, MeshGPU] = {}
        self._build_static_meshes()

        self.inst_star = InstancedMeshGPU(ctx, self.prog_inst, M.star_quad())
        self.inst_flag = InstancedMeshGPU(ctx, self.prog_inst, M.prayer_flag())
        self.inst_diya = InstancedMeshGPU(ctx, self.prog_inst, M.diya_lamp())
        self.inst_boat = InstancedMeshGPU(ctx, self.prog_inst, M.boat())
        self.inst_balloon = InstancedMeshGPU(ctx, self.prog_inst, M.hot_air_balloon())
        self.inst_lamp = InstancedMeshGPU(ctx, self.prog_inst, M.box(0.22, 0.35, 0.22, (1.0, 0.75, 0.35)))

        self._init_star_instances()
        self._init_flag_instances()
        self._init_diya_instances()
        self._init_boat_instances()
        self._init_balloon_instances()
        self._init_lamp_instances()

        self.tex_normal = upload_rgba(ctx, ripple_normal_map(256))
        self.tex_mosaic = upload_rgba(ctx, mosaic_texture(256))
        self.tex_crawl = upload_rgba(ctx, crawl_text_texture(CRAWL_TEXT))
        atlas = build_sprite_atlas()
        self.sprites = {k: upload_rgba(ctx, v) for k, v in atlas.items()}
        self.billboard = BillboardGPU(ctx, self.prog_bill)

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

        water = M.ground_grid(70, 56, color_a=(0.12, 0.28, 0.38), color_b=(0.1, 0.24, 0.34))
        self.water = MeshGPU(ctx, self.prog_water, water)

    def _build_static_meshes(self) -> None:
        ctx, p = self.ctx, self.prog_mesh
        self.meshes["europe"] = MeshGPU(ctx, p, M.europe_hills())
        self.meshes["desert"] = MeshGPU(ctx, p, M.dune_terrain())
        self.meshes["canyon"] = MeshGPU(ctx, p, M.canyon_walls())
        self.meshes["alpine"] = MeshGPU(ctx, p, M.terrace_hills())
        self.meshes["cobble"] = MeshGPU(
            ctx, p, M.ground_grid(90, 72, color_a=(0.42, 0.38, 0.34), color_b=(0.36, 0.33, 0.3))
        )
        self.meshes["road"] = MeshGPU(ctx, p, M.road_ribbon(100, 5.4))
        self.meshes["house"] = MeshGPU(ctx, p, M.gabled_house())
        self.meshes["bridge_stone"] = MeshGPU(ctx, p, M.stone_arch_bridge())
        self.meshes["suspension"] = MeshGPU(ctx, p, M.suspension_bridge())
        self.meshes["iwan"] = MeshGPU(ctx, p, M.iwan_arch())
        self.meshes["pagoda"] = MeshGPU(ctx, p, M.pagoda(3, 7.0))
        self.meshes["pagoda2"] = MeshGPU(ctx, p, M.pagoda(4, 5.8))
        self.meshes["mountains"] = MeshGPU(ctx, p, M.mountain_range(140, peaks=8))
        self.meshes["pine"] = MeshGPU(ctx, p, M.pine_tree(6.2))
        self.meshes["pine2"] = MeshGPU(ctx, p, M.pine_tree(5.2, color=(0.1, 0.26, 0.12)))
        self.meshes["deciduous"] = MeshGPU(ctx, p, M.deciduous_tree(5.8))
        self.meshes["deciduous2"] = MeshGPU(ctx, p, M.deciduous_tree(4.6, color=(0.28, 0.45, 0.16)))
        self.meshes["ghats"] = MeshGPU(ctx, p, M.ghat_steps())
        self.meshes["rooftop"] = MeshGPU(
            ctx,
            p,
            M.merge_meshes(
                [
                    M.box(18, 0.4, 18, (0.48, 0.32, 0.24), (0, -0.18, 0)),
                    M.box(0.4, 1.2, 18, (0.42, 0.28, 0.22), (-9, 0.45, 0)),
                    M.box(0.4, 1.2, 18, (0.42, 0.28, 0.22), (9, 0.45, 0)),
                    M.box(0.4, 1.2, 18, (0.42, 0.28, 0.22), (0, 0.45, -9)),
                    M.box(5.2, 0.1, 6.0, (0.55, 0.12, 0.14), (0, 0.06, 0)),
                    M.box(1.4, 0.55, 1.4, (0.55, 0.4, 0.2), (-4.0, 0.32, -4.0)),
                    M.box(1.0, 0.7, 1.0, (0.5, 0.36, 0.22), (4.2, 0.4, -3.5)),
                    # clay pots / detail
                    M.transform_mesh(M.sphere(0.35, 8, 10, (0.55, 0.3, 0.18)), (3.5, 0.35, 3.2)),
                    M.transform_mesh(M.sphere(0.28, 8, 10, (0.5, 0.28, 0.16)), (4.1, 0.3, 3.5)),
                ]
            ),
        )
        self.meshes["skyline"] = MeshGPU(
            ctx,
            p,
            M.merge_meshes(
                [M.transform_mesh(M.box(2.8, 7 + (i % 3), 2.8, (0.38, 0.34, 0.32)), (x, 0, -42)) for i, x in enumerate(range(-28, 29, 7))]
                + [M.transform_mesh(M.sphere(2.2, 10, 14, (0.42, 0.38, 0.35)), (x, 9, -42)) for x in (-14, 0, 16)]
                + [M.transform_mesh(M.box(0.35, 11, 0.35, (0.5, 0.45, 0.38)), (x, 5.5, -40)) for x in (-12, 2, 18)]
                # Kathmandu rooftop silhouette — denser midrise cluster
                + [
                    M.transform_mesh(
                        M.box(2.2 + (i % 3) * 0.4, 4.5 + (i % 4) * 1.3, 2.2, (0.4 + 0.02 * (i % 3), 0.32, 0.28)),
                        (-20 + i * 3.5, 0, -30 - (i % 2) * 4),
                    )
                    for i in range(12)
                ]
            ),
        )

    def _init_star_instances(self) -> None:
        n = 2200
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            u, v = hash01(i), hash01(i + 3)
            theta = u * math.pi * 2
            phi = math.acos(max(-1.0, min(1.0, 1.0 - v * 0.95)))
            r = 62 + hash01(i + 5) * 28
            data[i, 0] = r * math.sin(phi) * math.cos(theta)
            data[i, 1] = abs(r * math.cos(phi)) + 6
            data[i, 2] = r * math.sin(phi) * math.sin(theta)
            tier = hash01(i + 7)
            if tier > 0.97:
                data[i, 3] = 0.55 + hash01(i + 9) * 0.35
            elif tier > 0.75:
                data[i, 3] = 0.22 + hash01(i + 9) * 0.2
            else:
                data[i, 3] = 0.08 + hash01(i + 9) * 0.12
            warm = hash01(i + 11)
            data[i, 4:7] = (0.85 + 0.15 * warm, 0.9 + 0.08 * (1 - warm), 1.0)
            data[i, 7] = hash01(i + 13) * 6.28
            data[i, 8] = hash01(i + 15) * 6.28
        self.inst_star.set_instances(data)

    def _init_flag_instances(self) -> None:
        colors = [(0.15, 0.35, 0.85), (0.95, 0.95, 0.95), (0.85, 0.12, 0.12), (0.15, 0.65, 0.25), (0.9, 0.8, 0.15)]
        n = 160
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            strand, idx = i // 5, i % 5
            data[i, 0] = -18 + strand * 3.2 + idx * 0.65
            data[i, 1] = 7 + (strand % 3) * 2.2
            data[i, 2] = -8 + (strand % 6) * 3.5
            data[i, 3] = 1.15
            data[i, 4:7] = colors[idx]
            data[i, 7] = hash01(i) * 6.28
            data[i, 8] = 0.15
        self.inst_flag.set_instances(data)

    def _init_diya_instances(self) -> None:
        n = 160
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 36
            data[i, 1] = 0.2
            data[i, 2] = (hash01(i + 8) - 0.5) * 36
            data[i, 3] = 0.9 + hash01(i + 2) * 0.4
            data[i, 4:7] = (1.0, 0.85, 0.4)
            data[i, 7] = hash01(i + 4) * 6.28
        self.inst_diya.set_instances(data)

    def _init_boat_instances(self) -> None:
        n = 22
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 30
            data[i, 1] = 0.25
            data[i, 2] = -12 + hash01(i + 2) * 30
            data[i, 3] = 1.0 + hash01(i + 5) * 0.7
            data[i, 4:7] = (1, 1, 1)
            data[i, 7] = hash01(i + 1) * 6.28
            data[i, 8] = hash01(i + 6) * 6.28
        self.inst_boat.set_instances(data)

    def _init_balloon_instances(self) -> None:
        n = 10
        data = np.zeros((n, 12), np.float32)
        palette = [(0.9, 0.25, 0.2), (0.2, 0.4, 0.9), (0.95, 0.7, 0.15), (0.2, 0.7, 0.4), (0.8, 0.35, 0.7)]
        for i in range(n):
            data[i, 0] = (hash01(i) - 0.5) * 45
            data[i, 1] = 10 + hash01(i + 2) * 10
            data[i, 2] = -20 - hash01(i + 4) * 25
            data[i, 3] = 1.4 + hash01(i + 1) * 1.0
            data[i, 4:7] = palette[i % len(palette)]
            data[i, 7] = hash01(i) * 6.28
        self.inst_balloon.set_instances(data)

    def _init_lamp_instances(self) -> None:
        n = 28
        data = np.zeros((n, 12), np.float32)
        for i in range(n):
            ang = i / n * math.pi * 2
            data[i, 0] = math.cos(ang) * (3.5 + (i % 3))
            data[i, 1] = 0.35
            data[i, 2] = math.sin(ang) * (3.5 + (i % 3))
            data[i, 3] = 0.7
            data[i, 4:7] = (1.0, 0.78, 0.4)
            data[i, 7] = hash01(i) * 6.28
        self.inst_lamp.set_instances(data)

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
        if mode == 1:
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE
            self.ctx.disable(moderngl.DEPTH_TEST)
            inst.render()
            self.ctx.enable(moderngl.DEPTH_TEST)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            self.ctx.disable(moderngl.BLEND)
        else:
            inst.render()

    def _draw_sky(self, frame: SceneFrame) -> None:
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.disable(moderngl.DEPTH_TEST)
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
        p["u_position"].value = tuple(float(x) for x in pos)
        p["u_size"].value = tuple(size)
        p["u_face_cam"].value = 1 if face_cam else 0
        p["u_yaw"].value = yaw
        p["u_time"].value = frame.t
        p["u_sway"].value = sway
        p["u_alpha"].value = 1.0
        p["u_tint"].value = (1.0, 1.0, 1.0)
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.billboard.render()
        self.ctx.disable(moderngl.BLEND)
        self.ctx.enable(moderngl.CULL_FACE)

    def _draw_bus(self, frame: SceneFrame) -> None:
        if not frame.bus_visible:
            return
        bp = frame.bus_pos
        # Fixed yaw along the road — never camera-face (avoids stretch/clip)
        self._draw_billboard(
            "vw_bus",
            (bp.x, bp.y, bp.z),
            (7.2, 4.05),
            frame,
            sway=0.0,
            face_cam=False,
            yaw=frame.bus_yaw + math.pi * 0.5,
        )

    def _draw_crawl(self, frame: SceneFrame) -> None:
        import glm as g
        from engine.mathutil import mat4_bytes

        m = g.mat4(1.0)
        z = 1.5 - frame.crawl_offset * 0.95
        y = -5.5 + frame.crawl_offset * 0.55
        m = g.translate(m, g.vec3(0.0, y, z))
        m = g.rotate(m, g.radians(-32.0), g.vec3(1, 0, 0))
        m = g.scale(m, g.vec3(1.35, 1.35, 1.35))
        p = self.prog_crawl
        p["u_model"].write(mat4_bytes(m))
        p["u_glow"].value = 1.15
        self.tex_crawl.use(0)
        p["u_tex"] = 0
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.crawl_vao.render()
        self.ctx.disable(moderngl.BLEND)
        self.ctx.enable(moderngl.CULL_FACE)

    def _draw_pines(self, frame: SceneFrame, bz: float, count: int = 28, dist: float = 10.5) -> None:
        for i in range(count):
            side = -1.0 if i % 2 == 0 else 1.0
            x = side * (dist + (i % 5) * 1.4 + hash01(i + 20) * 2.0)
            z = bz - 22.0 + i * 2.6 + hash01(i + 40) * 1.5
            sc = 0.7 + (i % 6) * 0.1 + hash01(i) * 0.15
            name = "pine" if i % 3 else "pine2"
            self._draw_mesh(name, frame, model_trs(x, 0.0, z, sc, sc * (0.95 + hash01(i + 1) * 0.15), sc))

    def _draw_deciduous(self, frame: SceneFrame, bz: float, count: int = 20, dist: float = 9.0) -> None:
        for i in range(count):
            side = -1.0 if i % 2 == 0 else 1.0
            x = side * (dist + (i % 4) * 1.8 + hash01(i + 55) * 1.5)
            z = bz - 16.0 + i * 3.0
            sc = 0.65 + (i % 5) * 0.12
            name = "deciduous" if i % 2 == 0 else "deciduous2"
            self._draw_mesh(name, frame, model_trs(x, 0.0, z, sc, sc, sc))

    def _draw_road(self, frame: SceneFrame, bz: float, y: float = 0.0, yaw: float = 0.0, sx: float = 1.0) -> None:
        """Tile road segments so the lane never ends in camera view."""
        for dz in (-90.0, 0.0, 90.0):
            self._draw_mesh("road", frame, model_trs(frame.bus_pos.x if abs(yaw) > 1e-4 else 0.0, y, bz + dz, sx, 1.0, 1.0, yaw=yaw))

    def _draw_travel(self, frame: SceneFrame) -> None:
        bz = frame.bus_pos.z
        land = frame.landscape

        if land in ("europe", "town"):
            self._draw_mesh("europe", frame, model_trs(0, 0, bz))
            self._draw_road(frame, bz)
            if land == "town":
                self._draw_deciduous(frame, bz, count=22, dist=8.5)
            else:
                self._draw_pines(frame, bz, count=30, dist=9.5)
                self._draw_deciduous(frame, bz, count=12, dist=12.0)
            self._draw_mesh("mountains", frame, model_trs(0, -1.5, bz - 75, 1.2, 0.9, 1.0))
            if land == "town" or frame.props.get("bavaria", 1) < 0.5:
                for x in (-9.0, 9.0):
                    for row in range(6):
                        self._draw_mesh("house", frame, model_trs(x, 0, bz - 12 + row * 6.5, 0.8, 1.0, 0.85))
                self._draw_mesh("bridge_stone", frame, model_trs(0, 0, bz + 16, 0.95, 0.95, 0.95))

        elif land == "bridge":
            self._draw_mesh("cobble", frame, model_trs(0, 3.55, bz, 0.25, 1, 1.0))
            self._draw_mesh("suspension", frame, model_trs(0, 0, bz))
            self._draw_mesh("skyline", frame, model_trs(0, 0, bz - 40))
            self._draw_road(frame, bz, y=3.95, sx=0.9)
            if frame.props.get("balloons"):
                self._draw_instances(self.inst_balloon, frame, mode=3, emissive=0.2)

        elif land == "desert":
            self._draw_mesh("desert", frame, model_trs(0, 0, bz))
            self._draw_road(frame, bz)
            for zoff in (12, 28, 44):
                self._draw_mesh("iwan", frame, model_trs(0, 0, bz + zoff), tex=self.tex_mosaic)

        elif land == "canyon":
            self._draw_mesh("canyon", frame, model_trs(frame.bus_pos.x * 0.1, 0, bz))
            self._draw_road(frame, bz, yaw=frame.bus_yaw, sx=0.9)
            if frame.props.get("trucks"):
                for i in range(3):
                    tz = bz + 20 + i * 22 - (frame.t * 4.5) % 50
                    self._draw_billboard(
                        "jingle_truck",
                        (frame.bus_pos.x - 4.2, 0.08, tz),
                        (5.6, 3.7),
                        frame,
                        face_cam=False,
                        yaw=frame.bus_yaw + math.pi * 0.5,
                    )

        elif land == "river":
            self._draw_mesh("ghats", frame, model_trs(8, 0, bz + 6, 0.7, 0.7, 0.7))
            self._draw_mesh("cobble", frame, model_trs(0, 0, bz, 0.5, 1, 1))
            self._draw_road(frame, bz)
            self.prog_water["u_model"].write(model_trs(-10, 0.05, bz + 4, 0.55, 1, 0.7))
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
            if frame.props.get("diyas"):
                self._draw_instances(self.inst_diya, frame, mode=3, emissive=1.1)
                self._draw_instances(self.inst_boat, frame, mode=3)
            self._draw_mesh("pagoda", frame, model_trs(14, 3.5, bz + 12, 0.7, 0.7, 0.7))

        elif land == "alpine":
            self._draw_mesh("alpine", frame, model_trs(0, 0, bz))
            self._draw_road(frame, bz)
            self._draw_mesh("mountains", frame, model_trs(0, 2, bz - 80, 1.5, 1.25, 1.1))
            self._draw_mesh("suspension", frame, model_trs(0, 5, bz + 8, 0.55, 0.55, 0.55))
            self._draw_pines(frame, bz, count=26, dist=11.0)
            if frame.props.get("flags"):
                self._draw_instances(self.inst_flag, frame, mode=2)

        elif land == "city":
            self._draw_mesh("cobble", frame, model_trs(0, 0, 0))
            self._draw_road(frame, bz, sx=0.8)
            self._draw_mesh("pagoda", frame, model_trs(-9, 0, 10))
            self._draw_mesh("pagoda2", frame, model_trs(10, 0, 7))
            self._draw_mesh("pagoda", frame, model_trs(1, 0, 18, 0.75, 0.75, 0.75))
            for x in (-13, -5, 5, 13):
                self._draw_mesh("house", frame, model_trs(x, 0, -5, 0.75, 0.8, 0.9))

        self._draw_bus(frame)
        for b in frame.billboards:
            self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0.0))

    def render_frame(self, frame: SceneFrame, display: bool = True) -> None:
        self.cam.update(frame.camera, self.aspect)
        self.post.begin_scene(clear_color=(*frame.sky_bottom, 1.0))
        self._draw_sky(frame)

        if frame.landscape == "cosmos" or frame.scene_id == "crawl":
            # Procedural sky carries the starfield — no oversized instance blobs
            self._draw_crawl(frame)
            if frame.props.get("cloud_deck", 0) > 0.2:
                self._draw_mesh("cobble", frame, model_trs(0, -8, -25, 2.0, 1, 2.0), alpha=0.5)

        elif frame.landscape == "rooftop":
            self._draw_mesh("rooftop", frame, model_trs(0, 0, 0))
            # Soft distant city — keep far behind stage
            self._draw_mesh("skyline", frame, model_trs(0, -5.5, -48, 1.2, 0.75, 1.0))
            self._draw_mesh("pagoda", frame, model_trs(-18, -7, -36, 1.35, 1.35, 1.35))
            self._draw_mesh("pagoda2", frame, model_trs(16, -7, -34, 1.15, 1.15, 1.15))
            # Thin far ridge only (compressed Z so it cannot intersect stage)
            self._draw_mesh("mountains", frame, model_trs(0, -6, -110, 2.0, 1.1, 0.55))
            self._draw_instances(self.inst_lamp, frame, mode=3, emissive=1.6)
            if frame.stars:
                self._draw_instances(self.inst_star, frame, mode=1, emissive=0.7)
            for b in frame.billboards:
                self._draw_billboard(b["sprite"], b["pos"], b["size"], frame, sway=b.get("sway", 0.0))

        elif frame.landscape == "outro":
            self._draw_mesh("mountains", frame, model_trs(0, -4, -80, 2.4, 2.0, 1.4))
            self._draw_instances(self.inst_star, frame, mode=1, emissive=1.15)
            self._draw_mesh("skyline", frame, model_trs(0, -2, -35, 0.9, 0.65, 0.9))
            for i in range(12):
                self._draw_mesh(
                    "house",
                    frame,
                    model_trs(-22 + i * 4.2, 0, 8, 0.45, 0.35 + hash01(i) * 0.35, 0.45),
                    emissive=0.08,
                )
            self._draw_instances(self.inst_lamp, frame, mode=3, emissive=1.0)

        else:
            self._draw_travel(frame)

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
