"""GPU resource helpers — VAOs, textures, programs."""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

import moderngl
import numpy as np

from . import mesh as M
from . import shaders as S
from .camera import CameraUBO


def compile_program(ctx: moderngl.Context, vs: str, fs: str) -> moderngl.Program:
    return ctx.program(vertex_shader=vs, fragment_shader=fs)


def upload_rgba(ctx: moderngl.Context, arr: np.ndarray, filter_linear: bool = True) -> moderngl.Texture:
    if arr.ndim == 2:
        h, w = arr.shape
        comp = 1
        data = arr
    elif arr.shape[2] == 3:
        h, w, _ = arr.shape
        # expand to RGBA
        rgba = np.empty((h, w, 4), dtype=np.uint8)
        rgba[:, :, :3] = arr
        rgba[:, :, 3] = 255
        data = rgba
        comp = 4
    else:
        h, w, comp = arr.shape
        data = arr
    tex = ctx.texture((w, h), comp, data.tobytes())
    if filter_linear:
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    else:
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
    tex.repeat_x = True
    tex.repeat_y = True
    return tex


def upload_lut_3d(ctx: moderngl.Context, lut: np.ndarray) -> moderngl.Texture3D:
    """lut shape (S, S, S, 3) uint8 — ModernGL expects depth, height, width order."""
    s = lut.shape[0]
    if lut.shape[3] == 3:
        rgba = np.empty((s, s, s, 4), dtype=np.uint8)
        rgba[..., :3] = lut
        rgba[..., 3] = 255
        data = rgba
        components = 4
    else:
        data = lut
        components = lut.shape[3]
    tex = ctx.texture3d((s, s, s), components, data.tobytes())
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    tex.repeat_x = False
    tex.repeat_y = False
    tex.repeat_z = False
    return tex


class MeshGPU:
    def __init__(self, ctx: moderngl.Context, program: moderngl.Program, data: M.MeshData):
        self.count = len(data.indices)
        interleaved = data.interleaved().tobytes()
        self.vbo = ctx.buffer(interleaved)
        self.ibo = ctx.buffer(data.indices.tobytes())
        # Layout: pos3 n3 uv2 color3 — skip stripped attrs by BYTE count (ModernGL `x` = 1 byte).
        mapping = (("in_pos", 3), ("in_normal", 3), ("in_uv", 2), ("in_color", 3))
        fmt_tokens = []
        attrs = []
        for name, n in mapping:
            if name in program:
                fmt_tokens.append(f"{n}f")
                attrs.append(name)
            else:
                fmt_tokens.append(f"{n * 4}x")
        self.vao = ctx.vertex_array(program, [(self.vbo, " ".join(fmt_tokens), *attrs)], self.ibo)

    def render(self) -> None:
        self.vao.render()


class InstancedMeshGPU:
    def __init__(self, ctx: moderngl.Context, program: moderngl.Program, data: M.MeshData):
        self.ctx = ctx
        self.program = program
        self.base_count = len(data.indices)
        interleaved = data.interleaved().tobytes()
        self.vbo = ctx.buffer(interleaved)
        self.ibo = ctx.buffer(data.indices.tobytes())
        # instance buffer: pos_scale(4) + tint_phase(4) + rot(4) = 12 floats
        self.instance_capacity = 0
        self.instance_vbo = ctx.buffer(reserve=12 * 4 * 4)
        self.vao = ctx.vertex_array(
            program,
            [
                (self.vbo, "3f 3f 2f 3f", "in_pos", "in_normal", "in_uv", "in_color"),
                (self.instance_vbo, "4f 4f 4f/i", "in_i_pos_scale", "in_i_tint_phase", "in_i_rot"),
            ],
            self.ibo,
        )
        self.n_instances = 0

    def set_instances(self, array: np.ndarray) -> None:
        """array shape (N, 12) float32."""
        array = np.ascontiguousarray(array, dtype=np.float32)
        nbytes = array.nbytes
        if nbytes > self.instance_vbo.size:
            self.instance_vbo = self.ctx.buffer(reserve=max(nbytes, 12 * 4 * 64))
            self.vao = self.ctx.vertex_array(
                self.program,
                [
                    (self.vbo, "3f 3f 2f 3f", "in_pos", "in_normal", "in_uv", "in_color"),
                    (self.instance_vbo, "4f 4f 4f/i", "in_i_pos_scale", "in_i_tint_phase", "in_i_rot"),
                ],
                self.ibo,
            )
        self.instance_vbo.write(array.tobytes())
        self.n_instances = len(array)

    def render(self) -> None:
        if self.n_instances <= 0:
            return
        self.vao.render(instances=self.n_instances)


class BillboardGPU:
    def __init__(self, ctx: moderngl.Context, program: moderngl.Program):
        verts, _ = M.billboard_quad()
        self.vbo = ctx.buffer(verts.tobytes())
        self.vao = ctx.vertex_array(program, [(self.vbo, "3f 2f", "in_pos", "in_uv")])

    def render(self) -> None:
        self.vao.render()


def identity_model() -> bytes:
    import glm
    from .mathutil import mat4_bytes

    return mat4_bytes(glm.mat4(1.0))


def model_trs(tx=0.0, ty=0.0, tz=0.0, sx=1.0, sy=1.0, sz=1.0, yaw=0.0) -> bytes:
    import glm
    from .mathutil import mat4_bytes

    m = glm.translate(glm.mat4(1.0), glm.vec3(tx, ty, tz))
    m = glm.rotate(m, yaw, glm.vec3(0, 1, 0))
    m = glm.scale(m, glm.vec3(sx, sy, sz))
    return mat4_bytes(m)
