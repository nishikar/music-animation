#!/usr/bin/env python3
"""
Wish You Were Here (Nepali Adhunik) — Himalayan Landscape Visualizer
Production-oriented procedural GLSL scenes, 72 BPM / 189s.

Controls: ESC quit | SPACE pause | R reset | 1-8 jump scene
          S screenshot | LEFT/RIGHT scrub 5s
CLI:      --screenshot-all DIR | --screenshot TIME PATH
"""
import argparse
import os
import struct
import sys

# Platform display drivers:
# - macOS must use Cocoa (never force x11 — that yields "video system not initialized")
# - Linux cloud/headless VMs often need x11 + software GL
if sys.platform == "darwin":
    os.environ.pop("SDL_VIDEODRIVER", None)  # let SDL pick cocoa
    os.environ.pop("LIBGL_ALWAYS_SOFTWARE", None)
elif sys.platform.startswith("linux"):
    os.environ.setdefault("SDL_VIDEODRIVER", "x11")
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import pygame
import moderngl

# ==============================================================================
# 1. PYGAME & OPENGL 3.3 CORE PROFILE
# ==============================================================================
pygame.init()
try:
    pygame.mixer.quit()
except pygame.error:
    pass

# macOS Core Profile attributes — must run after init, before set_mode
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FLAGS, pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG)

