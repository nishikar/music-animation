"""ModernGL render pipeline: FBOs, shaders, bloom, CRT, compositing."""

from __future__ import annotations

import math
from dataclasses import dataclass

import moderngl
import numpy as np

from . import HEIGHT, WIDTH
from .math3d import as_bytes, identity


LINE_VS = """
#version 330 core
in vec3 in_pos;
in vec3 in_color;
uniform mat4 mvp;
uniform float time;
uniform float pulse;
out vec3 v_color;
void main() {
    vec3 p = in_pos;
    // tiny time wobble keeps uniform live under driver optimization
    p.y += 0.0001 * sin(time + p.x);
    gl_Position = mvp * vec4(p, 1.0);
    float glow = 0.85 + 0.15 * pulse;
    v_color = in_color * glow;
}
"""

LINE_FS = """
#version 330 core
in vec3 v_color;
out vec4 f_color;
void main() {
    f_color = vec4(v_color, 1.0);
}
"""

SOLID_VS = """
#version 330 core
in vec3 in_pos;
in vec3 in_normal;
in vec3 in_color;
uniform mat4 mvp;
uniform mat4 model;
uniform vec3 light_dir;
uniform vec3 light_color;
out vec3 v_color;
void main() {
    vec3 n = normalize(mat3(model) * in_normal);
    float ndl = max(dot(n, normalize(-light_dir)), 0.0);
    float spec = pow(max(dot(reflect(normalize(light_dir), n), vec3(0,0,1)), 0.0), 32.0);
    vec3 ambient = in_color * 0.25;
    vec3 diffuse = in_color * ndl * light_color;
    vec3 specular = light_color * spec * 0.45;
    v_color = ambient + diffuse + specular;
    gl_Position = mvp * vec4(in_pos, 1.0);
}
"""

SOLID_FS = """
#version 330 core
in vec3 v_color;
out vec4 f_color;
void main() {
    f_color = vec4(v_color, 1.0);
}
"""

PARTICLE_VS = """
#version 330 core
in vec3 in_pos;
in vec3 in_color;
in float in_size;
uniform mat4 mvp;
out vec3 v_color;
void main() {
    v_color = in_color;
    gl_Position = mvp * vec4(in_pos, 1.0);
    gl_PointSize = in_size;
}
"""

PARTICLE_FS = """
#version 330 core
in vec3 v_color;
out vec4 f_color;
void main() {
    vec2 c = gl_PointCoord * 2.0 - 1.0;
    float d = dot(c, c);
    if (d > 1.0) discard;
    float a = exp(-d * 2.8);
    f_color = vec4(v_color, a);
}
"""

QUAD_VS = """
#version 330 core
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

BLOOM_EXTRACT_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D tex;
uniform float threshold;
out vec4 f_color;
void main() {
    vec3 c = texture(tex, v_uv).rgb;
    float b = max(max(c.r, c.g), c.b);
    float m = smoothstep(threshold, threshold + 0.35, b);
    f_color = vec4(c * m, 1.0);
}
"""

BLUR_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D tex;
uniform vec2 direction;
uniform vec2 texel;
out vec4 f_color;
void main() {
    vec3 c = vec3(0.0);
    float wsum = 0.0;
    // 9-tap gaussian
    float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    c += texture(tex, v_uv).rgb * w[0];
    wsum += w[0];
    for (int i = 1; i < 5; ++i) {
        vec2 off = direction * texel * float(i) * 1.6;
        c += texture(tex, v_uv + off).rgb * w[i];
        c += texture(tex, v_uv - off).rgb * w[i];
        wsum += w[i] * 2.0;
    }
    f_color = vec4(c / wsum, 1.0);
}
"""

COMPOSITE_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D scene_tex;
uniform sampler2D bloom_tex;
uniform float bloom_strength;
uniform float exposure;
uniform float vignette;
uniform float time;
uniform int crt_mode;
uniform float shake_x;
uniform float shake_y;
out vec4 f_color;
void main() {
    vec2 uv = v_uv + vec2(shake_x, shake_y);
    if (crt_mode == 1) {
        // barrel distortion
        vec2 cc = uv * 2.0 - 1.0;
        float r2 = dot(cc, cc);
        cc *= 1.0 + 0.08 * r2;
        uv = cc * 0.5 + 0.5;
    }
    vec2 ca = (uv - 0.5) * (crt_mode == 1 ? 0.004 : 0.0);
    float r = texture(scene_tex, uv + ca).r;
    float g = texture(scene_tex, uv).g;
    float b = texture(scene_tex, uv - ca).b;
    vec3 scene = vec3(r, g, b);
    vec3 bloom = texture(bloom_tex, uv).rgb;
    vec3 color = scene + bloom * bloom_strength;
    color = 1.0 - exp(-color * exposure);

    if (crt_mode == 1) {
        float scan = 0.88 + 0.12 * sin(uv.y * 900.0 + time * 10.0);
        color *= scan;
        // slight RGB phosphor
        color.r *= 1.05;
        color.b *= 1.03;
    }

    float vig = smoothstep(1.2, 0.35, length(uv - 0.5));
    color *= mix(1.0, vig, vignette);
    f_color = vec4(color, 1.0);
}
"""

