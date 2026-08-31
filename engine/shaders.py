"""GLSL shader sources for the Desecration Smile engine."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Shared camera UBO (binding 0)
# ---------------------------------------------------------------------------
CAMERA_UBO = """
layout(std140) uniform Camera {
    mat4 u_view;
    mat4 u_proj;
    vec4 u_cam_pos;
};
"""

# ---------------------------------------------------------------------------
# Solid / lit mesh (environment geometry)
# ---------------------------------------------------------------------------
MESH_VS = """
#version 330 core
""" + CAMERA_UBO + """
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_normal;
layout(location = 2) in vec2 in_uv;
layout(location = 3) in vec3 in_color;

uniform mat4 u_model;

out vec3 v_world;
out vec3 v_normal;
out vec2 v_uv;
out vec3 v_color;

void main() {
    vec4 world = u_model * vec4(in_pos, 1.0);
    v_world = world.xyz;
    v_normal = mat3(u_model) * in_normal;
    v_uv = in_uv;
    v_color = in_color;
    gl_Position = u_proj * u_view * world;
}
"""

MESH_FS = """
#version 330 core
""" + CAMERA_UBO + """
in vec3 v_world;
in vec3 v_normal;
in vec2 v_uv;
in vec3 v_color;

uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_ambient;
uniform float u_time;
uniform float u_fog_density;
uniform vec3 u_fog_color;
uniform float u_emissive;
uniform sampler2D u_tex;
uniform int u_use_tex;
uniform float u_alpha;

out vec4 f_color;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_dir);
    float ndl = max(dot(N, L), 0.0);
    float wrap = ndl * 0.65 + 0.35;
    vec3 base = v_color;
    if (u_use_tex == 1) {
        vec4 tex = texture(u_tex, v_uv);
        base = mix(base, tex.rgb, tex.a);
    }
    vec3 lit = base * (u_ambient + u_light_color * wrap);
    lit += base * u_emissive;
    float dist = length(v_world - u_cam_pos.xyz);
    float fog = 1.0 - exp(-u_fog_density * dist * 0.015);
    lit = mix(lit, u_fog_color, clamp(fog, 0.0, 0.75));
    f_color = vec4(lit, u_alpha);
}
"""

# ---------------------------------------------------------------------------
# Instanced props (stars, flags, lamps, trees, diyas, balloons)
# ---------------------------------------------------------------------------
INSTANCE_VS = """
#version 330 core
""" + CAMERA_UBO + """
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_normal;
layout(location = 2) in vec2 in_uv;
layout(location = 3) in vec3 in_color;

// Per-instance: xyz = position, w = scale
layout(location = 4) in vec4 in_i_pos_scale;
// Per-instance: rgb = tint, a = phase
layout(location = 5) in vec4 in_i_tint_phase;
// Per-instance rotation yaw (radians) in x, pitch in y, unused zw
layout(location = 6) in vec4 in_i_rot;

uniform float u_time;
uniform int u_mode; // 0=static, 1=twinkle, 2=flutter, 3=bob, 4=spin

out vec3 v_world;
out vec3 v_normal;
out vec2 v_uv;
out vec3 v_color;
out float v_phase;

mat3 rot_y(float a) {
    float c = cos(a), s = sin(a);
    return mat3(c, 0, s, 0, 1, 0, -s, 0, c);
}
mat3 rot_x(float a) {
    float c = cos(a), s = sin(a);
    return mat3(1, 0, 0, 0, c, -s, 0, s, c);
}

void main() {
    float scale = in_i_pos_scale.w;
    vec3 pos = in_pos * scale;
    float phase = in_i_tint_phase.a;
    float yaw = in_i_rot.x;
    float pitch = in_i_rot.y;

    if (u_mode == 2) {
        // prayer flag flutter
        float flap = sin(u_time * 8.0 + phase + in_pos.x * 4.0) * 0.15 * in_pos.x;
        pos.z += flap;
        pos.y += sin(u_time * 6.0 + phase) * 0.05 * abs(in_pos.x);
    } else if (u_mode == 3) {
        pos.y += sin(u_time * 1.4 + phase) * 0.35 * scale;
    } else if (u_mode == 4) {
        yaw += u_time * 0.6 + phase;
    }

    mat3 R = rot_y(yaw) * rot_x(pitch);
    pos = R * pos;
    vec3 world = in_i_pos_scale.xyz + pos;
    v_world = world;
    v_normal = R * in_normal;
    v_uv = in_uv;
    v_color = in_color * in_i_tint_phase.rgb;
    v_phase = phase;
    gl_Position = u_proj * u_view * vec4(world, 1.0);
}
"""

INSTANCE_FS = """
#version 330 core
in vec3 v_world;
in vec3 v_normal;
in vec2 v_uv;
in vec3 v_color;
in float v_phase;

uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_ambient;
uniform float u_time;
uniform float u_fog_density;
uniform vec3 u_fog_color;
uniform int u_mode;
uniform float u_emissive;

out vec4 f_color;

void main() {
    vec3 N = normalize(v_normal);
    float ndl = max(dot(N, normalize(-u_light_dir)), 0.0);
    vec3 lit = v_color * (u_ambient + u_light_color * (ndl * 0.7 + 0.3));
    float emit = u_emissive;
    if (u_mode == 1) {
        // star twinkle
        emit += 0.55 + 0.45 * sin(u_time * 5.0 + v_phase * 20.0);
        lit = v_color * emit;
    } else if (u_mode == 3) {
        emit += 0.8 + 0.2 * sin(u_time * 3.0 + v_phase);
        lit += v_color * emit * 0.5;
    }
    lit += v_color * u_emissive;
    float dist = length(v_world);
    float fog = 1.0 - exp(-u_fog_density * dist * dist * 0.00008);
    lit = mix(lit, u_fog_color, clamp(fog, 0.0, 0.85));
    f_color = vec4(lit, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Camera-facing billboards (characters, vehicles details)
# ---------------------------------------------------------------------------
BILLBOARD_VS = """
#version 330 core
""" + CAMERA_UBO + """
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec2 in_uv;

uniform vec3 u_position;
uniform vec2 u_size;
uniform float u_yaw; // optional fixed yaw; if u_face_cam==1 ignore
uniform int u_face_cam;
uniform float u_time;
uniform float u_sway;

out vec2 v_uv;

void main() {
    vec3 right;
    vec3 up = vec3(0.0, 1.0, 0.0);
    if (u_face_cam == 1) {
        vec3 cam = u_cam_pos.xyz;
        vec3 to_cam = normalize(vec3(cam.x - u_position.x, 0.0, cam.z - u_position.z));
        right = normalize(cross(up, to_cam));
    } else {
        right = vec3(cos(u_yaw), 0.0, sin(u_yaw));
    }
    float sway = sin(u_time * 4.0 + u_position.x) * u_sway * in_pos.y;
    vec3 world = u_position
        + right * in_pos.x * u_size.x
        + up * in_pos.y * u_size.y
        + right * sway;
    v_uv = in_uv;
    gl_Position = u_proj * u_view * vec4(world, 1.0);
}
"""

BILLBOARD_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_tex;
uniform float u_alpha;
uniform vec3 u_tint;

out vec4 f_color;

void main() {
    vec4 c = texture(u_tex, v_uv);
    c.rgb *= u_tint;
    c.a *= u_alpha;
    if (c.a < 0.1) discard;
    f_color = c;
}
"""

# ---------------------------------------------------------------------------
# Sky / gradient fullscreen (drawn as large inverted sphere or quad in world)
# ---------------------------------------------------------------------------
SKY_VS = """
#version 330 core
""" + CAMERA_UBO + """
layout(location = 0) in vec3 in_pos;
out vec3 v_dir;

void main() {
    mat4 view_no_trans = mat4(mat3(u_view));
    vec4 clip = u_proj * view_no_trans * vec4(in_pos, 1.0);
    gl_Position = clip.xyww;
    v_dir = in_pos;
}
"""

SKY_FS = """
#version 330 core
in vec3 v_dir;
uniform vec3 u_top;
uniform vec3 u_horizon;
uniform vec3 u_bottom;
uniform float u_time;
uniform float u_sun_elev;
uniform vec3 u_sun_color;
uniform int u_stars;

out vec4 f_color;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void main() {
    vec3 d = normalize(v_dir);
    float h = d.y * 0.5 + 0.5;
    vec3 col = mix(u_bottom, u_horizon, smoothstep(0.0, 0.45, h));
    col = mix(col, u_top, smoothstep(0.45, 1.0, h));

    // sun disk
    float elev = clamp(u_sun_elev, -0.2, 1.2);
    vec3 sun_dir = normalize(vec3(0.35, elev, -0.75));
    float sun = pow(max(dot(d, sun_dir), 0.0), 180.0);
    float glow = pow(max(dot(d, sun_dir), 0.0), 12.0);
    col += u_sun_color * (sun * 2.5 + glow * 0.45);

    if (u_stars == 1 && d.y > 0.05) {
        float s = step(0.997, hash(floor(d.xz * 80.0)));
        float tw = 0.6 + 0.4 * sin(u_time * 3.0 + hash(floor(d.xz * 80.0)) * 40.0);
        col += vec3(s * tw);
    }
    f_color = vec4(col, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Water / canal reflective plane
# ---------------------------------------------------------------------------
WATER_VS = """
#version 330 core
""" + CAMERA_UBO + """
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_normal;
layout(location = 2) in vec2 in_uv;
layout(location = 3) in vec3 in_color;

uniform mat4 u_model;
uniform float u_time;

out vec3 v_world;
out vec2 v_uv;
out vec3 v_color;

void main() {
    vec3 p = in_pos;
    p.y += sin(p.x * 2.5 + u_time * 1.8) * 0.03 + cos(p.z * 2.2 + u_time * 1.4) * 0.03;
    vec4 world = u_model * vec4(p, 1.0);
    v_world = world.xyz;
    v_uv = in_uv;
    v_color = in_color;
    gl_Position = u_proj * u_view * world;
}
"""

WATER_FS = """
#version 330 core
in vec3 v_world;
in vec2 v_uv;
in vec3 v_color;

uniform float u_time;
uniform vec3 u_light_dir;
uniform vec3 u_cam_world;
uniform vec3 u_fog_color;
uniform float u_fog_density;
uniform sampler2D u_normal_map;

out vec4 f_color;

void main() {
    vec2 uv = v_uv * 4.0 + vec2(u_time * 0.03, u_time * 0.02);
    vec3 ntex = texture(u_normal_map, uv).xyz * 2.0 - 1.0;
    vec3 N = normalize(vec3(ntex.x, 1.0, ntex.y));
    vec3 V = normalize(u_cam_world - v_world);
    vec3 L = normalize(-u_light_dir);
    float fres = pow(1.0 - max(dot(N, V), 0.0), 3.0);
    float spec = pow(max(dot(reflect(-L, N), V), 0.0), 64.0);
    vec3 col = mix(v_color * 0.55, vec3(0.55, 0.7, 0.85), fres * 0.5);
    col += vec3(1.0, 0.95, 0.8) * spec * 0.6;
    float dist = length(v_world - u_cam_world);
    float fog = 1.0 - exp(-u_fog_density * dist * dist * 0.00008);
    col = mix(col, u_fog_color, clamp(fog, 0.0, 0.85));
    f_color = vec4(col, 0.92);
}
"""

# ---------------------------------------------------------------------------
# Star Wars crawl text plane
# ---------------------------------------------------------------------------
CRAWL_VS = """
#version 330 core
""" + CAMERA_UBO + """
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec2 in_uv;

uniform mat4 u_model;

out vec2 v_uv;

void main() {
    vec4 world = u_model * vec4(in_pos, 1.0);
    v_uv = in_uv;
    gl_Position = u_proj * u_view * world;
}
"""

CRAWL_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_tex;
uniform float u_glow;

out vec4 f_color;

void main() {
    vec4 c = texture(u_tex, v_uv);
    if (c.a < 0.05) discard;
    vec3 glow = c.rgb * u_glow;
    f_color = vec4(c.rgb + glow * 0.35, c.a);
}
"""

# ---------------------------------------------------------------------------
# Post-process: fullscreen triangle
# ---------------------------------------------------------------------------
POST_VS = """
#version 330 core
out vec2 v_uv;
void main() {
    vec2 pos = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    v_uv = pos;
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
"""

# Pass A: bloom extract
BLOOM_EXTRACT_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_color;
uniform float u_threshold;
out vec4 f_color;

void main() {
    vec3 c = texture(u_color, v_uv).rgb;
    float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float m = smoothstep(u_threshold, u_threshold + 0.35, lum);
    f_color = vec4(c * m, 1.0);
}
"""

# Pass B: separable gaussian blur
BLUR_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_color;
uniform vec2 u_direction;
uniform vec2 u_texel;
out vec4 f_color;

void main() {
    vec3 sum = vec3(0.0);
    float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    sum += texture(u_color, v_uv).rgb * w[0];
    for (int i = 1; i < 5; ++i) {
        vec2 o = u_direction * u_texel * float(i) * 1.8;
        sum += texture(u_color, v_uv + o).rgb * w[i];
        sum += texture(u_color, v_uv - o).rgb * w[i];
    }
    f_color = vec4(sum, 1.0);
}
"""

# Final composite: grain, CA, grading, bloom, vignette, film burn
COMPOSITE_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_color;
uniform sampler2D u_bloom;
uniform sampler3D u_lut;
uniform float u_time;
uniform float u_grain;
uniform float u_ca;
uniform float u_vignette;
uniform float u_bloom_str;
uniform float u_gate_jitter;
uniform float u_film_burn;
uniform float u_kaleido; // 0..1 rubaiyat effect
uniform vec2 u_texel;

out vec4 f_color;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

vec2 barrel(vec2 uv, float k) {
    vec2 c = uv * 2.0 - 1.0;
    float r2 = dot(c, c);
    c *= 1.0 + k * r2;
    return c * 0.5 + 0.5;
}

void main() {
    // Super-8 gate jitter
    float jitter = (hash(vec2(floor(u_time * 24.0), 0.3)) - 0.5) * u_gate_jitter;
    vec2 uv = v_uv + vec2(jitter * 0.004, jitter * 0.002);

    // Rubaiyat kaleidoscope border
    if (u_kaleido > 0.001) {
        vec2 c = uv - 0.5;
        float ang = atan(c.y, c.x);
        float rad = length(c);
        float seg = 6.2831853 / 8.0;
        ang = mod(ang, seg);
        ang = abs(ang - seg * 0.5);
        vec2 kuv = vec2(cos(ang), sin(ang)) * rad + 0.5;
        float border = smoothstep(0.35, 0.55, rad);
        uv = mix(uv, kuv, border * u_kaleido);
    }

    // Chromatic aberration
    vec2 dir = (uv - 0.5) * u_ca;
    float r = texture(u_color, uv + dir).r;
    float g = texture(u_color, uv).g;
    float b = texture(u_color, uv - dir).b;
    vec3 col = vec3(r, g, b);

    // Bloom
    vec3 bloom = texture(u_bloom, uv).rgb;
    col += bloom * u_bloom_str;

    // Warm amber / terracotta grade via LUT
    vec3 coord = clamp(col, 0.0, 1.0);
    col = texture(u_lut, coord).rgb;

    // Film grain + dust
    float grain = (hash(uv * vec2(1920.0, 1080.0) + u_time * 60.0) - 0.5) * u_grain;
    col += grain;
    float dust = step(0.9985, hash(uv * 400.0 + floor(u_time * 12.0)));
    col += dust * 0.35;

    // Soft vignette
    vec2 vc = uv * 2.0 - 1.0;
    float vig = 1.0 - dot(vc, vc) * u_vignette;
    col *= vig;

    // Film burn flare (outro)
    if (u_film_burn > 0.0) {
        float burn = u_film_burn;
        vec2 bc = uv - vec2(0.5, 0.4);
        float blob = exp(-dot(bc, bc) * (3.0 - burn * 2.0));
        col = mix(col, vec3(1.0, 0.55, 0.15), clamp(blob * burn * 1.8 + burn * 0.4, 0.0, 1.0));
        col *= 1.0 - smoothstep(0.7, 1.0, burn);
    }

    f_color = vec4(col, 1.0);
}
"""

# Copy / display
COPY_FS = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_color;
out vec4 f_color;
void main() {
    f_color = texture(u_color, v_uv);
}
"""