WINDOW_SIZE = (1280, 720)
screen = pygame.display.set_mode(WINDOW_SIZE, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
pygame.display.set_caption("Wish You Were Here (Nepali Adhunik) - 72 BPM")

# Bind ModernGL to the pygame-created GL context (important on macOS)
ctx = moderngl.create_context(require=330)
width, height = screen.get_size()
ctx.viewport = (0, 0, width, height)

vertices = [-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, 1.0, 1.0]
vertex_data = struct.pack(f"{len(vertices)}f", *vertices)

vertex_shader = """
#version 330
in vec2 in_vert;
void main() { gl_Position = vec4(in_vert, 0.0, 1.0); }
"""

fragment_shader = """
#version 330
out vec4 fragColor;

uniform vec2  u_resolution;
uniform float u_time;
uniform float u_bpm;
uniform float u_duration;

#define PI 3.14159265359
#define TWO_PI 6.28318530718

// =============================================================================
// HASH / NOISE
// =============================================================================
float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float hash21(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise(float x) {
    float i = floor(x);
    float f = fract(x);
    float u = f * f * (3.0 - 2.0 * f);
    return mix(hash11(i), hash11(i + 1.0), u);
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
    for (int i = 0; i < 5; i++) {
        v += a * noise2D(p);
        p = m * p;
        a *= 0.5;
    }
    return v;
}

float fbm3(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) {
        v += a * noise2D(p);
        p *= 2.15;
        a *= 0.5;
    }
    return v;
}

// =============================================================================
// TERRAIN
// =============================================================================
float broadRidge(float x, float freq, float amp) {
    float n = 0.0;
    n += vnoise(x * freq)         * 0.44;
    n += vnoise(x * freq * 2.07)  * 0.25;
    n += vnoise(x * freq * 4.3)   * 0.14;
    n += vnoise(x * freq * 8.9)   * 0.09;
    n += vnoise(x * freq * 17.0)  * 0.05;
    n += vnoise(x * freq * 32.0)  * 0.03; // crags — keep below aliasing range
    // Domain-warp for irregular ridgelines
    float warp = (vnoise(x * freq * 1.3 + 9.0) - 0.5) * 0.28;
    n += (vnoise((x + warp) * freq * 2.8) - 0.5) * 0.07;
    // Sharp horns (sparse)
    float cell = floor(x * freq * 0.38);
    float local = fract(x * freq * 0.38) - 0.5;
    float horn = exp(-local * local * 55.0) * hash11(cell + 1.7);
    horn *= step(0.55, hash11(cell)) * amp * 0.30;
    float steps = max(0.0, vnoise(x * freq * 5.5) - 0.62) * amp * 0.07;
    return (n - 0.38) * amp + horn + steps;
}

float getFarMassifH(float x, float pan) {
    return broadRidge(x + pan * 0.11, 0.82, 0.60) + 0.16;
}
float getDistantRidgeH(float x, float pan) {
    return broadRidge(x + 2.4 + pan * 0.30, 1.20, 0.50) + 0.00;
}
float getMidRidgeH(float x, float pan) {
    return broadRidge(x + 5.6 + pan * 0.55, 1.50, 0.42) - 0.16;
}
float getNearFoothillH(float x, float pan) {
    return broadRidge(x + 9.0 + pan * 0.90, 1.80, 0.34) - 0.30;
}
float getShoreH(float x, float pan) {
    float curve = sin(x * 1.25 + 0.9) * 0.14 - 0.42;
    float detail = broadRidge(x + pan * 1.2, 2.3, 0.11);
    float rocks = max(0.0, vnoise(x * 5.5 + pan) - 0.55) * 0.06;
    return curve + detail + rocks;
}

// Discrete pine tree height — wide layered cones, irregular gaps (not barcode spikes)
float pineTreeAt(float x, float density, float base, float maxH) {
    float cell = floor(x * density);
    float lx = fract(x * density) - 0.5;
    float hr = hash11(cell + 0.3);
    if (hr < 0.32) return base; // more clearings
    // Lower w => wider canopy (avoid toothpick trees)
    float w = mix(0.95, 1.65, hash11(cell + 1.1));
    float th = maxH * (0.50 + 0.95 * hr);
    // Slight lateral lean
    lx += (hash11(cell + 5.5) - 0.5) * 0.08;
    float shape = 0.0;
    for (int t = 0; t < 4; t++) {
        float ft = float(t);
        float taper = 1.0 - ft * 0.18;
        float local = 1.0 - abs(lx) * (w / max(taper, 0.25));
        local = max(0.0, local);
        local = pow(local, 0.95 + ft * 0.12);
        float top = th * (0.55 + 0.12 * (3.0 - ft));
        // Jagged canopy edge
        local *= 0.85 + 0.15 * noise2D(vec2(lx * 20.0 + cell, ft));
        shape = max(shape, local * top * (1.0 - ft * 0.08));
    }
    float trunk = step(abs(lx), mix(0.03, 0.05, hr)) * th * 0.16;
    return base + max(shape, trunk);
}

float rhodoAt(float x, float density, float base, float maxH) {
    float cell = floor(x * density);
    float lx = fract(x * density) - 0.5;
    float hr = hash11(cell + 8.2);
    if (hr < 0.25) return base;
    float shape = max(0.0, 1.0 - abs(lx) * 2.1);
    shape = pow(shape, 0.75);
    float crown = sqrt(shape) * maxH * (0.65 + 0.55 * hr);
    return base + crown;
}

// Soft forest canopy edge + sparse specimen pines (avoids barcode sawtooth)
float forestCanopy(float x, float base, float amount, float maxH) {
    if (amount < 0.01) return base;
    // Primary: undulating closed canopy (organic, not periodic spikes)
    float canopy = 0.5 + 0.5 * fbm3(vec2(x * 5.5, 2.0));
    canopy += 0.20 * (vnoise(x * 11.0) - 0.5);
    canopy += 0.10 * (vnoise(x * 23.0) - 0.5);
    float h = base + maxH * 0.70 * clamp(canopy, 0.0, 1.2) * amount;
    // Sparse taller specimen trees only (low density)
    float tall = pineTreeAt(x, 9.0, base, maxH * 1.15);
    float tall2 = pineTreeAt(x + 1.15, 7.0, base, maxH * 0.9);
    h = max(h, mix(base, max(tall, tall2), amount * 0.35));
    return h;
}

float getMidWithVeg(float x, float pan, float forest, float rhodo) {
    float base = getMidRidgeH(x, pan);
    float pines = forestCanopy(x + pan * 0.55, base, forest, 0.075);
    float rhod = rhodoAt(x + pan * 0.55 + 1.4, 26.0, base, 0.050);
    float h = mix(base, pines, clamp(forest, 0.0, 1.0));
    return mix(h, rhod, rhodo);
}

float getNearWithVeg(float x, float pan, float forest, float rhodo) {
    float base = getNearFoothillH(x, pan);
    float pines = forestCanopy(x + pan * 0.90, base, forest, 0.10);
    float rhod = rhodoAt(x + pan * 0.90 + 2.0, 28.0, base, 0.058);
    float h = mix(base, pines, clamp(forest, 0.0, 1.0));
    return mix(h, rhod, rhodo);
}

// =============================================================================
// STARS / MILKY WAY
// =============================================================================
float renderStars(vec2 uv, float threshold) {
    float stars = 0.0;
    for (int s = 0; s < 3; s++) {
        float scale = 95.0 + float(s) * 50.0;
        vec2 grid = floor(uv * scale);
        float h = hash21(grid + float(s) * 17.0);
        if (h > threshold - float(s) * 0.01) {
            vec2 sub = fract(uv * scale) - 0.5;
            float size = mix(0.06, 0.16, hash21(grid + 3.3));
            float tw = 0.55 + 0.45 * sin(u_time * (1.2 + h * 2.5) + h * TWO_PI);
            float b = smoothstep(size, 0.0, length(sub)) * tw;
            b *= 1.0 + step(0.994, h) * 1.6;
            // slight color weight baked into brightness variation
            stars += b * (0.6 - float(s) * 0.12);
        }
    }
    return min(stars, 1.5);
}

float milkyWay(vec2 p) {
    // Soft dusty galactic band (not a hard searchlight)
    float band = abs(p.x * 0.45 + p.y * 0.95 - 0.08);
    float core = exp(-band * band * 18.0);
    float dust = fbm3(p * 4.0 + vec2(2.0, u_time * 0.008));
    float clumps = smoothstep(0.35, 0.75, dust);
    return core * (0.15 + 0.35 * clumps);
}

// =============================================================================
// SDF HELPERS & PROPS
// =============================================================================
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}
float sdCircle(vec2 p, float r) { return length(p) - r; }

vec4 prayerFlags(vec2 p, vec2 left, vec2 right, float flutter, float presence) {
    if (presence < 0.02) return vec4(0.0);
    float x0 = min(left.x, right.x);
    float x1 = max(left.x, right.x);
    float t = clamp((p.x - x0) / max(x1 - x0, 1e-4), 0.0, 1.0);
    float yBase = mix(left.y, right.y, t);
    float sag = -0.032 * sin(t * PI);
    float wind = sin(t * 16.0 + u_time * (4.5 + flutter * 2.0)) * 0.010 * flutter;
    float ropeY = yBase + sag + wind;
    float inSpan = step(x0, p.x) * step(p.x, x1);

    // Poles at ends
    float poleL = smoothstep(0.006, 0.0, abs(p.x - left.x)) *
                  step(p.y, left.y + 0.02) * step(left.y - 0.16, p.y);
    float poleR = smoothstep(0.006, 0.0, abs(p.x - right.x)) *
                  step(p.y, right.y + 0.02) * step(right.y - 0.16, p.y);
    float rope = smoothstep(0.0036, 0.0, abs(p.y - ropeY)) * inSpan;

    float flagIdx = floor(t * 15.0);
    float ft = (flagIdx + 0.5) / 15.0;
    float cx = mix(x0, x1, ft);
    float cy = mix(left.y, right.y, ft) - 0.032 * sin(ft * PI)
             + sin(ft * 16.0 + u_time * (4.5 + flutter * 2.0)) * 0.010 * flutter;
    float flWind = sin(u_time * (5.0 + hash11(flagIdx)) + flagIdx) * 0.016 * flutter;
    vec2 fp = p - vec2(cx + flWind * 0.25, cy);
    float flagH = 0.030 + 0.008 * hash11(flagIdx + 2.0);
    float bottom = -flagH + sin(fp.x * 70.0 + u_time * 6.5 + flagIdx) * 0.006 * flutter;
    // Slight perspective taper
    float halfW = 0.015 + 0.004 * hash11(flagIdx + 4.0);
    float flagMask = step(abs(fp.x), halfW) * step(fp.y, 0.004) * step(bottom, fp.y) * inSpan;
    // Frayed edge noise
    flagMask *= step(0.25, noise2D(fp * 60.0 + flagIdx));

    vec3 fcol = vec3(0.78, 0.12, 0.10);
    float cm = mod(flagIdx, 5.0);
    if (cm >= 1.0 && cm < 2.0) fcol = vec3(0.90, 0.76, 0.14);
    else if (cm >= 2.0 && cm < 3.0) fcol = vec3(0.92, 0.92, 0.88);
    else if (cm >= 3.0 && cm < 4.0) fcol = vec3(0.14, 0.46, 0.28);
    else if (cm >= 4.0) fcol = vec3(0.14, 0.28, 0.72);

    float poles = max(poleL, poleR);
    float alpha = max(max(rope * 0.9, flagMask), poles * 0.85) * presence;
    vec3 rgb = vec3(0.22, 0.16, 0.10); // rope/pole wood
    rgb = mix(rgb, fcol, flagMask);
    rgb = mix(rgb, vec3(0.28, 0.20, 0.12), poles);
    return vec4(rgb, alpha);
}

vec4 drawStupa(vec2 p, vec2 anchor, float scale, float presence) {
    if (presence < 0.02) return vec4(0.0);
    vec2 q = (p - anchor) / scale;
    float d = 1e5;
    d = min(d, sdBox(q - vec2(0.0, -0.16), vec2(0.42, 0.045)));
    d = min(d, sdBox(q - vec2(0.0, -0.08), vec2(0.34, 0.040)));
    d = min(d, sdCircle(q - vec2(0.0, 0.10), 0.20));
    d = min(d, sdBox(q - vec2(0.0, 0.30), vec2(0.09, 0.06)));
    // Tiered spire
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        d = min(d, sdBox(q - vec2(0.0, 0.40 + fi * 0.045), vec2(0.04 - fi * 0.005, 0.022)));
    }
    d = min(d, sdCircle(q - vec2(0.0, 0.66), 0.025)); // tip
    float mask = smoothstep(0.018, 0.0, d);
    // Soft shading
    float shade = clamp(0.55 + q.x * 0.35 + q.y * 0.15, 0.35, 1.0);
    vec3 col = vec3(0.86, 0.82, 0.74) * shade;
    // Buddha eyes band
    float eyes = smoothstep(0.035, 0.0, abs(q.y - 0.24)) * smoothstep(0.14, 0.0, abs(q.x));
    col = mix(col, vec3(0.45, 0.12, 0.10), eyes * 0.75);
    // Gold tip
    col = mix(col, vec3(0.92, 0.72, 0.22), smoothstep(0.07, 0.0, length(q - vec2(0.0, 0.66))));
    // Ground shadow
    float sh = smoothstep(0.5, 0.0, length(vec2(q.x * 0.8, q.y + 0.22))) * 0.35;
    return vec4(mix(col, vec3(0.05), sh * 0.5), max(mask, sh * 0.4) * presence);
}

vec4 drawLodge(vec2 p, vec2 anchor, float scale, float presence, float windowGlow) {
    if (presence < 0.02) return vec4(0.0);
    vec2 q = (p - anchor) / scale;
    float body = sdBox(q - vec2(0.0, 0.02), vec2(0.38, 0.16));
    float roofD = abs(q.x) * 0.95 + (q.y - 0.18) * 1.35 - 0.38;
    roofD = max(roofD, -(q.y - 0.14));
    float mask = smoothstep(0.018, 0.0, min(body, roofD));
    // Stone / wood
    float stoneN = noise2D(q * 10.0);
    vec3 col = mix(vec3(0.20, 0.14, 0.10), vec3(0.32, 0.28, 0.24), stoneN * step(q.y, 0.0));
    col = mix(col, vec3(0.35, 0.18, 0.10), step(0.14, q.y) * mask); // roof timber
    // Eaves overhang line
    float eave = smoothstep(0.02, 0.0, abs(q.y - 0.16)) * step(abs(q.x), 0.42);
    col = mix(col, col * 0.6, eave);
    // Windows
    float win = 0.0;
    win += smoothstep(0.025, 0.0, sdBox(q - vec2(-0.16, 0.02), vec2(0.055, 0.045)));
    win += smoothstep(0.025, 0.0, sdBox(q - vec2(0.0, 0.02), vec2(0.055, 0.045)));
    win += smoothstep(0.025, 0.0, sdBox(q - vec2(0.16, 0.02), vec2(0.055, 0.045)));
    vec3 glow = vec3(1.0, 0.75, 0.38) * windowGlow;
    col = mix(col, glow, clamp(win, 0.0, 1.0) * windowGlow);
    // Chimney + smoke
    float chim = smoothstep(0.015, 0.0, sdBox(q - vec2(0.24, 0.30), vec2(0.03, 0.07)));
    col = mix(col, vec3(0.25, 0.2, 0.16), chim);
    float smoke = 0.0;
    if (windowGlow > 0.25) {
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            vec2 sp = q - vec2(0.24 + sin(u_time * 0.9 + fi) * 0.02,
                               0.40 + fi * 0.05 + fract(u_time * 0.15 + fi * 0.3) * 0.08);
            smoke += smoothstep(0.06, 0.0, length(sp * vec2(1.4, 0.7))) *
                     (0.25 + 0.2 * noise2D(sp * 6.0 + u_time));
        }
        col = mix(col, vec3(0.45, 0.45, 0.48), smoke);
    }
    return vec4(col, max(mask, smoke * 0.45) * presence);
}

vec4 drawCairn(vec2 p, vec2 anchor, float scale, float presence) {
    if (presence < 0.02) return vec4(0.0);
    vec2 q = (p - anchor) / scale;
    float d = 1e5;
    d = min(d, sdCircle(q - vec2(-0.02, -0.06), 0.13));
    d = min(d, sdCircle(q - vec2(0.06, 0.05), 0.10));
    d = min(d, sdCircle(q - vec2(-0.04, 0.14), 0.08));
    d = min(d, sdCircle(q - vec2(0.02, 0.26), 0.06));
    d = min(d, sdCircle(q - vec2(0.0, 0.36), 0.04));
    float mask = smoothstep(0.018, 0.0, d);
    float n = noise2D(q * 7.0);
    vec3 col = mix(vec3(0.38, 0.36, 0.34), vec3(0.55, 0.52, 0.48), n);
    // Prayer scarf on cairn
    float kata = smoothstep(0.03, 0.0, abs(q.y - 0.28)) * smoothstep(0.12, 0.0, abs(q.x));
    col = mix(col, vec3(0.85, 0.88, 0.95), kata * 0.7);
    return vec4(col, mask * presence);
}

vec4 drawBoat(vec2 p, vec2 anchor, float scale, float presence) {
    if (presence < 0.02) return vec4(0.0);
    float bob = sin(u_time * 1.4 + anchor.x * 4.0) * 0.007;
    vec2 q = (p - anchor - vec2(0.0, bob)) / scale;
    // Crescent hull
    float hull = max(abs(q.x) * 0.35 + q.y * 1.2 - 0.02, -q.y - 0.05);
    hull = max(hull, abs(q.x) - 0.28);
    float mask = smoothstep(0.012, 0.0, hull);
    // Gunwale highlight
    float rim = smoothstep(0.02, 0.0, abs(q.y - 0.01)) * step(abs(q.x), 0.26);
    float mast = smoothstep(0.006, 0.0, abs(q.x + 0.04)) * step(0.0, q.y) * step(q.y, 0.26);
    vec3 col = vec3(0.22, 0.14, 0.08);
    col = mix(col, vec3(0.40, 0.30, 0.18), rim);
    col = mix(col, vec3(0.30, 0.24, 0.16), mast);
    return vec4(col, max(mask, mast * 0.85) * presence);
}

vec4 drawBirds(vec2 p, float presence) {
    if (presence < 0.02) return vec4(0.0);
    float alpha = 0.0;
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float seed = hash11(fi * 9.1 + 1.4);
        float speed = 0.035 + seed * 0.04;
        float x = fract(seed * 1.7 + u_time * speed * 0.12) * 2.6 - 1.3;
        float y = 0.28 + seed * 0.38 + sin(u_time * 0.7 + fi * 1.3) * 0.02;
        // Smaller birds for grand mountain scale
        float sc = mix(0.55, 0.85, seed);
        vec2 bp = (p - vec2(x, y)) / sc;
        float flap = sin(u_time * (7.0 + seed * 3.0) + fi) * 0.012;
        float wingY = abs(bp.x) * 0.42 - bp.x * bp.x * 3.0 + flap;
        float wing = smoothstep(0.008, 0.0, abs(bp.y - wingY)) *
                     smoothstep(0.055, 0.008, abs(bp.x));
        float body = smoothstep(0.009, 0.0, length(bp * vec2(2.0, 1.1)));
        alpha = max(alpha, max(wing, body));
    }
    return vec4(vec3(0.06, 0.06, 0.08), alpha * presence);
}

vec4 drawCampfire(vec2 p, vec2 anchor, float presence) {
    if (presence < 0.02) return vec4(0.0);
    vec2 q = p - anchor;
    float glow = exp(-dot(q, q) * 160.0);
    float flame = exp(-length((q - vec2(0.0, 0.015 + sin(u_time * 10.0) * 0.004)) * vec2(3.2, 1.6)) * 85.0);
    float flicker = 0.65 + 0.35 * noise2D(vec2(u_time * 3.5, 8.0));
    vec3 col = vec3(1.0, 0.50, 0.12) * glow * 0.85 + vec3(1.0, 0.82, 0.35) * flame * flicker;
    // Logs
    float log1 = smoothstep(0.012, 0.0, abs(q.y + 0.01) ) * step(abs(q.x), 0.035);
    col = mix(col, vec3(0.2, 0.1, 0.05), log1 * 0.8);
    float ember = 0.0;
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        vec2 ep = q - vec2(sin(u_time * 1.2 + fi * 2.1) * 0.025,
                           0.03 + fract(u_time * 0.3 + hash11(fi)) * 0.14);
        ember += smoothstep(0.007, 0.0, length(ep));
    }
    col += vec3(1.0, 0.45, 0.15) * ember * 0.7;
    float alpha = clamp(glow * 1.2 + flame + ember * 0.5 + log1, 0.0, 1.0) * presence;
    return vec4(col, alpha);
}

vec4 drawManiWall(vec2 p, vec2 anchor, float scale, float presence) {
    if (presence < 0.02) return vec4(0.0);
    vec2 q = (p - anchor) / scale;
    float wall = sdBox(q, vec2(0.58, 0.07));
    float mask = smoothstep(0.016, 0.0, wall);
    float stones = noise2D(q * 14.0);
    vec3 col = mix(vec3(0.42, 0.40, 0.36), vec3(0.28, 0.30, 0.38), stones);
    float paint = step(0.68, hash21(floor(q * vec2(9.0, 3.5)))) * smoothstep(0.05, 0.0, abs(q.y));
    col = mix(col, vec3(0.12, 0.22, 0.50), paint * mask);
    return vec4(col, mask * presence);
}

vec4 drawYak(vec2 p, vec2 anchor, float scale, float presence) {
    if (presence < 0.02) return vec4(0.0);
    vec2 q = (p - anchor) / scale;
    float body = sdBox(q - vec2(0.0, 0.02), vec2(0.16, 0.06));
    float head = sdCircle(q - vec2(0.16, 0.04), 0.05);
    float leg = 0.0;
    leg += smoothstep(0.02, 0.0, abs(q.x + 0.10)) * step(q.y, 0.0) * step(-0.12, q.y);
    leg += smoothstep(0.02, 0.0, abs(q.x - 0.08)) * step(q.y, 0.0) * step(-0.12, q.y);
    float horn = smoothstep(0.015, 0.0, abs(q.y - 0.10 - abs(q.x - 0.16) * 0.4)) *
                 step(abs(q.x - 0.16), 0.08);
    float mask = max(max(smoothstep(0.015, 0.0, min(body, head)), leg), horn * 0.8);
    return vec4(vec3(0.08, 0.06, 0.05), mask * presence);
}

// =============================================================================
// TERRAIN SHADING (directional, no hard outline stroke)
// =============================================================================
vec3 shadeTerrain(vec2 p, float h, vec3 baseCol, vec3 snowCol, vec3 lightCol,
                  vec2 lightDir, float snowAmt, float aerial, vec3 haze,
                  float detailScale)
{
    float below = max(0.0, h - p.y);
    // Isotropic rock detail (avoid vertical stretch)
    vec2 tuv = vec2(p.x * detailScale, p.y * detailScale * 1.1);
    float n1 = fbm3(tuv);
    float n2 = fbm3(tuv * 2.3 + vec2(3.1, 7.7));
    float n3 = noise2D(tuv * 5.0);

    float facing = 0.50 + 0.40 * (n1 - 0.5) + 0.15 * sign(lightDir.x) * (n2 - 0.5);
    facing = clamp(facing, 0.28, 1.15);

    vec3 rock = baseCol * facing;
    float cleft = smoothstep(0.60, 0.88, n2);
    rock = mix(rock, baseCol * 0.48, cleft * 0.55);
    // Gentle strata — angled, not vertical bands
    float strata = sin(p.x * 6.0 + p.y * 14.0 + n1 * 2.0) * 0.5 + 0.5;
    rock = mix(rock, rock * 1.12, strata * 0.15);

    // Patchy snow with softer falloff (no hard step edges / streaking)
    float heightSnow = smoothstep(0.32, 0.02, below);
    float steep = smoothstep(0.40, 0.80, n2);
    float snowPatch = smoothstep(0.45, 0.78, n1 * 0.55 + heightSnow * 0.55 + n3 * 0.25);
    snowPatch *= (1.0 - steep * 0.75) * snowAmt;
    rock = mix(rock, snowCol * (0.82 + 0.18 * facing), snowPatch);

    float crest = exp(-below * below * 500.0) * 0.35;
    rock += lightCol * crest * 0.25;
    rock *= mix(1.0, 0.68, smoothstep(0.0, 0.40, below));
    rock = mix(rock, haze, aerial);
    return rock;
}

// =============================================================================
// ENVIRONMENT
// =============================================================================
vec3 sampleEnvironment(
    vec2 p, float pan,
    vec3 skyTop, vec3 skyBot, vec3 sunColor, vec2 sunPos,
    float sunStrength, float moonStrength,
    float forest, float rhodo, float windIntensity, float starWeight,
    float cloudSea, float alpenglow, float godRays, float sceneDust,
    float snowFar, float snowMid
) {
    // Sky with warm horizon band
    float skyT = clamp(p.y * 0.52 + 0.40, 0.0, 1.0);
    vec3 horizon = mix(skyBot, sunColor, 0.22 * sunStrength);
    vec3 col = mix(horizon, skyTop, pow(skyT, 1.2));

    // Structured clouds (more vertical variation, less flat streaks)
    if (p.y > -0.08) {
        vec2 cUV = vec2(p.x * 1.2 - u_time * 0.018 - pan * 0.08, p.y * 3.2);
        float cl = fbm(cUV);
        float cl2 = fbm(cUV * 1.7 + 5.0);
        float clouds = smoothstep(0.48, 0.82, cl * 0.7 + cl2 * 0.3);
        clouds *= (0.20 + 0.40 * sceneDust) * smoothstep(-0.08, 0.5, p.y);
        // Soften at night
        clouds *= 1.0 - starWeight * 0.65;
        vec3 cCol = mix(vec3(0.50, 0.54, 0.62), vec3(0.93, 0.94, 0.96), 0.5 + p.y * 0.4);
        cCol = mix(cCol, sunColor, 0.18 * sunStrength * (1.0 - p.y));
        col = mix(col, cCol, clouds);
    }

    // Sea of clouds — soft continuous sheet with peak islands, not bubbly blobs
    if (cloudSea > 0.01) {
        float top = -0.06 + 0.07 * (fbm3(vec2(p.x * 1.2 - u_time * 0.025, 1.2)) - 0.5);
        float body = smoothstep(top + 0.28, top + 0.02, p.y) * smoothstep(-0.55, -0.10, p.y);
        vec2 sc = vec2(p.x * 1.6 - u_time * 0.03, p.y * 2.2);
        float dens = smoothstep(0.30, 0.70, fbm(sc) * 0.65 + fbm(sc * 2.1 + 3.0) * 0.35);
        // Soft underside shadow
        float under = smoothstep(top + 0.05, top + 0.20, p.y);
        vec3 seaCol = mix(vec3(0.62, 0.68, 0.78), vec3(0.94, 0.95, 0.97), dens);
        seaCol = mix(seaCol, seaCol * 0.75, under * 0.35);
        float hFarGate = getFarMassifH(p.x, pan);
        float punch = smoothstep(top, top + 0.12, p.y) * step(top, hFarGate) * step(p.y, hFarGate);
        col = mix(col, seaCol, body * dens * cloudSea * 0.78 * (1.0 - punch * 0.7));
    }

    // Sun
    float sunDist = length(p - sunPos);
    float sunDisc = smoothstep(0.045, 0.028, sunDist) * sunStrength;
    float sunGlow = (0.028 / (sunDist + 0.05)) * sunStrength;
    float halo = smoothstep(0.28, 0.04, sunDist) * 0.10 * sunStrength;
    col += sunColor * (sunDisc + sunGlow * 0.45 + halo);

    // Moon with simple maria
    vec2 moonPos = vec2(-0.50, 0.42);
    float moonDist = length(p - moonPos);
    float moonDisc = smoothstep(0.040, 0.028, moonDist) * moonStrength;
    float maria = noise2D((p - moonPos) * 28.0) * moonDisc;
    vec3 moonCol = mix(vec3(0.88, 0.90, 0.95), vec3(0.70, 0.72, 0.78), maria * 0.45);
    // Crescent softener for dawn moon
    float shade = smoothstep(0.055, 0.0, length(p - (moonPos + vec2(0.016, 0.01))));
    col += moonCol * moonDisc * (1.0 - shade * 0.4);
    col += vec3(0.85, 0.90, 1.0) * (0.018 / (moonDist + 0.06)) * moonStrength * 0.4;

    // Stars + milky way
    if (starWeight > 0.01 && p.y > 0.0) {
        float st = renderStars(p, 0.970);
        col += vec3(0.82, 0.88, 1.0) * st * starWeight;
        // Colorful bright stars
        col += vec3(1.0, 0.9, 0.7) * st * starWeight * 0.15;
        col += vec3(0.40, 0.50, 0.80) * milkyWay(p) * starWeight * 0.5;
        // Tapered meteor with bright head (not a flat graphic line)
        float mt = fract(u_time * 0.065);
        vec2 md = normalize(vec2(1.15, -0.48));
        vec2 mo = vec2(-1.0 + hash11(floor(u_time * 0.065)) * 0.9, 0.62);
        float along = dot(p - mo, md);
        float perp = abs(dot(p - mo, vec2(-md.y, md.x)));
        float headPos = mt * 1.45;
        float trail = smoothstep(0.55, 0.0, headPos - along) * step(along, headPos) *
                      smoothstep(0.014 * (0.3 + (headPos - along) * 1.5), 0.0, perp);
        float head = smoothstep(0.025, 0.0, length(p - (mo + md * headPos)));
        float life = smoothstep(0.0, 0.08, mt) * smoothstep(1.0, 0.72, mt);
        col += vec3(0.95, 0.97, 1.0) * (trail * 0.7 + head * 1.4) * starWeight * life;
    }

    // God rays
    if (godRays > 0.01 && sunStrength > 0.15) {
        float ang = atan(p.y - sunPos.y, p.x - sunPos.x);
        float rays = pow(max(0.0, noise2D(vec2(ang * 3.5, floor(u_time * 0.5)))), 2.5);
        float radial = smoothstep(1.0, 0.05, sunDist);
        col += sunColor * rays * radial * godRays * 0.18;
    }

    // Heights
    float hFar  = getFarMassifH(p.x, pan);
    float hDist = getDistantRidgeH(p.x, pan);
    float hMid  = getMidWithVeg(p.x, pan, forest, rhodo);
    float hNear = getNearWithVeg(p.x, pan, forest, rhodo);
    float hShore = getShoreH(p.x, pan);

    vec3 haze = mix(skyBot, skyTop, 0.45);
    vec3 snow = vec3(0.92, 0.94, 0.98);
    vec2 lightDir = normalize(sunPos - vec2(0.0, 0.0));

    // Far massifs
    if (p.y < hFar) {
        vec3 base = mix(haze, vec3(0.18, 0.20, 0.28), 0.40);
        vec3 layer = shadeTerrain(p, hFar, base, snow, sunColor, lightDir,
                                  snowFar, 0.50, haze, 5.5);
        // Alpenglow on high snow
        float ag = alpenglow * smoothstep(0.18, 0.0, hFar - p.y) * 0.5;
        layer = mix(layer, mix(sunColor, vec3(1.0, 0.55, 0.40), 0.45), ag);
        col = mix(col, layer, 0.68);
    }

    // Distant ridge
    if (p.y < hDist) {
        vec3 base = mix(haze, vec3(0.10, 0.12, 0.18), 0.65);
        vec3 layer = shadeTerrain(p, hDist, base, snow * 0.96, sunColor, lightDir,
                                  snowFar * 0.7, 0.32, haze, 7.0);
        float ag = alpenglow * smoothstep(0.14, 0.0, hDist - p.y) * 0.4;
        layer = mix(layer, mix(sunColor, vec3(1.0, 0.5, 0.35), 0.5), ag);
        col = mix(col, layer, 0.86);
    }

    // Valley fog
    if (p.y < hDist + 0.14 && p.y > -0.40) {
        vec2 fogUV = vec2(p.x * 1.8 - u_time * 0.04, p.y * 4.5);
        float fog = smoothstep(0.38, 0.75, fbm(fogUV));
        float mask = fog * 0.40 * (1.0 - smoothstep(hDist, hDist + 0.14, p.y));
        col = mix(col, mix(vec3(0.80, 0.84, 0.90), skyBot, 0.2), mask);
    }

    // Mid ridge / forest — rock shading when not forested; vegetated when forested
    if (p.y < hMid) {
        vec3 rockBase = mix(haze, vec3(0.14, 0.12, 0.14), 0.75);
        vec3 rockLayer = shadeTerrain(p, hMid, rockBase, snow * 0.9, sunColor, lightDir,
                                      snowMid + (1.0 - forest) * 0.35, 0.18, haze, 9.0);
        vec3 veg = vec3(0.04, 0.07, 0.045);
        veg = mix(veg, vec3(0.03, 0.09, 0.05), forest);
        veg = mix(veg, vec3(0.10, 0.05, 0.07), rhodo * 0.8);
        float bloom = fbm3(vec2(p.x * 22.0, p.y * 28.0));
        veg = mix(veg, vec3(0.55, 0.16, 0.28),
                  rhodo * smoothstep(0.62, 0.88, bloom) * 0.4 *
                  smoothstep(0.10, 0.0, hMid - p.y));
        float canopy = noise2D(vec2(p.x * 40.0, p.y * 20.0));
        veg *= 0.80 + 0.25 * canopy;
        float top = exp(-pow(hMid - p.y, 2.0) * 900.0);
        veg += sunColor * top * 0.14;
        veg = mix(veg, snow * 0.6, top * windIntensity * 0.22);
        veg *= 0.72 + 0.38 * clamp(0.5 + lightDir.x * 0.45 + canopy * 0.2, 0.0, 1.0);
        float vegMix = clamp(forest * 0.95 + rhodo * 0.7, 0.0, 1.0);
        vec3 mid = mix(rockLayer, veg, vegMix);
        // Sun-facing canopy rim (breaks flat silhouette)
        float sunRim = exp(-pow(hMid - p.y, 2.0) * 600.0) * sunStrength;
        mid += sunColor * sunRim * 0.22 * vegMix;
        col = mix(col, mid, 0.94);
    }

    // Near foothills
    if (p.y < hNear) {
        vec3 rockBase = vec3(0.10, 0.09, 0.10);
        vec3 rockLayer = shadeTerrain(p, hNear, rockBase, snow * 0.85, sunColor, lightDir,
                                      snowMid * 0.5, 0.08, haze, 12.0);
        vec3 veg = vec3(0.03, 0.045, 0.032);
        veg = mix(veg, vec3(0.025, 0.06, 0.035), forest);
        veg = mix(veg, vec3(0.08, 0.04, 0.05), rhodo * 0.5);
        float g = noise2D(vec2(p.x * 55.0, p.y * 35.0));
        veg *= 0.75 + 0.30 * g;
        float top = exp(-pow(hNear - p.y, 2.0) * 1100.0);
        veg += sunColor * top * 0.10;
        float vegMix = clamp(forest * 0.9 + rhodo * 0.5, 0.0, 1.0);
        col = mix(rockLayer, veg, vegMix);
    }

    // Shore / headland — strongly suppressed in forest so pines own the FG
    float shoreBias = forest * 0.22 + rhodo * 0.08;
    if (p.y < hShore - shoreBias) {
        float rockN = fbm3(vec2(p.x * 9.0, (hShore - p.y) * 16.0));
        vec3 shore = mix(vec3(0.08, 0.07, 0.06), vec3(0.20, 0.16, 0.13), rockN);
        float lichen = smoothstep(0.55, 0.85, noise2D(vec2(p.x * 24.0, p.y * 20.0)));
        shore = mix(shore, vec3(0.09, 0.13, 0.06), lichen * 0.45);
        float grass = step(0.70, noise2D(vec2(p.x * 50.0, floor((hShore - p.y) * 40.0)))) *
                      smoothstep(0.10, 0.0, hShore - shoreBias - p.y);
        shore = mix(shore, vec3(0.11, 0.15, 0.07), grass * 0.55);
        // Forest floor continuation
        shore = mix(shore, vec3(0.04, 0.06, 0.035), forest * 0.65);
        float top = exp(-pow(hShore - shoreBias - p.y, 2.0) * 1600.0);
        shore += sunColor * top * 0.12;
        col = shore;
    }

    // Spindrift — soft lofted particles only near crests (avoid full-frame scanlines)
    if (windIntensity > 0.01 && p.y > -0.25) {
        vec2 wUV = vec2(p.x * 3.2 - u_time * 1.6, p.y * 4.5 + u_time * 0.2);
        float drift = smoothstep(0.55, 0.88, fbm(wUV));
        float nearCrest = exp(-pow(p.y - hFar, 2.0) * 55.0) +
                          exp(-pow(p.y - hDist, 2.0) * 70.0);
        drift *= nearCrest * windIntensity * 0.85;
        col += vec3(0.88, 0.92, 0.98) * drift * 0.35;
        // Sparse flakes (tight Y frequency, low amplitude)
        float flakes = pow(noise2D(vec2(p.x * 2.5 - u_time * 2.2, p.y * 35.0)), 8.0);
        flakes *= nearCrest * 0.6 + 0.15;
        col += vec3(0.92, 0.95, 1.0) * flakes * windIntensity * 0.12;
    }

    return col;
}

// =============================================================================
// WATER
// =============================================================================
vec3 sampleWater(
    vec2 uv0, float pan, float waterLevel,
    vec3 skyTop, vec3 skyBot, vec3 sunColor, vec2 sunPos,
    float sunStrength, float moonStrength, float forest, float rhodo,
    float windIntensity, float starWeight, float cloudSea, float alpenglow,
    float godRays, float sceneDust, float snowFar, float snowMid,
    float s1, float s3, float s5, float s6, float s7, float s8
) {
    float depth = max(0.01, waterLevel - uv0.y);
    float amp = mix(0.005, 0.014, windIntensity);
    float w1 = sin(uv0.x * (16.0 / depth) + u_time * 2.0) * amp * depth;
    float w2 = sin(uv0.x * (28.0 / depth) - u_time * 2.8 + 2.0) * amp * 0.5 * depth;
    float w3 = (noise2D(vec2(uv0.x * 7.0 - u_time * 0.35, uv0.y * 18.0)) - 0.5) * 0.01 * depth;
    float distort = w1 + w2 + w3;

    // Break mirror perfection: lateral smear + slight blur via dual sample
    vec2 refA = vec2(uv0.x + distort * 0.55,
                     waterLevel + (waterLevel - uv0.y) * 0.88 + distort);
    vec2 refB = vec2(uv0.x + distort * 0.55 + 0.008,
                     waterLevel + (waterLevel - uv0.y) * 0.88 + distort * 0.9);

    vec3 r1 = sampleEnvironment(refA, pan, skyTop, skyBot, sunColor, sunPos,
        sunStrength, moonStrength, forest, rhodo, windIntensity, starWeight,
        cloudSea, alpenglow, godRays, sceneDust, snowFar, snowMid);
    vec3 r2 = sampleEnvironment(refB, pan, skyTop, skyBot, sunColor, sunPos,
        sunStrength, moonStrength, forest, rhodo, windIntensity, starWeight,
        cloudSea, alpenglow, godRays, sceneDust, snowFar, snowMid);
    vec3 reflected = mix(r1, r2, 0.45);

    vec3 deep = vec3(0.02, 0.07, 0.12) * (s1 * 1.1 + s3 * 0.7)
              + vec3(0.16, 0.05, 0.03) * s5
              + vec3(0.02, 0.03, 0.07) * (s6 + s7 + s8)
              + vec3(0.05, 0.09, 0.12) * clamp(1.0 - (s1+s3+s5+s6+s7+s8), 0.0, 1.0);

    float fresnel = 0.28 + 0.72 * pow(clamp(1.0 - depth * 1.6, 0.0, 1.0), 2.2);
    // Distance blur: deeper = more tint, less perfect reflection
    float clarity = clamp(1.0 - depth * 1.8, 0.25, 0.88);
    vec3 water = mix(deep, reflected, fresnel * clarity);

    // Specular glitter
    float glitter = pow(noise2D(vec2(uv0.x * 45.0, uv0.y * 70.0 + u_time * 1.5)), 10.0);
    water += sunColor * glitter * (sunStrength + moonStrength * 0.4) * 0.4 * fresnel;

    // Foam line
    float foam = smoothstep(0.02, 0.0, abs(uv0.y - waterLevel));
    foam *= 0.45 + 0.55 * noise2D(vec2(uv0.x * 28.0 - u_time * 0.4, 2.0));
    water += vec3(0.6, 0.72, 0.85) * foam * 0.5;

    // Submerged stones near shore
    if (depth < 0.11) {
        float stones = smoothstep(0.6, 0.9, noise2D(vec2(uv0.x * 16.0, depth * 45.0)));
        water = mix(water, vec3(0.14, 0.15, 0.16), stones * (1.0 - depth / 0.11) * 0.4);
    }

    if (sunStrength > 0.25 && depth < 0.22) {
        float cau = fbm3(vec2(uv0.x * 11.0 + u_time * 0.25, uv0.y * 16.0));
        water += sunColor * smoothstep(0.55, 0.85, cau) * 0.07 * (1.0 - depth / 0.22);
    }

    return water;
}

void main() {
    vec2 uv0 = (gl_FragCoord.xy * 2.0 - u_resolution.xy) / u_resolution.y;

    float bps = u_bpm / 60.0;
    float beat = u_time * bps;

    float s1 = 1.0 - smoothstep(20.0, 24.0, u_time);
    float s2 = smoothstep(21.0, 25.0, u_time) * (1.0 - smoothstep(45.0, 49.0, u_time));
    float s3 = smoothstep(46.0, 50.0, u_time) * (1.0 - smoothstep(69.0, 73.0, u_time));
    float s4 = smoothstep(70.0, 74.0, u_time) * (1.0 - smoothstep(93.0, 97.0, u_time));
    float s5 = smoothstep(94.0, 98.0, u_time) * (1.0 - smoothstep(117.0, 121.0, u_time));
    float s6 = smoothstep(118.0, 122.0, u_time) * (1.0 - smoothstep(141.0, 145.0, u_time));
    float s7 = smoothstep(142.0, 146.0, u_time) * (1.0 - smoothstep(166.0, 170.0, u_time));
    float s8 = smoothstep(167.0, 171.0, u_time);

    float forest   = s2 * 1.0 + s6 * 0.25 + s3 * 0.2;
    float rhodo    = s6 * 0.95 + s5 * 0.12;
    float wind     = s4 * 1.0 + s8 * 0.65 + s3 * 0.12;
    float lake     = s1 * 1.0 + s3 * 0.5 + s5 * 1.0 + s7 * 0.8 + s8 * 0.15;
    float stars    = s6 * 0.45 + s7 * 1.0 + s8 * 0.9 + s1 * 0.08;
    float cloudSea = s3 * 1.0 + s4 * 0.2;
    float alpenglow= s1 * 0.85 + s5 * 1.0 + s6 * 0.3;
    float godRays  = s2 * 0.85 + s5 * 0.35;
    float dust     = s2 * 0.45 + s3 * 0.65 + s4 * 0.35;
    float snowFar  = 0.65 + s1 * 0.25 + s4 * 0.3 + s7 * 0.3 + s3 * 0.2 + s5 * 0.15;
    float snowMid  = s4 * 0.45 + s1 * 0.25 + s7 * 0.2 + s3 * 0.15;

    // Palettes — brighter, more distinct per scene
    vec3 skyTop = vec3(0.0), skyBot = vec3(0.0);
    // 1 Gokyo dawn — brighter alpine morning, peach alpenglow
    skyTop += vec3(0.32, 0.48, 0.72) * s1; skyBot += vec3(0.95, 0.68, 0.42) * s1;
    // 2 Morning forest gold
    skyTop += vec3(0.35, 0.48, 0.72) * s2; skyBot += vec3(0.95, 0.72, 0.38) * s2;
    // 3 Crisp inversion blue
    skyTop += vec3(0.28, 0.48, 0.78) * s3; skyBot += vec3(0.70, 0.80, 0.90) * s3;
    // 4 Gale — cold overcast
    skyTop += vec3(0.42, 0.46, 0.52) * s4; skyBot += vec3(0.68, 0.70, 0.74) * s4;
    // 5 Crimson sunset
    skyTop += vec3(0.28, 0.12, 0.32) * s5; skyBot += vec3(0.95, 0.40, 0.12) * s5;
    // 6 Violet dusk
    skyTop += vec3(0.10, 0.08, 0.22) * s6; skyBot += vec3(0.42, 0.22, 0.40) * s6;
    // 7 Star night
    skyTop += vec3(0.02, 0.03, 0.10) * s7; skyBot += vec3(0.08, 0.10, 0.22) * s7;
    // 8 Midnight fade
    skyTop += vec3(0.01, 0.015, 0.04) * s8; skyBot += vec3(0.04, 0.05, 0.10) * s8;

    vec2 sunPos =
        vec2(0.62, 0.10) * s1 +
        vec2(0.35, 0.32) * s2 +
        vec2(0.48, 0.48) * s3 +
        vec2(0.15, 0.55) * s4 +
        vec2(0.58, 0.08) * s5 +
        vec2(0.70, 0.02) * s6 +
        vec2(0.3, 0.3) * (s7 + s8) * 0.01;

    float sunStrength = s1 * 0.55 + s2 * 1.05 + s3 * 0.75 + s4 * 0.25 + s5 * 1.15 + s6 * 0.15;
    float moonStrength = s1 * 0.12 + s6 * 0.8 + s7 * 1.0 + s8 * 0.7;

    vec3 sunColor = vec3(1.0, 0.93, 0.75);
    sunColor = mix(sunColor, vec3(1.0, 0.55, 0.22), clamp(s5 + s1 * 0.45, 0.0, 1.0));
    sunColor = mix(sunColor, vec3(0.90, 0.92, 0.95), clamp(s4 * 0.7, 0.0, 1.0));

    float pan = u_time * 0.018;

    // Water levels per scene — forest has little/no lake; soften shore dominance
    float waterLevel = -0.18;
    waterLevel = mix(waterLevel, -0.16, s1);
    waterLevel = mix(waterLevel, -0.62, s2);   // forest: water off-frame
    waterLevel = mix(waterLevel, -0.20, s3);
    waterLevel = mix(waterLevel, -0.55, s4);   // pass: land focused
    waterLevel = mix(waterLevel, -0.17, s5);
    waterLevel = mix(waterLevel, -0.52, s6);   // dusk ridges
    waterLevel = mix(waterLevel, -0.18, s7);
    waterLevel = mix(waterLevel, -0.38, s8);

    // Slight shoreline undulation so the horizon isn't a perfect ruler line
    float shoreWobble = sin(uv0.x * 3.5 + pan) * 0.006 + sin(uv0.x * 9.0) * 0.003;
    float waterLine = waterLevel + shoreWobble * lake;

    vec3 col;
    if (lake > 0.08 && uv0.y < waterLine) {
        vec3 water = sampleWater(uv0, pan, waterLine, skyTop, skyBot, sunColor, sunPos,
            sunStrength, moonStrength, forest, rhodo, wind, stars, cloudSea, alpenglow,
            godRays, dust, snowFar, snowMid, s1, s3, s5, s6, s7, s8);
        vec3 direct = sampleEnvironment(uv0, pan, skyTop, skyBot, sunColor, sunPos,
            sunStrength, moonStrength, forest, rhodo, wind, stars, cloudSea, alpenglow,
            godRays, dust, snowFar, snowMid);
        col = mix(direct, water, lake);
    } else {
        col = sampleEnvironment(uv0, pan, skyTop, skyBot, sunColor, sunPos,
            sunStrength, moonStrength, forest, rhodo, wind, stars, cloudSea, alpenglow,
            godRays, dust, snowFar, snowMid);
    }

    // ----- Props -----
    float flagPres = s1 * 0.95 + s4 * 1.0 + s5 * 0.9 + s7 * 0.55 + s8 * 0.45 + s3 * 0.5;
    // Anchor flags onto shore/ridge heights so they don't float
    float leftAnchorY = max(getShoreH(-0.75, pan), waterLevel + 0.02);
    float rightAnchorY = getMidWithVeg(-0.05, pan, forest, rhodo) - 0.02;
    vec4 flags = prayerFlags(uv0, vec2(-0.78, leftAnchorY + 0.06), vec2(-0.08, rightAnchorY),
                             0.35 + wind * 1.6, flagPres * 0.95);
    col = mix(col, flags.rgb, flags.a);

    float rLeftY = getMidWithVeg(0.35, pan, forest, rhodo);
    float rRightY = getShoreH(0.9, pan);
    vec4 flags2 = prayerFlags(uv0, vec2(0.30, rLeftY), vec2(0.92, max(rRightY, waterLevel) + 0.05),
                              0.5 + wind * 1.8, (s4 + s8 * 0.55 + s3 * 0.45) * 0.9);
    col = mix(col, flags2.rgb, flags2.a);

    vec4 stupa = drawStupa(uv0, vec2(0.58, max(waterLevel, getShoreH(0.58, pan)) + 0.01),
                           0.20, s5 * 0.95 + s6 * 0.5);
    // Warm sunset bounce on white plaster
    stupa.rgb = mix(stupa.rgb, stupa.rgb * mix(vec3(1.0), sunColor, 0.55), s5 * 0.7);
    col = mix(col, stupa.rgb, stupa.a);

    float lodgeY = getNearWithVeg(-0.55, pan, forest, rhodo) - 0.015;
    vec4 lodge = drawLodge(uv0, vec2(-0.58, lodgeY), 0.30,
                           s2 * 0.7 + s6 * 0.9 + s7 * 0.8,
                           s6 * 0.75 + s7 * 1.0 + s2 * 0.2);
    col = mix(col, lodge.rgb, lodge.a);

    vec4 cairn = drawCairn(uv0, vec2(0.12, getMidRidgeH(0.12, pan) - 0.02), 0.16, s4 * 0.95);
    col = mix(col, cairn.rgb, cairn.a);

    vec4 mani = drawManiWall(uv0, vec2(-0.32, max(waterLevel, getShoreH(-0.32, pan)) + 0.01),
                             0.18, s1 * 0.75 + s5 * 0.55);
    col = mix(col, mani.rgb, mani.a);

    vec4 boat = drawBoat(uv0, vec2(0.22, waterLevel - 0.035), 0.32,
                         (s1 * 0.9 + s5 * 0.65 + s7 * 0.35) * lake);
    col = mix(col, boat.rgb, boat.a);

    vec4 birds = drawBirds(uv0, s2 * 0.9 + s3 * 0.55 + s6 * 0.35 + s1 * 0.25);
    col = mix(col, birds.rgb, birds.a);

    vec4 yak = drawYak(uv0, vec2(0.4, getNearWithVeg(0.4, pan, forest, rhodo) - 0.01),
                       0.22, s2 * 0.55 + s4 * 0.4);
    col = mix(col, yak.rgb, yak.a);

    // Prop reflections in lake (simple mirrored overlays so objects aren't "pasted on")
    if (lake > 0.4 && uv0.y < waterLine) {
        float depth = waterLine - uv0.y;
        vec2 mir = vec2(uv0.x, waterLine + depth * 0.9);
        mir.x += sin(uv0.x * 20.0 + u_time * 2.0) * 0.004 * depth;
        vec4 rf = prayerFlags(mir, vec2(-0.78, leftAnchorY + 0.06), vec2(-0.08, rightAnchorY),
                              0.35 + wind * 1.6, flagPres * 0.5);
        vec4 rs = drawStupa(mir, vec2(0.58, max(waterLevel, getShoreH(0.58, pan)) + 0.01),
                            0.20, (s5 * 0.95 + s6 * 0.5) * 0.55);
        vec4 rb = drawBoat(mir, vec2(0.22, waterLevel - 0.035), 0.32,
                           (s1 * 0.9 + s5 * 0.65) * lake * 0.5);
        vec4 rl = drawLodge(mir, vec2(-0.58, lodgeY), 0.26,
                            (s7 * 0.75) * 0.45, s7 * 0.8);
        float fade = lake * clamp(1.0 - depth * 2.5, 0.15, 0.55);
        col = mix(col, rf.rgb * 0.7, rf.a * fade);
        col = mix(col, rs.rgb * 0.7, rs.a * fade);
        col = mix(col, rb.rgb * 0.7, rb.a * fade);
        col = mix(col, rl.rgb * 0.7, rl.a * fade);
    }

    // Campfire only on land scenes / above water
    float firePres = (s7 * 0.9 + s8 * 0.75) * step(waterLevel, -0.30);
    // Also allow on shore above water for night lake
    vec2 firePos = vec2(-0.72, mix(-0.52, waterLevel + 0.04, step(-0.25, waterLevel)));
    if (s7 + s8 > 0.2 && waterLevel > -0.30) {
        firePos = vec2(-0.70, max(waterLevel, getShoreH(-0.70, pan)) + 0.02);
        firePres = (s7 + s8) * 0.85;
    }
    vec4 fire = drawCampfire(uv0, firePos, firePres);
    col = mix(col, fire.rgb, fire.a);
    if (firePres > 0.1) {
        float bleed = exp(-length(uv0 - firePos) * 3.5) * firePres * 0.18;
        col += vec3(1.0, 0.45, 0.12) * bleed;
    }

    // Village lights (dusk)
    if (s6 + s7 * 0.4 > 0.15) {
        float lights = 0.0;
        for (int i = 0; i < 14; i++) {
            float fi = float(i);
            float lx = -0.95 + hash11(fi + 3.3) * 1.9;
            float ly = getNearWithVeg(lx, pan, forest, rhodo) - 0.02 - hash11(fi) * 0.03;
            float tw = 0.55 + 0.45 * sin(u_time * 2.2 + fi * 2.7);
            lights += smoothstep(0.011, 0.0, length(uv0 - vec2(lx, ly))) * tw;
        }
        col += vec3(1.0, 0.72, 0.35) * lights * (s6 * 0.85 + s7 * 0.35);
    }

    // Post
    col = max(col, 0.0);
    col = pow(col, vec3(0.92));
    float grain = (hash21(gl_FragCoord.xy + fract(u_time * 19.0)) - 0.5) * 0.028;
    col += grain;
    float vig = smoothstep(1.8, 0.42, length(uv0 * vec2(0.9, 1.05)));
    col *= mix(0.90, 1.0, vig);
    col *= 1.0 + sin(beat * TWO_PI) * 0.006;
    float fade = smoothstep(0.0, 3.0, u_time) * (1.0 - smoothstep(185.0, 189.0, u_time));
    col *= fade;
    col = col / (1.0 + col * 0.3);
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
"""

program = ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)
vbo = ctx.buffer(vertex_data)
vao = ctx.vertex_array(program, [(vbo, "2f", "in_vert")])
clock = pygame.time.Clock()

