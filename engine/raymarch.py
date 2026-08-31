"""Advanced SDF raymarcher for Desecration Smile landscapes.

Inspired by procedural FBM terrain + domain-repeated structures,
with soft shadows, AO, atmospheric fog, and Uncharted-2 film tone.
"""

from __future__ import annotations

RAYMARCH_VS = """
#version 330 core
out vec2 v_uv;
void main() {
    vec2 pos = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    v_uv = pos;
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
"""

RAYMARCH_FS = """
#version 330 core
in vec2 v_uv;
layout(location = 0) out vec4 fragColor;

uniform vec2  u_resolution;
uniform float u_time;
uniform vec3  u_cam_pos;
uniform vec3  u_cam_target;
uniform vec3  u_cam_up;
uniform float u_fovy;
uniform float u_near;
uniform float u_far;

uniform int   u_landscape; // 0 cosmos 1 town 2 europe 3 bridge 4 desert
                           // 5 canyon 6 river 7 alpine 8 city 9 rooftop 10 outro
uniform float u_bus_z;
uniform int   u_stars;
uniform float u_sun_elev;
uniform vec3  u_sky_top;
uniform vec3  u_sky_horizon;
uniform vec3  u_sky_bottom;
uniform vec3  u_sun_color;
uniform vec3  u_light_dir;
uniform vec3  u_light_color;
uniform vec3  u_ambient;
uniform float u_fog_density;
uniform vec3  u_fog_color;

#define MAT_SKY       0.0
#define MAT_TERRAIN   1.0
#define MAT_ROAD      2.0
#define MAT_WATER     3.0
#define MAT_BUILDING  4.0
#define MAT_TREE      5.0
#define MAT_ROCK      6.0
#define MAT_SNOW      7.0
#define MAT_EMISSIVE  8.0
#define MAT_METAL     9.0
#define MAT_SAND     10.0
#define MAT_STEPS    11.0
#define MAT_TEMPLE   12.0
#define MAT_WOOD     13.0

float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float hash31(vec3 p) {
    return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453123);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash21(i + vec2(0, 0)), hash21(i + vec2(1, 0)), u.x),
        mix(hash21(i + vec2(0, 1)), hash21(i + vec2(1, 1)), u.x),
        u.y
    );
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 rot = mat2(0.8, 0.6, -0.6, 0.8);
    for (int i = 0; i < 5; ++i) {
        v += a * noise(p);
        p = rot * p * 2.05;
        a *= 0.5;
    }
    return v;
}

float fbm3(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 3; ++i) {
        v += a * noise(p);
        p *= 2.1;
        a *= 0.5;
    }
    return v;
}

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float sdCappedCylinder(vec3 p, float h, float r) {
    vec2 d = abs(vec2(length(p.xz), p.y)) - vec2(r, h);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

float sdCone(vec3 p, float h, float r1, float r2) {
    vec2 q = vec2(length(p.xz), p.y);
    vec2 k1 = vec2(r2, h);
    vec2 k2 = vec2(r2 - r1, 2.0 * h);
    vec2 ca = vec2(q.x - min(q.x, (q.y < 0.0) ? r1 : r2), abs(q.y) - h);
    vec2 cb = q - k1 + k2 * clamp(dot(k1 - q, k2) / dot(k2, k2), 0.0, 1.0);
    float s = (cb.x < 0.0 && ca.y < 0.0) ? -1.0 : 1.0;
    return s * sqrt(min(dot(ca, ca), dot(cb, cb)));
}

float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}

float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}

float opUnion(float d1, float d2) { return min(d1, d2); }
float opSub(float d1, float d2) { return max(d1, -d2); }

float roadBand(float x, float halfW) {
    return abs(x) - halfW;
}

// Analytical terrain height — mode dependent
float terrainHeight(vec2 xz) {
    float n = fbm(xz * 0.045);
    float n2 = fbm(xz * 0.12 + 17.0);
    float h = 0.0;

    if (u_landscape == 1 || u_landscape == 2) {
        // town / europe hills — keep a flat asphalt corridor
        float road = smoothstep(3.6, 8.5, abs(xz.x));
        h = (n * 3.8 + n2 * 1.2 - 0.4) * road;
    } else if (u_landscape == 3) {
        // bridge approach — water below, low banks
        h = n * 1.2 - 3.5;
        h += smoothstep(18.0, 28.0, abs(xz.x)) * (n2 * 6.0 + 2.0);
    } else if (u_landscape == 4) {
        // desert dunes with clear road cut
        float road = smoothstep(3.5, 9.0, abs(xz.x));
        h = (n * 4.2 + sin(xz.x * 0.07 + xz.y * 0.04) * 1.4 + n2 * 1.6) * road;
    } else if (u_landscape == 5) {
        // canyon — close walls with strata
        float wall = pow(max(0.0, abs(xz.x) - 4.8) / 5.5, 1.25) * 22.0;
        h = wall + n * 3.0 + n2 * 1.5;
        float floorMask = 1.0 - smoothstep(3.8, 5.2, abs(xz.x));
        h = mix(h, 0.0, floorMask);
        // cliff noise ledges
        if (abs(xz.x) > 5.0) h += sin(xz.y * 0.35 + abs(xz.x)) * 0.6;
    } else if (u_landscape == 6) {
        // river / ghats — water on -X, steps/bank, road corridor
        if (xz.x < -14.0) {
            h = -1.35 + 0.04 * sin(xz.y * 0.4 + u_time * 0.6);
        } else if (xz.x < -6.0) {
            float g = (-6.0 - xz.x) / 8.0;
            h = g * 4.5 + n * 0.3;
        } else {
            float road = smoothstep(3.6, 9.0, abs(xz.x));
            h = n * 2.0 * road;
        }
    } else if (u_landscape == 7) {
        // alpine terraces + distant peaks
        float road = smoothstep(4.0, 10.0, abs(xz.x));
        h = (n * 6.5 + n2 * 3.0 - 0.8) * road;
        float ridge = abs(xz.x) - 20.0;
        if (ridge > 0.0) h += ridge * 0.9 + n2 * 3.5;
    } else if (u_landscape == 8) {
        // city plaza
        float road = smoothstep(3.5, 8.0, abs(xz.x));
        h = n * 1.4 * road;
    } else if (u_landscape == 9) {
        // rooftop deck
        h = -8.0 + n * 3.0;
    } else if (u_landscape == 10) {
        // outro mountains
        h = n * 18.0 + n2 * 8.0 - 6.0;
    } else {
        h = -40.0;
    }
    return h;
}

vec2 vmin(vec2 a, vec2 b) {
    return (a.x < b.x) ? a : b;
}

float treeSDF(vec3 p, float h) {
    float trunk = sdCappedCylinder(p - vec3(0.0, h * 0.18, 0.0), h * 0.18, 0.12);
    float crown = sdCone(p - vec3(0.0, h * 0.55, 0.0), h * 0.45, 1.1, 0.05);
    return min(trunk, crown);
}

float deciduousSDF(vec3 p, float h) {
    float trunk = sdCappedCylinder(p - vec3(0.0, h * 0.22, 0.0), h * 0.22, 0.14);
    float crown = sdSphere(p - vec3(0.0, h * 0.72, 0.0), h * 0.42);
    return min(trunk, crown);
}

float houseSDF(vec3 p) {
    float body = sdBox(p - vec3(0.0, 1.1, 0.0), vec3(1.6, 1.1, 1.3));
    // gabled roof: box cut by diagonal planes
    float roof = sdBox(p - vec3(0.0, 2.6, 0.0), vec3(1.9, 0.7, 1.5));
    roof = max(roof, abs(p.x) * 0.55 + (p.y - 3.35));
    roof = max(roof, -(p.y - 2.15));
    return min(body, roof);
}

float pagodaSDF(vec3 p, float scale) {
    p /= scale;
    float d = 1e5;
    for (int i = 0; i < 4; ++i) {
        float y = float(i) * 1.35;
        float w = 2.2 - float(i) * 0.35;
        d = min(d, sdBox(p - vec3(0.0, 0.55 + y, 0.0), vec3(w * 0.55, 0.45, w * 0.55)));
        // eaves
        d = min(d, sdBox(p - vec3(0.0, 1.05 + y, 0.0), vec3(w * 0.85, 0.12, w * 0.85)));
    }
    d = min(d, sdCone(p - vec3(0.0, 5.6, 0.0), 0.9, 0.55, 0.02));
    return d * scale;
}

float templeSDF(vec3 p) {
    float base = sdBox(p - vec3(0.0, 1.0, 0.0), vec3(1.8, 1.0, 1.8));
    float tower = sdBox(p - vec3(0.0, 3.2, 0.0), vec3(0.7, 2.2, 0.7));
    float dome = sdSphere(p - vec3(0.0, 5.6, 0.0), 0.95);
    float spire = sdCone(p - vec3(0.0, 6.8, 0.0), 1.1, 0.35, 0.02);
    return min(min(base, tower), min(dome, spire));
}

float iwanSDF(vec3 p) {
    float wall = sdBox(p - vec3(0.0, 3.5, 0.0), vec3(5.0, 3.5, 1.2));
    float arch = sdCappedCylinder(p - vec3(0.0, 2.2, 0.0), 2.4, 2.0);
    // rotate arch axis to Z by swapping — open portal
    float portal = length(vec2(p.x, p.y - 2.0)) - 2.1;
    portal = max(portal, abs(p.z) - 1.5);
    return opSub(wall, max(-portal, -(p.y + 0.1)));
}

float bridgeDeckSDF(vec3 p) {
    float deck = sdBox(p - vec3(0.0, 4.0, 0.0), vec3(5.5, 0.25, 40.0));
    float towerL = sdBox(p - vec3(-4.2, 8.0, 8.0), vec3(0.45, 5.0, 0.45));
    float towerR = sdBox(p - vec3(4.2, 8.0, 8.0), vec3(0.45, 5.0, 0.45));
    float towerL2 = sdBox(p - vec3(-4.2, 8.0, -8.0), vec3(0.45, 5.0, 0.45));
    float towerR2 = sdBox(p - vec3(4.2, 8.0, -8.0), vec3(0.45, 5.0, 0.45));
    float cable = sdCapsule(p, vec3(-4.2, 12.5, 8.0), vec3(0.0, 4.4, 0.0), 0.06);
    cable = min(cable, sdCapsule(p, vec3(4.2, 12.5, 8.0), vec3(0.0, 4.4, 0.0), 0.06));
    cable = min(cable, sdCapsule(p, vec3(-4.2, 12.5, -8.0), vec3(0.0, 4.4, 0.0), 0.06));
    cable = min(cable, sdCapsule(p, vec3(4.2, 12.5, -8.0), vec3(0.0, 4.4, 0.0), 0.06));
    float d = min(deck, min(min(towerL, towerR), min(towerL2, towerR2)));
    return min(d, cable);
}

float rooftopSDF(vec3 p) {
    float deck = sdBox(p - vec3(0.0, -0.15, 0.0), vec3(9.0, 0.2, 9.0));
    float rail = sdBox(p - vec3(0.0, 0.55, 0.0), vec3(9.05, 0.55, 9.05));
    rail = opSub(rail, sdBox(p - vec3(0.0, 0.55, 0.0), vec3(8.6, 0.7, 8.6)));
    float carpet = sdBox(p - vec3(0.0, 0.02, 0.0), vec3(2.6, 0.04, 3.0));
    return min(min(deck, rail), carpet);
}

vec2 mapStructures(vec3 p) {
    vec2 res = vec2(1e5, MAT_SKY);
    float bz = u_bus_z;
    vec3 pl = p;
    pl.z -= bz; // landscape scrolls with bus

    if (u_landscape == 1 || u_landscape == 2) {
        // domain-repeated houses ahead of bus
        vec3 q = pl;
        float cellZ = 8.0;
        float idz = floor((q.z + 4.0) / cellZ);
        q.z = mod(q.z + 4.0, cellZ) - 4.0;
        // left and right rows, only when side of road
        if (abs(pl.x) > 9.5 && abs(pl.x) < 18.0 && idz > -1.0) {
            vec3 hp = q - vec3(sign(pl.x) * 12.5, terrainHeight(vec2(sign(pl.x) * 12.5, bz + idz * cellZ)), 0.0);
            float d = houseSDF(hp);
            res = vmin(res, vec2(d, MAT_BUILDING));
        }
        // trees
        float tcell = 6.0;
        float tid = floor((pl.z + 3.0) / tcell);
        vec3 tq = pl;
        tq.z = mod(pl.z + 3.0, tcell) - 3.0;
        float side = (hash21(vec2(tid, 3.1)) > 0.5) ? 1.0 : -1.0;
        float tx = side * (10.5 + hash21(vec2(tid, 7.7)) * 3.0);
        if (abs(pl.x - tx) < 4.0 && tid > -2.0) {
            float th = terrainHeight(vec2(tx, bz + tid * tcell));
            float ht = 4.5 + hash21(vec2(tid, 1.2)) * 2.0;
            float d = (u_landscape == 1)
                ? deciduousSDF(tq - vec3(tx, th, 0.0), ht)
                : treeSDF(tq - vec3(tx, th, 0.0), ht);
            res = vmin(res, vec2(d, MAT_TREE));
        }
        // stone arch ahead
        vec3 bp = pl - vec3(0.0, 0.0, 48.0);
        float arch = sdBox(bp - vec3(0.0, 2.5, 0.0), vec3(5.5, 2.5, 1.2));
        float hole = length(vec2(bp.x, bp.y - 1.6)) - 2.4;
        hole = max(hole, abs(bp.z) - 1.5);
        arch = opSub(arch, max(-hole, -bp.y));
        res = vmin(res, vec2(arch, MAT_ROCK));
    }

    if (u_landscape == 3) {
        res = vmin(res, vec2(bridgeDeckSDF(pl), MAT_METAL));
        // distant skyline boxes
        for (int i = 0; i < 5; ++i) {
            float x = -18.0 + float(i) * 9.0;
            float hh = 6.0 + hash21(vec2(float(i), 2.0)) * 8.0;
            float d = sdBox(pl - vec3(x, hh * 0.5 - 2.0, -42.0), vec3(2.2, hh * 0.5, 2.2));
            res = vmin(res, vec2(d, MAT_BUILDING));
        }
        // balloons
        float bcell = 14.0;
        float bid = floor((pl.z + 7.0) / bcell);
        vec3 bq = pl;
        bq.z = mod(pl.z + 7.0, bcell) - 7.0;
        float bx = (hash21(vec2(bid, 4.4)) - 0.5) * 20.0;
        float by = 10.0 + hash21(vec2(bid, 8.1)) * 6.0;
        float dbal = sdSphere(bq - vec3(bx, by, 0.0), 1.4);
        dbal = min(dbal, sdCappedCylinder(bq - vec3(bx, by - 2.2, 0.0), 0.35, 0.45));
        res = vmin(res, vec2(dbal, MAT_EMISSIVE));
    }

    if (u_landscape == 4) {
        // iwan arches along road — keep clear of asphalt corridor
        float cell = 28.0;
        float id = floor((pl.z + 14.0) / cell);
        vec3 q = pl;
        q.z = mod(pl.z + 14.0, cell) - 14.0;
        if (id > 0.0 && abs(q.z) < 6.0) {
            // offset to roadside so portal frames the road
            float d = iwanSDF(q - vec3(0.0, 0.0, 0.0));
            // push distance up near road center to avoid eating the lane
            d += max(0.0, 3.2 - abs(pl.x)) * 0.35;
            res = vmin(res, vec2(d, MAT_TEMPLE));
        }
    }

    if (u_landscape == 6) {
        // temples on +X bank, boats as capsules on water
        float cell = 14.0;
        float id = floor((pl.z + 7.0) / cell);
        vec3 q = pl;
        q.z = mod(pl.z + 7.0, cell) - 7.0;
        if (id > -2.0) {
            float d = templeSDF(q - vec3(10.5, 0.0, 0.0));
            res = vmin(res, vec2(d, MAT_TEMPLE));
            if (mod(abs(id), 2.0) < 0.5) {
                d = pagodaSDF(q - vec3(13.5, 0.0, 2.5), 0.9);
                res = vmin(res, vec2(d, MAT_TEMPLE));
            }
            // small shrine on ghat terrace
            d = sdBox(q - vec3(-7.5, 3.2, 0.0), vec3(0.8, 1.2, 0.8));
            d = min(d, sdCone(q - vec3(-7.5, 5.0, 0.0), 0.7, 0.55, 0.05));
            res = vmin(res, vec2(d, MAT_TEMPLE));
        }
        // diya emissive dots along ghats
        float dcell = 2.8;
        float did = floor((pl.z + 1.4) / dcell);
        vec3 dq = pl;
        dq.z = mod(pl.z + 1.4, dcell) - 1.4;
        float dx = -7.5 - hash21(vec2(did, 1.0)) * 2.5;
        float dy = max(0.2, terrainHeight(vec2(dx, bz + did * dcell))) + 0.2;
        float dd = sdSphere(dq - vec3(dx, dy, 0.0), 0.14);
        res = vmin(res, vec2(dd, MAT_EMISSIVE));
        // boat
        float boat = sdCapsule(pl - vec3(-26.0, -1.0, mod(pl.z + u_time * 0.35, 36.0) - 18.0),
                               vec3(-1.6, 0.0, 0.0), vec3(1.6, 0.0, 0.0), 0.4);
        res = vmin(res, vec2(boat, MAT_WOOD));
    }

    if (u_landscape == 7) {
        float tcell = 5.5;
        float tid = floor((pl.z + 2.75) / tcell);
        vec3 tq = pl;
        tq.z = mod(pl.z + 2.75, tcell) - 2.75;
        float side = (hash21(vec2(tid, 9.0)) > 0.5) ? 1.0 : -1.0;
        float tx = side * (11.0 + hash21(vec2(tid, 2.2)) * 4.0);
        float th = terrainHeight(vec2(tx, bz + tid * tcell));
        float d = treeSDF(tq - vec3(tx, th, 0.0), 5.0 + hash21(vec2(tid, 0.3)) * 2.5);
        res = vmin(res, vec2(d, MAT_TREE));
        // prayer flag poles
        float fcell = 9.0;
        float fid = floor((pl.z + 4.5) / fcell);
        vec3 fq = pl;
        fq.z = mod(pl.z + 4.5, fcell) - 4.5;
        float fx = -14.0;
        float fh = terrainHeight(vec2(fx, bz + fid * fcell));
        float pole = sdCappedCylinder(fq - vec3(fx, fh + 2.0, 0.0), 2.0, 0.05);
        res = vmin(res, vec2(pole, MAT_METAL));
        float flag = sdBox(fq - vec3(fx + 0.7, fh + 3.2, 0.0), vec3(0.7, 0.25, 0.02));
        res = vmin(res, vec2(flag, MAT_EMISSIVE));
    }

    if (u_landscape == 8) {
        // pagodas and houses
        float d = pagodaSDF(pl - vec3(-14.0, 0.0, 28.0), 1.0);
        res = vmin(res, vec2(d, MAT_TEMPLE));
        d = pagodaSDF(pl - vec3(-12.5, 0.0, 48.0), 0.85);
        res = vmin(res, vec2(d, MAT_TEMPLE));
        d = pagodaSDF(pl - vec3(15.0, 0.0, 55.0), 0.8);
        res = vmin(res, vec2(d, MAT_TEMPLE));
        float cell = 7.0;
        float id = floor((pl.z + 3.5) / cell);
        vec3 q = pl;
        q.z = mod(pl.z + 3.5, cell) - 3.5;
        if (abs(pl.x) > 10.0 && id > 1.0) {
            float hx = sign(pl.x) * (12.0 + hash21(vec2(id, 5.0)));
            d = houseSDF(q - vec3(hx, 0.0, 0.0));
            res = vmin(res, vec2(d, MAT_BUILDING));
        }
    }

    if (u_landscape == 9) {
        res = vmin(res, vec2(rooftopSDF(p), MAT_BUILDING));
        // city night skyline
        for (int i = 0; i < 8; ++i) {
            float x = -24.0 + float(i) * 7.0;
            float hh = 5.0 + hash21(vec2(float(i), 11.0)) * 10.0;
            float d = sdBox(p - vec3(x, hh * 0.5 - 8.0, -48.0), vec3(2.0, hh * 0.5, 2.0));
            res = vmin(res, vec2(d, MAT_BUILDING));
            if (hash21(vec2(float(i), 3.3)) > 0.55) {
                float win = sdBox(p - vec3(x, hh * 0.35 - 6.0, -46.5), vec3(1.5, hh * 0.25, 0.1));
                res = vmin(res, vec2(win, MAT_EMISSIVE));
            }
        }
        float d = pagodaSDF(p - vec3(-18.0, -7.0, -36.0), 1.35);
        res = vmin(res, vec2(d, MAT_TEMPLE));
        d = pagodaSDF(p - vec3(16.0, -7.0, -34.0), 1.15);
        res = vmin(res, vec2(d, MAT_TEMPLE));
        // lamps
        for (int i = 0; i < 4; ++i) {
            float ang = float(i) * 1.57;
            vec3 lp = vec3(cos(ang) * 5.5, 0.55, sin(ang) * 5.5);
            float d = sdBox(p - lp, vec3(0.15, 0.35, 0.15));
            res = vmin(res, vec2(d, MAT_EMISSIVE));
        }
    }

    if (u_landscape == 10) {
        for (int i = 0; i < 10; ++i) {
            float x = -20.0 + float(i) * 4.5;
            float hh = 1.5 + hash21(vec2(float(i), 0.7)) * 3.0;
            float d = sdBox(p - vec3(x, hh * 0.5, 6.0), vec3(1.4, hh * 0.5, 1.4));
            res = vmin(res, vec2(d, MAT_BUILDING));
        }
    }

    return res;
}

vec2 map(vec3 p) {
    vec2 res = vec2(1e5, MAT_SKY);

    if (u_landscape == 0) {
        // cosmos — no solid ground nearby
        res = vmin(res, vec2(p.y + 80.0, MAT_TERRAIN));
        return res;
    }

    // Terrain heightfield
    float th = terrainHeight(p.xz);
    float dTerrain = p.y - th;
    float matT = MAT_TERRAIN;
    if (u_landscape == 4) matT = MAT_SAND;
    if (u_landscape == 5) matT = MAT_ROCK;
    if (u_landscape == 7 && th > 9.0) matT = MAT_SNOW;
    if (u_landscape == 6 && p.x < -14.0) {
        float wave = sin(p.x * 1.5 + u_time * 1.2) * 0.03 + cos(p.z * 1.1 + u_time * 0.9) * 0.03;
        dTerrain = p.y - (-1.35 + wave);
        matT = MAT_WATER;
    } else if (u_landscape == 6 && p.x < -6.0) {
        matT = MAT_STEPS;
    }
    if (u_landscape == 3 && th < -1.0) {
        float wave = sin(p.x * 0.8 + u_time) * 0.05;
        dTerrain = p.y - (-3.2 + wave);
        matT = MAT_WATER;
    }
    res = vmin(res, vec2(dTerrain, matT));

    // Road ribbon — flat strip that always wins the corridor
    if (u_landscape >= 1 && u_landscape <= 8) {
        float roadY = 0.05;
        if (u_landscape == 3) roadY = 4.05;
        float halfW = (u_landscape == 5) ? 4.4 : 3.6;
        if (u_landscape == 8) halfW = 3.2;
        if (abs(p.x) < halfW) {
            float dRoad = abs(p.y - roadY) - 0.05;
            dRoad = max(dRoad, abs(p.x) - halfW);
            res = vmin(res, vec2(dRoad, MAT_ROAD));
        }
        // gravel shoulder
        if (abs(p.x) >= halfW && abs(p.x) < halfW + 1.4) {
            float dSh = p.y - (roadY - 0.02 + 0.08 * noise(p.xz * 2.0));
            res = vmin(res, vec2(dSh, MAT_ROCK));
        }
    }

    // Structures
    res = vmin(res, mapStructures(p));

    // Explicit canyon cliffs (heightfields undersample vertical faces)
    if (u_landscape == 5) {
        float nW = fbm3(vec2(p.z * 0.1, p.y * 0.15)) * 2.5;
        // Left cliff across the road (camera sits on +X and looks inward)
        float left = sdBox(p - vec3(-8.5 - nW * 0.4, 11.0, u_bus_z), vec3(3.8 + nW, 14.0, 120.0));
        // Right cliff behind / beside chase cam
        float right = sdBox(p - vec3(18.5 + nW * 0.4, 11.0, u_bus_z), vec3(6.0 + nW, 14.0, 120.0));
        left = opSub(left, sdBox(p - vec3(-6.2, 3.5, u_bus_z), vec3(1.4, 1.0, 120.0)));
        left = opSub(left, sdBox(p - vec3(-6.0, 7.5, u_bus_z), vec3(1.2, 0.7, 120.0)));
        res = vmin(res, vec2(min(left, right), MAT_ROCK));
    }

    // Distant mountain silhouette for europe/alpine/outro
    if (u_landscape == 2 || u_landscape == 7 || u_landscape == 10) {
        float mz = (u_landscape == 10) ? -80.0 : (u_bus_z - 110.0);
        vec2 mxz = vec2(p.x * 0.35, (p.z - mz) * 0.08);
        float mh = fbm(mxz * 0.6) * 28.0 + fbm(mxz * 1.5) * 10.0 - 4.0;
        if (u_landscape == 10) mh *= 1.3;
        float dM = p.y - mh;
        // only far field
        float far = smoothstep(60.0, 100.0, abs(p.z - u_bus_z));
        dM += (1.0 - far) * 20.0;
        float mm = (mh > 16.0) ? MAT_SNOW : MAT_ROCK;
        res = vmin(res, vec2(dM, mm));
    }

    return res;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.002, 0.0);
    return normalize(vec3(
        map(p + e.xyy).x - map(p - e.xyy).x,
        map(p + e.yxy).x - map(p - e.yxy).x,
        map(p + e.yyx).x - map(p - e.yyx).x
    ));
}

float softShadow(vec3 ro, vec3 rd, float mint, float maxt, float k) {
    float res = 1.0;
    float t = mint;
    for (int i = 0; i < 32; ++i) {
        float h = map(ro + rd * t).x;
        res = min(res, k * h / t);
        t += clamp(h, 0.05, 0.6);
        if (res < 0.02 || t > maxt) break;
    }
    return clamp(res, 0.0, 1.0);
}

float calcAO(vec3 p, vec3 n) {
    float occ = 0.0;
    float sca = 1.0;
    for (int i = 0; i < 5; ++i) {
        float h = 0.01 + 0.15 * float(i);
        float d = map(p + n * h).x;
        occ += (h - d) * sca;
        sca *= 0.85;
    }
    return clamp(1.0 - 1.8 * occ, 0.0, 1.0);
}

vec3 skyColor(vec3 rd) {
    float elev = rd.y;
    vec3 col = mix(u_sky_horizon, u_sky_top, smoothstep(0.0, 0.65, elev));
    col = mix(u_sky_bottom, col, smoothstep(-0.25, 0.05, elev));
    // sun disk
    vec3 sunDir = normalize(vec3(u_light_dir.x, max(0.02, u_sun_elev), u_light_dir.z));
    float sun = pow(max(0.0, dot(rd, sunDir)), 256.0);
    col += u_sun_color * sun * 1.8;
    col += u_sun_color * pow(max(0.0, dot(rd, sunDir)), 8.0) * 0.25;
    if (u_stars == 1) {
        // sharp pin-prick stars (avoid large blocky cells)
        vec3 sp = rd * 220.0;
        float s = hash31(floor(sp));
        float sparkle = step(0.9965, s) * pow(fract(s * 47.0), 4.0);
        col += vec3(0.9, 0.93, 1.0) * sparkle * 2.5;
        float band = exp(-abs(rd.y) * 10.0) * 0.035;
        col += vec3(0.22, 0.28, 0.5) * band * noise(rd.xz * 50.0);
    }
    return col;
}

vec3 materialAlbedo(float matId, vec3 p, vec3 n) {
    if (matId == MAT_ROAD) {
        float dash = step(0.55, fract(p.z * 0.15));
        float center = smoothstep(0.12, 0.0, abs(p.x));
        vec3 asphalt = vec3(0.08, 0.08, 0.09);
        return mix(asphalt, vec3(0.75, 0.72, 0.55), center * dash * 0.9);
    }
    if (matId == MAT_WATER) {
        return vec3(0.04, 0.12, 0.18);
    }
    if (matId == MAT_TERRAIN) {
        float rock = noise(p.xz * 1.2);
        vec3 grass = vec3(0.18, 0.32, 0.12);
        vec3 dirt = vec3(0.28, 0.2, 0.12);
        return mix(dirt, grass, clamp(n.y * 0.9 + rock * 0.2, 0.0, 1.0));
    }
    if (matId == MAT_SAND) {
        float d = noise(p.xz * 0.8);
        return mix(vec3(0.62, 0.48, 0.28), vec3(0.78, 0.62, 0.38), d);
    }
    if (matId == MAT_ROCK) {
        float r = noise(p.xz * 1.5 + p.y);
        return mix(vec3(0.35, 0.28, 0.22), vec3(0.55, 0.42, 0.32), r);
    }
    if (matId == MAT_SNOW) {
        return mix(vec3(0.55, 0.58, 0.62), vec3(0.92, 0.94, 0.97), clamp(n.y, 0.0, 1.0));
    }
    if (matId == MAT_BUILDING) {
        return vec3(0.55, 0.48, 0.4) * (0.85 + 0.15 * noise(p.xz * 2.0));
    }
    if (matId == MAT_TREE) {
        return (n.y > 0.35) ? vec3(0.12, 0.28, 0.1) : vec3(0.28, 0.18, 0.1);
    }
    if (matId == MAT_TEMPLE) {
        return vec3(0.72, 0.55, 0.32) * (0.9 + 0.1 * noise(p.xy * 3.0));
    }
    if (matId == MAT_METAL) {
        return vec3(0.35, 0.36, 0.38);
    }
    if (matId == MAT_STEPS) {
        return vec3(0.55, 0.42, 0.32);
    }
    if (matId == MAT_EMISSIVE) {
        return vec3(1.0, 0.7, 0.3);
    }
    if (matId == MAT_WOOD) {
        return vec3(0.35, 0.22, 0.12);
    }
    return vec3(0.4);
}

vec3 tonemapUncharted2(vec3 x) {
    float A = 0.15, B = 0.50, C = 0.10, D = 0.20, E = 0.02, F = 0.30;
    return ((x * (A * x + C * B) + D * E) / (x * (A * x + B) + D * F)) - E / F;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / u_resolution.y;

    vec3 ro = u_cam_pos;
    vec3 ta = u_cam_target;
    vec3 cw = normalize(ta - ro);
    vec3 cp = normalize(u_cam_up);
    vec3 cu = normalize(cross(cw, cp));
    vec3 cv = normalize(cross(cu, cw));
    float fl = 1.0 / tan(radians(u_fovy) * 0.5);
    vec3 rd = normalize(uv.x * cu + uv.y * cv + fl * cw);

    float t = 0.0;
    float tMax = 160.0;
    vec2 hit = vec2(-1.0);
    vec3 p = ro;
    for (int i = 0; i < 128; ++i) {
        p = ro + rd * t;
        hit = map(p);
        if (abs(hit.x) < 0.0015 * t || t > tMax) break;
        t += hit.x * 0.55;
    }

    vec3 sky = skyColor(rd);
    vec3 color = sky;
    float depthDist = tMax;

    if (t < tMax && hit.y > 0.0) {
        depthDist = t;
        p = ro + rd * t;
        vec3 n = calcNormal(p);
        vec3 ldir = normalize(-u_light_dir);
        float dif = clamp(dot(n, ldir), 0.0, 1.0);
        float sha = softShadow(p + n * 0.02, ldir, 0.05, 40.0, 8.0);
        float ao = calcAO(p, n);
        float spe = pow(clamp(dot(reflect(-ldir, n), -rd), 0.0, 1.0), 48.0);

        vec3 albedo = materialAlbedo(hit.y, p, n);
        if (hit.y == MAT_EMISSIVE) {
            color = albedo * (4.0 + 2.0 * sin(u_time * 3.0 + p.x));
        } else if (hit.y == MAT_WATER) {
            vec3 ref = reflect(rd, n);
            vec3 refCol = skyColor(ref);
            float fre = pow(clamp(1.0 + dot(rd, n), 0.0, 1.0), 3.0);
            color = mix(albedo * (dif * sha * u_light_color + u_ambient * ao), refCol, fre * 0.85);
        } else {
            color = albedo * (dif * sha * u_light_color + u_ambient * ao);
            if (hit.y == MAT_METAL || hit.y == MAT_ROAD) {
                color += spe * u_light_color * 0.35 * sha;
            }
        }

        // atmospheric fog — gentler so mid-ground structures read
        float fogAmt = u_fog_density;
        if (u_landscape == 5 || u_landscape == 6 || u_landscape == 7) fogAmt *= 0.55;
        float fog = 1.0 - exp(-fogAmt * t * 0.18 - fogAmt * 0.006 * t * t);
        color = mix(color, mix(u_fog_color, sky, 0.45), clamp(fog, 0.0, 0.88));
    }

    // Mild film curve — post stack also grades; keep HDR-ish for bloom
    color = max(color, vec3(0.0));
    fragColor = vec4(color, 1.0);

    // Write depth for billboard compositing
    float viewZ = t * dot(rd, cw);
    // OpenGL perspective depth from eye-space z (negative in RH view; use positive distance along forward)
    float zEye = -viewZ; // typically negative if cw points forward and we use RH... 
    // We want geometric distance along view axis:
    float z = max(u_near, depthDist * max(0.001, dot(rd, cw)));
    float A = u_far / (u_far - u_near);
    float B = -(u_far * u_near) / (u_far - u_near);
    float ndcZ = A + B / z;
    gl_FragDepth = clamp(ndcZ, 0.0, 1.0);
}
"""