BG_VS = """
#version 330 core
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

BG_FS = """
#version 330 core
in vec2 v_uv;
uniform vec3 top_color;
uniform vec3 mid_color;
uniform vec3 bot_color;
uniform float star_amount;
uniform float time;
out vec4 f_color;
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
void main() {
    float y = v_uv.y;
    vec3 col = mix(bot_color, mid_color, smoothstep(0.0, 0.45, y));
    col = mix(col, top_color, smoothstep(0.45, 1.0, y));
    if (star_amount > 0.01) {
        vec2 gp = floor(v_uv * vec2(180.0, 120.0));
        float h = hash(gp);
        if (h > 1.0 - star_amount * 0.08) {
            float tw = 0.6 + 0.4 * sin(time * 4.0 + h * 40.0);
            col += vec3(tw) * (h - (1.0 - star_amount * 0.08)) * 20.0;
        }
    }
    f_color = vec4(col, 1.0);
}
"""


@dataclass
class Mesh:
    vao: moderngl.VertexArray
    mode: int
    count: int = 0


class Pipeline:
    def __init__(self, ctx: moderngl.Context, width: int = WIDTH, height: int = HEIGHT):
        self.ctx = ctx
        self.width = width
        self.height = height
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        self.line_prog = ctx.program(vertex_shader=LINE_VS, fragment_shader=LINE_FS)
        self.solid_prog = ctx.program(vertex_shader=SOLID_VS, fragment_shader=SOLID_FS)
        self.particle_prog = ctx.program(vertex_shader=PARTICLE_VS, fragment_shader=PARTICLE_FS)
        self.bg_prog = ctx.program(vertex_shader=BG_VS, fragment_shader=BG_FS)
        self.extract_prog = ctx.program(vertex_shader=QUAD_VS, fragment_shader=BLOOM_EXTRACT_FS)
        self.blur_prog = ctx.program(vertex_shader=QUAD_VS, fragment_shader=BLUR_FS)
        self.composite_prog = ctx.program(vertex_shader=QUAD_VS, fragment_shader=COMPOSITE_FS)

        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype=np.float32)
        self.quad_vbo = ctx.buffer(quad.tobytes())
        self.quad_vao_extract = ctx.simple_vertex_array(self.extract_prog, self.quad_vbo, "in_pos")
        self.quad_vao_blur = ctx.simple_vertex_array(self.blur_prog, self.quad_vbo, "in_pos")
        self.quad_vao_comp = ctx.simple_vertex_array(self.composite_prog, self.quad_vbo, "in_pos")
        self.quad_vao_bg = ctx.simple_vertex_array(self.bg_prog, self.quad_vbo, "in_pos")

        self._init_fbos()

        self.shake = [0.0, 0.0]
        self.crt_mode = 0
        self.bloom_strength = 0.85
        self.exposure = 1.15
        self.vignette = 0.55

    def _init_fbos(self):
        ctx = self.ctx
        w, h = self.width, self.height
        self.scene_tex = ctx.texture((w, h), 4)
        self.scene_depth = ctx.depth_renderbuffer((w, h))
        self.scene_fbo = ctx.framebuffer(self.scene_tex, self.scene_depth)

        bw, bh = w // 2, h // 2
        self.bloom0 = ctx.texture((bw, bh), 4)
        self.bloom1 = ctx.texture((bw, bh), 4)
        self.bloom_fbo0 = ctx.framebuffer(self.bloom0)
        self.bloom_fbo1 = ctx.framebuffer(self.bloom1)

        self.out_tex = ctx.texture((w, h), 4)
        self.out_fbo = ctx.framebuffer(self.out_tex)

        for t in (self.scene_tex, self.bloom0, self.bloom1, self.out_tex):
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)

    def begin_scene(self, clear=(0.02, 0.02, 0.06, 1.0)):
        self.scene_fbo.use()
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.ctx.clear(*clear)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.BLEND)

    def draw_background(self, top, mid, bot, star_amount=0.0, time=0.0):
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.bg_prog["top_color"].value = top
        self.bg_prog["mid_color"].value = mid
        self.bg_prog["bot_color"].value = bot
        self.bg_prog["star_amount"].value = float(star_amount)
        self.bg_prog["time"].value = float(time)
        self.quad_vao_bg.render(moderngl.TRIANGLE_STRIP)
        self.ctx.enable(moderngl.DEPTH_TEST)

    def make_line_mesh(self, data: np.ndarray) -> Mesh:
        vbo = self.ctx.buffer(np.ascontiguousarray(data, dtype=np.float32).tobytes())
        vao = self.ctx.vertex_array(
            self.line_prog,
            [(vbo, "3f 3f", "in_pos", "in_color")],
        )
        return Mesh(vao, moderngl.LINES, count=len(data) // 6)

    def make_solid_mesh(self, interleaved: np.ndarray, indices: np.ndarray) -> Mesh:
        vbo = self.ctx.buffer(np.ascontiguousarray(interleaved, dtype=np.float32).tobytes())
        ibo = self.ctx.buffer(np.ascontiguousarray(indices, dtype=np.uint32).tobytes())
        vao = self.ctx.vertex_array(
            self.solid_prog,
            [(vbo, "3f 3f 3f", "in_pos", "in_normal", "in_color")],
            ibo,
        )
        return Mesh(vao, moderngl.TRIANGLES)

    def make_particle_buffer(self, capacity: int):
        # pos3 color3 size1 = 7 floats
        vbo = self.ctx.buffer(reserve=capacity * 7 * 4)
        vao = self.ctx.vertex_array(
            self.particle_prog,
            [(vbo, "3f 3f 1f", "in_pos", "in_color", "in_size")],
        )
        return vbo, vao

    def draw_lines(self, mesh: Mesh, mvp: np.ndarray, time=0.0, pulse=0.0):
        self.line_prog["mvp"].write(as_bytes(mvp))
        if "time" in self.line_prog:
            self.line_prog["time"].value = float(time)
        if "pulse" in self.line_prog:
            self.line_prog["pulse"].value = float(pulse)
        self.ctx.line_width = 1.5
        mesh.vao.render(mesh.mode)

    def draw_solid(self, mesh: Mesh, mvp: np.ndarray, model: np.ndarray,
                   light_dir=(0.4, -1.0, 0.3), light_color=(1.0, 0.9, 0.7)):
        self.solid_prog["mvp"].write(as_bytes(mvp))
        self.solid_prog["model"].write(as_bytes(model))
        self.solid_prog["light_dir"].value = tuple(light_dir)
        self.solid_prog["light_color"].value = tuple(light_color)
        mesh.vao.render(mesh.mode)

    def draw_particles(self, vao, count: int, mvp: np.ndarray):
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.particle_prog["mvp"].write(as_bytes(mvp))
        vao.render(moderngl.POINTS, vertices=count)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ctx.enable(moderngl.DEPTH_TEST)

    def end_and_composite(self, time=0.0, target_fbo=None):
        # bloom extract
        self.bloom_fbo0.use()
        self.ctx.viewport = (0, 0, self.width // 2, self.height // 2)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.scene_tex.use(0)
        self.extract_prog["tex"].value = 0
        self.extract_prog["threshold"].value = 0.45
        self.quad_vao_extract.render(moderngl.TRIANGLE_STRIP)

        # blur H
        self.bloom_fbo1.use()
        self.bloom0.use(0)
        self.blur_prog["tex"].value = 0
        self.blur_prog["direction"].value = (1.0, 0.0)
        self.blur_prog["texel"].value = (1.0 / (self.width // 2), 1.0 / (self.height // 2))
        self.quad_vao_blur.render(moderngl.TRIANGLE_STRIP)

        # blur V
        self.bloom_fbo0.use()
        self.bloom1.use(0)
        self.blur_prog["direction"].value = (0.0, 1.0)
        self.quad_vao_blur.render(moderngl.TRIANGLE_STRIP)

        # composite to out or screen
        dest = target_fbo if target_fbo is not None else self.out_fbo
        dest.use()
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.scene_tex.use(0)
        self.bloom0.use(1)
        self.composite_prog["scene_tex"].value = 0
        self.composite_prog["bloom_tex"].value = 1
        self.composite_prog["bloom_strength"].value = float(self.bloom_strength)
        self.composite_prog["exposure"].value = float(self.exposure)
        self.composite_prog["vignette"].value = float(self.vignette)
        self.composite_prog["time"].value = float(time)
        self.composite_prog["crt_mode"].value = int(self.crt_mode)
        self.composite_prog["shake_x"].value = float(self.shake[0])
        self.composite_prog["shake_y"].value = float(self.shake[1])
        self.quad_vao_comp.render(moderngl.TRIANGLE_STRIP)

    def read_rgb(self) -> bytes:
        # OpenGL textures are often bottom-up; flip
        data = self.out_fbo.read(components=3, alignment=1)
        arr = np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 3)
        arr = np.flipud(arr)
        return arr.tobytes()

    def blit_to_screen(self):
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, self.width, self.height)
        # reuse composite onto screen
        self.scene_tex.use(0)
        self.bloom0.use(1)
        self.composite_prog["scene_tex"].value = 0
        self.composite_prog["bloom_tex"].value = 1
        self.quad_vao_comp.render(moderngl.TRIANGLE_STRIP)