BPM = 72.0
TOTAL_DURATION = 189.0

if "u_bpm" in program:
    program["u_bpm"].value = float(BPM)
if "u_duration" in program:
    program["u_duration"].value = float(TOTAL_DURATION)


def scene_name_at(t: float) -> str:
    if t < 24.0:
        return "Scene 1: Gokyo Glacial Lake Dawn"
    if t < 48.0:
        return "Scene 2: Annapurna Pine Forest & Morning Sun"
    if t < 72.0:
        return "Scene 3: Sea of Clouds & Valley Inversion"
    if t < 96.0:
        return "Scene 4: High Mountain Pass Gale (Chorus)"
    if t < 120.0:
        return "Scene 5: Sacred Crimson Sunset Lake"
    if t < 144.0:
        return "Scene 6: Violet Dusk over Rhododendron Ridges"
    if t < 168.0:
        return "Scene 7: Celestial Starlight Peaks"
    return "Scene 8: Windswept Night Outro"


def render_frame(elapsed: float, w: int, h: int) -> None:
    ctx.clear(0.0, 0.0, 0.0, 1.0)
    if "u_resolution" in program:
        program["u_resolution"].value = (float(w), float(h))
    if "u_time" in program:
        program["u_time"].value = float(elapsed)
    vao.render()
    pygame.display.flip()


