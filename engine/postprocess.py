"""Multi-pass HDR post-processing: bloom, grain, CA, LUT, vignette, film burn."""

from __future__ import annotations

from dataclasses import dataclass

import moderngl
import numpy as np

from . import shaders as S
from .gpu import compile_program, upload_lut_3d
from .textures import color_grade_lut


@dataclass
class PostParams:
    grain: float = 0.08
    ca: float = 0.003
    vignette: float = 0.28
    bloom_str: float = 0.45
    bloom_threshold: float = 0.65
    gate_jitter: float = 0.6
    film_burn: float = 0.0
    kaleido: float = 0.0


def _setu(prog, name, value) -> None:
    if name in prog:
        prog[name].value = value


class PostStack:
    def __init__(self, ctx: moderngl.Context, width: int, height: int):
        self.ctx = ctx
        self.width = width
        self.height = height

        self.prog_extract = compile_program(ctx, S.POST_VS, S.BLOOM_EXTRACT_FS)
        self.prog_blur = compile_program(ctx, S.POST_VS, S.BLUR_FS)
        self.prog_composite = compile_program(ctx, S.POST_VS, S.COMPOSITE_FS)
        self.prog_copy = compile_program(ctx, S.POST_VS, S.COPY_FS)

        self.vao_extract = ctx.vertex_array(self.prog_extract, [])
        self.vao_blur = ctx.vertex_array(self.prog_blur, [])
        self.vao_composite = ctx.vertex_array(self.prog_composite, [])
        self.vao_copy = ctx.vertex_array(self.prog_copy, [])

        lut = color_grade_lut(32)
        self.lut = upload_lut_3d(ctx, lut)

        self._alloc_targets(width, height)

    def _alloc_targets(self, w: int, h: int) -> None:
        self.width, self.height = w, h
        # Scene HDR color + depth
        self.scene_color = self.ctx.texture((w, h), 4, dtype="f2")
        self.scene_color.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.scene_depth = self.ctx.depth_texture((w, h))
        self.scene_fbo = self.ctx.framebuffer(color_attachments=[self.scene_color], depth_attachment=self.scene_depth)

        bw, bh = max(1, w // 2), max(1, h // 2)
        self.bloom0 = self.ctx.texture((bw, bh), 4, dtype="f2")
        self.bloom1 = self.ctx.texture((bw, bh), 4, dtype="f2")
        self.bloom0.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.bloom1.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo_bloom0 = self.ctx.framebuffer(color_attachments=[self.bloom0])
        self.fbo_bloom1 = self.ctx.framebuffer(color_attachments=[self.bloom1])

        # Final LDR for display / readback
        self.final_color = self.ctx.texture((w, h), 4)
        self.final_color.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.final_fbo = self.ctx.framebuffer(color_attachments=[self.final_color])

        # Pre-allocated export buffer (RGBA8)
        self.read_buffer = bytearray(w * h * 4)

    def begin_scene(self, clear_color=(0.02, 0.02, 0.05, 1.0)) -> None:
        self.scene_fbo.use()
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.ctx.clear(*clear_color)

    def end_scene_and_post(self, t: float, params: PostParams, display: bool = True) -> None:
        ctx = self.ctx
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.CULL_FACE)

        # Bloom extract
        self.fbo_bloom0.use()
        ctx.viewport = (0, 0, self.bloom0.width, self.bloom0.height)
        self.scene_color.use(0)
        self.prog_extract["u_color"] = 0
        _setu(self.prog_extract, "u_threshold", params.bloom_threshold)
        self.vao_extract.render(mode=moderngl.TRIANGLES, vertices=3)

        # Blur H
        self.fbo_bloom1.use()
        self.bloom0.use(0)
        self.prog_blur["u_color"] = 0
        _setu(self.prog_blur, "u_direction", (1.0, 0.0))
        _setu(self.prog_blur, "u_texel", (1.0 / self.bloom0.width, 1.0 / self.bloom0.height))
        self.vao_blur.render(mode=moderngl.TRIANGLES, vertices=3)

        # Blur V
        self.fbo_bloom0.use()
        self.bloom1.use(0)
        _setu(self.prog_blur, "u_direction", (0.0, 1.0))
        self.vao_blur.render(mode=moderngl.TRIANGLES, vertices=3)

        # Composite into final
        self.final_fbo.use()
        ctx.viewport = (0, 0, self.width, self.height)
        self.scene_color.use(0)
        self.bloom0.use(1)
        self.lut.use(2)
        p = self.prog_composite
        p["u_color"] = 0
        p["u_bloom"] = 1
        p["u_lut"] = 2
        _setu(p, "u_time", float(t))
        _setu(p, "u_grain", params.grain)
        _setu(p, "u_ca", params.ca)
        _setu(p, "u_vignette", params.vignette)
        _setu(p, "u_bloom_str", params.bloom_str)
        _setu(p, "u_gate_jitter", params.gate_jitter)
        _setu(p, "u_film_burn", params.film_burn)
        _setu(p, "u_kaleido", params.kaleido)
        _setu(p, "u_texel", (1.0 / self.width, 1.0 / self.height))
        self.vao_composite.render(mode=moderngl.TRIANGLES, vertices=3)

        if display:
            ctx.screen.use()
            ctx.viewport = (0, 0, self.width, self.height)
            self.final_color.use(0)
            self.prog_copy["u_color"] = 0
            self.vao_copy.render(mode=moderngl.TRIANGLES, vertices=3)

        ctx.enable(moderngl.DEPTH_TEST)
        ctx.enable(moderngl.CULL_FACE)

    def read_final_into(self) -> memoryview:
        """Zero-allocation readback into preallocated bytearray."""
        self.final_fbo.read_into(self.read_buffer, components=4, dtype="f1")
        return memoryview(self.read_buffer)
