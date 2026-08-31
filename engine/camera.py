"""Camera state packed into a ModernGL Uniform Buffer Object (binding 0)."""

from __future__ import annotations

from dataclasses import dataclass

import glm
import moderngl

from .config import CAMERA_UBO_BINDING, CAMERA_UBO_SIZE
from .mathutil import look_at, pack_camera_ubo, perspective


@dataclass
class CameraState:
    eye: glm.vec3
    target: glm.vec3
    up: glm.vec3
    fovy: float
    near: float = 0.15
    far: float = 900.0


class CameraUBO:
    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        self.buffer = ctx.buffer(reserve=CAMERA_UBO_SIZE)
        self.buffer.bind_to_uniform_block(CAMERA_UBO_BINDING)
        self.view = glm.mat4(1.0)
        self.proj = glm.mat4(1.0)
        self.eye = glm.vec3(0, 2, 8)

    def bind_program(self, prog: moderngl.Program) -> None:
        if "Camera" in prog:
            prog["Camera"].binding = CAMERA_UBO_BINDING

    def update(self, state: CameraState, aspect: float) -> None:
        self.eye = state.eye
        self.view = look_at(state.eye, state.target, state.up)
        self.proj = perspective(state.fovy, aspect, state.near, state.far)
        self.buffer.write(pack_camera_ubo(self.view, self.proj, state.eye))