def save_screenshot(path: str) -> None:
    data = ctx.screen.read(components=3)
    surf = pygame.image.fromstring(data, (width, height), "RGB")
    surf = pygame.transform.flip(surf, False, True)
    pygame.image.save(surf, path)
    print(f"Saved screenshot: {path}")


def run_screenshot_mode(jobs: list[tuple[float, str]]) -> None:
    global width, height
    width, height = screen.get_size()
    ctx.viewport = (0, 0, width, height)
    for t, path in jobs:
        for _ in range(2):
            render_frame(t, width, height)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        save_screenshot(path)
        print(f"  t={t:.1f}s -> {scene_name_at(t)}")


def run_interactive() -> None:
    global width, height
    start_ticks = pygame.time.get_ticks()
    paused = False
    pause_start = 0.0
    elapsed_time = 0.0
    running = True

    print("=== Himalayan Landscape Visualizer: Wish You Were Here (72 BPM) ===")
    print(f"Duration: {int(TOTAL_DURATION // 60)}m {int(TOTAL_DURATION % 60):02d}s")
    print("Controls: ESC | SPACE | R | 1-8 scenes | S shot | LEFT/RIGHT scrub\n")

    while running:
        if not paused:
            elapsed_time = (pygame.time.get_ticks() - start_ticks) / 1000.0
        if elapsed_time > TOTAL_DURATION:
            start_ticks = pygame.time.get_ticks()
            elapsed_time = 0.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    start_ticks = pygame.time.get_ticks()
                    elapsed_time = 0.0
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                    if paused:
                        pause_start = pygame.time.get_ticks()
                    else:
                        start_ticks += pygame.time.get_ticks() - pause_start
                elif event.key == pygame.K_s:
                    save_screenshot(f"frame_{int(elapsed_time):03d}.png")
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    targets = [10.0, 36.0, 60.0, 84.0, 108.0, 132.0, 156.0, 178.0]
                    elapsed_time = targets[event.key - pygame.K_1]
                    start_ticks = pygame.time.get_ticks() - int(elapsed_time * 1000)
                elif event.key == pygame.K_LEFT:
                    elapsed_time = max(0.0, elapsed_time - 5.0)
                    start_ticks = pygame.time.get_ticks() - int(elapsed_time * 1000)
                elif event.key == pygame.K_RIGHT:
                    elapsed_time = min(TOTAL_DURATION, elapsed_time + 5.0)
                    start_ticks = pygame.time.get_ticks() - int(elapsed_time * 1000)
            elif event.type == pygame.VIDEORESIZE:
                width, height = screen.get_size()
                ctx.viewport = (0, 0, width, height)

        render_frame(elapsed_time, width, height)
        mins, secs = int(elapsed_time // 60), int(elapsed_time % 60)
        status = " [PAUSED]" if paused else ""
        pygame.display.set_caption(
            f"[{mins:02d}:{secs:02d} / 03:09] {scene_name_at(elapsed_time)}{status} | 72 BPM"
        )
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Himalayan landscape visualizer")
    parser.add_argument("--screenshot", nargs=2, metavar=("TIME", "PATH"), action="append")
    parser.add_argument("--screenshot-all", metavar="DIR")
    args = parser.parse_args()

    jobs: list[tuple[float, str]] = []
    if args.screenshot:
        for t_str, path in args.screenshot:
            jobs.append((float(t_str), path))
    if args.screenshot_all:
        mids = [10.0, 36.0, 60.0, 84.0, 108.0, 132.0, 156.0, 178.0]
        for i, t in enumerate(mids, 1):
            jobs.append((t, os.path.join(args.screenshot_all, f"scene_{i:02d}_t{int(t)}.png")))

    if jobs:
        run_screenshot_mode(jobs)
        pygame.quit()
        sys.exit(0)
    run_interactive()


if __name__ == "__main__":
    main()
