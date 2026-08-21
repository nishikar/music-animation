import pygame
import math
import random
import sys
import argparse
import subprocess
import os
from pathlib import Path

# ==============================================================================
# CONFIGURATION & DISPLAY
# ==============================================================================
WIDTH, HEIGHT = 960, 540
FPS = 60
SONG_DURATION_SEC = 213.0  # 3 minutes 33 seconds

# Scene timeline (seconds)
SCENE_SOLO_START = 135.0
SCENE_SOLO_END = 145.0      # ~10s guitar solo cataclysm
SCENE_GROUND_BATTLE_END = 175.0
SCENE_AFTERMATH_START = 175.0

COLOR_BLACK = (8, 8, 12)
COLOR_DEEP_RED = (90, 10, 15)
COLOR_AMBER = (230, 125, 25)
COLOR_YELLOW = (255, 220, 90)
COLOR_SMOKE = (35, 30, 35)
COLOR_SEARCHLIGHT = (255, 245, 200)
COLOR_EMBER = (255, 140, 30)
COLOR_SILHOUETTE = (10, 10, 14)
COLOR_FLASH = (245, 240, 230)

# ==============================================================================
# FFMPEG EXPORT
# ==============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EXPORT_PATH = SCRIPT_DIR / "war_pigs.mp4"
AUDIO_PATH = SCRIPT_DIR / "war_pigs.mp3"


class FfmpegRecorder:
    """Pipe raw RGB frames to ffmpeg and mux optional audio into an MP4."""

    def __init__(self, output_path, fps=FPS, width=WIDTH, height=HEIGHT, audio_path=None):
        self.output_path = Path(output_path)
        self.frame_size = width * height * 3
        self._proc = None
        self.frames_written = 0

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{width}x{height}", "-pix_fmt", "rgb24",
            "-r", str(fps), "-i", "-",
        ]
        self._has_audio = audio_path is not None and Path(audio_path).is_file()
        if self._has_audio:
            cmd.extend(["-i", str(audio_path)])

        cmd.extend([
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
        ])
        if self._has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.extend(["-t", str(SONG_DURATION_SEC)])
        cmd.append(str(self.output_path))

        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    def write_frame(self, surface):
        if self._proc is None or self._proc.stdin is None:
            return
        raw = pygame.image.tostring(surface, "RGB")
        self._proc.stdin.write(raw)
        self.frames_written += 1

    def close(self):
        if self._proc is None:
            return
        if self._proc.stdin:
            self._proc.stdin.close()
        stderr = self._proc.stderr.read().decode("utf-8", errors="replace") if self._proc.stderr else ""
        rc = self._proc.wait()
        self._proc = None
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed (exit {rc}):\n{stderr[-2000:]}")
        return self.output_path


def parse_args():
    parser = argparse.ArgumentParser(description="War Pigs cinematic animation")
    parser.add_argument(
        "--export", "-e", action="store_true",
        help="Render to MP4 via ffmpeg pipe instead of interactive playback",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=DEFAULT_EXPORT_PATH,
        help=f"Output MP4 path (default: {DEFAULT_EXPORT_PATH.name} in script folder)",
    )
    parser.add_argument(
        "--no-preview", action="store_true",
        help="Headless export (no window); sets SDL_VIDEODRIVER=dummy",
    )
    parser.add_argument(
        "--hud", action="store_true",
        help="Include on-screen HUD in exported video (hidden by default)",
    )
    return parser.parse_args()


# ==============================================================================
# UTILITY HELPERS
# ==============================================================================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp_color(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def fire_color_for_life(life_ratio):
    """White-hot core cooling to ember as explosion ages."""
    if life_ratio > 0.75:
        return lerp_color((255, 255, 240), COLOR_YELLOW, (1.0 - life_ratio) * 4)
    if life_ratio > 0.45:
        return lerp_color(COLOR_YELLOW, COLOR_AMBER, (0.75 - life_ratio) / 0.3)
    if life_ratio > 0.2:
        return lerp_color(COLOR_AMBER, COLOR_EMBER, (0.45 - life_ratio) / 0.25)
    return lerp_color(COLOR_EMBER, (60, 20, 10), (0.2 - life_ratio) / 0.2)


# ==============================================================================
# CAMERA & ENVIRONMENT SYSTEMS
# ==============================================================================
class CameraShake:
    """Impulse-based shake with exponential decay — feels tied to blast force."""

    def __init__(self):
        self.amp_x = 0.0
        self.amp_y = 0.0
        self.freq_x = 18.0
        self.freq_y = 22.0
        self.decay = 0.88
        self.time = 0.0

    def add_impulse(self, strength, direction_x=0.0):
        self.amp_x = min(18.0, self.amp_x + strength * (0.6 + abs(direction_x) * 0.4))
        self.amp_y = min(18.0, self.amp_y + strength * 0.85)
        self.freq_x = random.uniform(14.0, 26.0)
        self.freq_y = random.uniform(16.0, 28.0)

    def update(self):
        self.time += 1.0 / FPS
        self.amp_x *= self.decay
        self.amp_y *= self.decay
        if self.amp_x < 0.15:
            self.amp_x = 0.0
        if self.amp_y < 0.15:
            self.amp_y = 0.0

    def offset(self):
        if self.amp_x <= 0 and self.amp_y <= 0:
            return 0, 0
        sx = int(math.sin(self.time * self.freq_x * math.pi * 2) * self.amp_x)
        sy = int(math.cos(self.time * self.freq_y * math.pi * 2) * self.amp_y)
        return sx, sy


class ScorchMark:
    """Persistent ground crater/scorch from explosions."""

    def __init__(self, x, y, radius):
        self.x = int(x)
        self.y = int(y)
        self.radius = radius
        self.alpha = 200

    def update(self):
        self.alpha = max(0, self.alpha - 0.4)

    def draw(self, surface):
        if self.alpha <= 0:
            return
        r = int(self.radius)
        s = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (25, 18, 12, int(self.alpha * 0.7)), (4, r // 2, r * 2, r))
        pygame.draw.ellipse(s, (12, 10, 8, int(self.alpha * 0.5)), (8, r // 2 + 4, r * 2 - 8, r - 6))
        surface.blit(s, (self.x - r - 4, self.y - r // 2))


class SmokePuff:
    """Billowing smoke with buoyancy, drag, and turbulent expansion."""

    def __init__(self, x, y, vx, vy, radius, life, color=COLOR_SMOKE, grow=0.35):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = radius
        self.max_life = life
        self.life = life
        self.color = color
        self.grow = grow
        self.turbulence = random.uniform(-0.4, 0.4)

    def update(self):
        self.life -= 1
        self.vx *= 0.97
        self.vy -= 0.04  # buoyancy
        self.vx += self.turbulence * 0.08
        self.x += self.vx
        self.y += self.vy
        self.radius += self.grow

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surface):
        if not self.alive:
            return
        alpha = int(180 * (self.life / self.max_life))
        r = max(1, int(self.radius))
        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (r + 2, r + 2), r)
        surface.blit(s, (int(self.x) - r - 2, int(self.y) - r - 2))


class SparkParticle:
    """Hot debris fragment with gravity and air drag."""

    def __init__(self, x, y, speed, angle, life, color=COLOR_EMBER, size=2):
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = 0.18

    def update(self):
        self.life -= 1
        self.vx *= 0.985
        self.vy += self.gravity
        self.x += self.vx
        self.y += self.vy

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surface):
        if not self.alive:
            return
        alpha = int(255 * (self.life / self.max_life))
        s = pygame.Surface((self.size * 2 + 2, self.size * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.size + 1, self.size + 1), self.size)
        surface.blit(s, (int(self.x) - self.size - 1, int(self.y) - self.size - 1))


# Shared atmospheric particle pools (updated each frame)
smoke_puffs = []
spark_particles = []
scorch_marks = []


def spawn_explosion_debris(x, y, count, speed_range=(2.0, 7.0)):
    for _ in range(count):
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(*speed_range)
        life = random.randint(18, 45)
        color = random.choice([COLOR_EMBER, COLOR_AMBER, (180, 80, 30), (90, 85, 80)])
        spark_particles.append(SparkParticle(x, y, speed, angle, life, color, random.randint(1, 3)))


def spawn_smoke_column(x, y, count, spread=1.0):
    for _ in range(count):
        smoke_puffs.append(SmokePuff(
            x + random.uniform(-8, 8) * spread,
            y + random.uniform(-4, 4),
            random.uniform(-0.6, 0.6) * spread,
            random.uniform(-1.2, -0.3),
            random.uniform(4, 10),
            random.randint(40, 90),
            color=(random.randint(30, 45), random.randint(28, 38), random.randint(32, 42)),
            grow=random.uniform(0.2, 0.5),
        ))


# ==============================================================================
# PROCEDURAL PARTICLE & ACTOR SYSTEMS
# ==============================================================================
class Explosion:
    def __init__(self, x, y, max_radius=45):
        self.x = float(x)
        self.y = float(y)
        self.radius = 2.0
        self.max_radius = float(max_radius)
        self.growth = random.uniform(3.0, 5.5)
        self.age = 0
        self.max_age = int(max_radius * 2.8)
        self.shockwave_r = 4.0
        self.shockwave_speed = random.uniform(5.5, 8.0)
        self.flash_alpha = 255
        spawn_explosion_debris(x, y, random.randint(12, 22), (3.0, 9.0))
        spawn_smoke_column(x, y - 5, random.randint(6, 12), spread=1.4)
        scorch_marks.append(ScorchMark(x, y, int(max_radius * 0.65)))

    @property
    def alpha(self):
        fade_start = self.max_age * 0.55
        if self.age < fade_start:
            return 255
        return max(0, int(255 * (1.0 - (self.age - fade_start) / (self.max_age - fade_start))))

    @property
    def alive(self):
        return self.alpha > 0

    def update(self):
        self.age += 1
        if self.radius < self.max_radius:
            # Ease-out expansion — fast initial blast, slowing at edge
            t = self.radius / self.max_radius
            self.radius += self.growth * (1.0 - t * 0.65)
        self.shockwave_r += self.shockwave_speed
        self.flash_alpha = max(0, self.flash_alpha - 18)

    def draw(self, surface):
        life_ratio = 1.0 - self.age / self.max_age
        alpha = self.alpha
        if alpha <= 0:
            return

        r = int(self.radius)
        fire_color = fire_color_for_life(life_ratio)

        # Outer turbulent fire shell
        fire_surf = pygame.Surface((r * 2 + 12, r * 2 + 12), pygame.SRCALPHA)
        cx, cy = r + 6, r + 6
        for ring in range(3, 0, -1):
            ring_r = int(r * (ring / 3.0))
            ring_alpha = int(alpha * (0.35 + ring * 0.2))
            c = fire_color if ring > 1 else lerp_color(fire_color, (40, 15, 8), 0.5)
            pygame.draw.circle(fire_surf, (*c, ring_alpha), (cx, cy), ring_r)

        # White-hot core (only early phase)
        if life_ratio > 0.5:
            core_r = max(2, int(r * 0.35 * life_ratio))
            pygame.draw.circle(fire_surf, (255, 255, 230, alpha), (cx, cy), core_r)

        surface.blit(fire_surf, (int(self.x) - r - 6, int(self.y) - r - 6))

        # Shockwave ring with attenuation
        sw_max = self.max_radius * 2.4
        if self.shockwave_r < sw_max:
            sw_r = int(self.shockwave_r)
            sw_surf = pygame.Surface((sw_r * 2 + 6, sw_r * 2 + 6), pygame.SRCALPHA)
            sw_alpha = int(220 * (1.0 - self.shockwave_r / sw_max) ** 1.5)
            pygame.draw.circle(sw_surf, (*COLOR_FLASH, sw_alpha), (sw_r + 3, sw_r + 3), sw_r, max(1, int(3 * (1 - self.shockwave_r / sw_max))))
            surface.blit(sw_surf, (int(self.x) - sw_r - 3, int(self.y) - sw_r - 3))

        # Initial flash bloom
        if self.flash_alpha > 0:
            flash_r = int(self.max_radius * 0.4)
            flash_surf = pygame.Surface((flash_r * 2, flash_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (255, 250, 220, self.flash_alpha), (flash_r, flash_r), flash_r)
            surface.blit(flash_surf, (int(self.x) - flash_r, int(self.y) - flash_r), special_flags=pygame.BLEND_ADD)


class FlakBurst:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.radius = random.uniform(4, 10)
        self.max_radius = random.uniform(28, 48)
        self.alpha = 255
        self.age = 0
        self.secondary_delay = random.randint(4, 10)
        self.secondary_fired = False
        # Fragmentation sparks
        for _ in range(random.randint(8, 16)):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1.5, 5.5)
            spark_particles.append(SparkParticle(x, y, speed, angle, random.randint(8, 22), COLOR_YELLOW, 1))
        spawn_smoke_column(x, y, random.randint(3, 6), spread=0.8)

    def update(self):
        self.age += 1
        t = self.radius / self.max_radius
        self.radius += 1.2 * (1.0 - t * 0.7)
        self.alpha = max(0, 255 - self.age * 5)
        if not self.secondary_fired and self.age >= self.secondary_delay:
            self.secondary_fired = True
            for _ in range(random.randint(4, 8)):
                angle = random.uniform(0, math.pi * 2)
                spark_particles.append(SparkParticle(
                    self.x + random.uniform(-6, 6), self.y + random.uniform(-6, 6),
                    random.uniform(0.8, 3.0), angle, random.randint(6, 14), COLOR_AMBER, 1
                ))

    def draw(self, surface):
        if self.alpha <= 0:
            return
        r = int(self.radius)
        s = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        cx, cy = r + 4, r + 4
        # Layered smoke puff
        pygame.draw.circle(s, (*COLOR_SMOKE, int(self.alpha * 0.55)), (cx, cy), r)
        pygame.draw.circle(s, (55, 48, 50, int(self.alpha * 0.35)), (cx, cy), int(r * 0.7))
        if self.radius < self.max_radius * 0.55:
            pygame.draw.circle(s, (*COLOR_AMBER, int(self.alpha * 0.85)), (cx, cy), max(2, int(r * 0.3)))
            pygame.draw.circle(s, (*COLOR_YELLOW, int(self.alpha * 0.6)), (cx, cy), max(1, int(r * 0.15)))
        surface.blit(s, (int(self.x) - r - 4, int(self.y) - r - 4))


class Bomb:
    def __init__(self, x, y, target_y=HEIGHT - 60):
        self.x = float(x)
        self.y = float(y)
        self.vx = random.uniform(2.5, 4.0)
        self.vy = 1.0
        self.gravity = 0.22
        self.drag = 0.998
        self.target_y = target_y
        self.exploded = False
        self.angle = math.atan2(self.vy, self.vx)
        self.spin = random.uniform(-0.12, 0.12)
        self.trail_timer = 0
        self.length = 10.0

    def update(self):
        self.vy += self.gravity
        self.vx *= self.drag
        self.vy *= self.drag
        self.x += self.vx
        self.y += self.vy
        self.angle += self.spin
        self.trail_timer += 1
        if self.trail_timer % 2 == 0:
            smoke_puffs.append(SmokePuff(
                self.x, self.y, self.vx * -0.15, self.vy * -0.1,
                random.uniform(2, 4), random.randint(12, 24),
                color=(50, 48, 52), grow=0.15
            ))
        if self.y >= self.target_y:
            self.exploded = True

    def draw(self, surface):
        px, py = int(self.x), int(self.y)
        cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)
        # Fuselage body
        nose = (px + cos_a * self.length * 0.5, py + sin_a * self.length * 0.5)
        tail = (px - cos_a * self.length * 0.5, py - sin_a * self.length * 0.5)
        perp = (-sin_a * 3, cos_a * 3)
        body = [
            (nose[0], nose[1]),
            (tail[0] + perp[0], tail[1] + perp[1]),
            (tail[0] - perp[0], tail[1] - perp[1]),
        ]
        pygame.draw.polygon(surface, (30, 28, 32), body)
        pygame.draw.polygon(surface, COLOR_SILHOUETTE, body, 1)
        # Tail fins
        fin_len = 4
        for sign in (-1, 1):
            fx = tail[0] + sign * perp[0] * 1.2 - cos_a * fin_len
            fy = tail[1] + sign * perp[1] * 1.2 - sin_a * fin_len
            pygame.draw.line(surface, COLOR_SILHOUETTE, tail, (fx, fy), 2)


class Plane:
    def __init__(self, x, y, speed, plane_type="bomber"):
        self.x = float(x)
        self.y = float(y)
        self.speed = speed
        self.plane_type = plane_type
        self.drop_timer = random.randint(20, 60)
        self.altitude_bob_phase = random.uniform(0, math.pi * 2)
        self.bank = 0.0
        self.prev_x = x
        self.contrail_timer = 0
        self.prop_phase = random.uniform(0, math.pi * 2)

    def update(self, bombs_list, current_sec=0.0):
        self.prev_x = self.x
        self.x += self.speed
        # Subtle altitude bob from turbulence
        self.y += math.sin(current_sec * 1.8 + self.altitude_bob_phase) * 0.25
        # Bank into velocity changes (simulated turn feel)
        target_bank = clamp(self.speed * 0.04, -0.35, 0.35)
        self.bank += (target_bank - self.bank) * 0.08

        self.contrail_timer += 1
        if self.contrail_timer % 3 == 0 and self.plane_type == "bomber":
            smoke_puffs.append(SmokePuff(
                self.x - 20, self.y + 2, -self.speed * 0.05, random.uniform(-0.2, 0.1),
                random.uniform(2, 5), random.randint(30, 60), color=(180, 185, 195), grow=0.12
            ))

        if self.plane_type == "bomber":
            self.drop_timer -= 1
            if self.drop_timer <= 0:
                bombs_list.append(Bomb(self.x, self.y + 10))
                self.drop_timer = random.randint(45, 90)

        self.prop_phase += abs(self.speed) * 0.35

    def draw(self, surface):
        px, py = int(self.x), int(self.y)
        bank_offset = int(self.bank * 18)

        if self.plane_type == "bomber":
            # Engine glow
            for eng_y in (-12, 12):
                glow = pygame.Surface((14, 8), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (255, 160, 60, 90), (0, 0, 14, 8))
                surface.blit(glow, (px - 8, py + eng_y + bank_offset - 4))

            # Heavy Bomber Silhouette with bank
            body = [
                (px + 35, py + bank_offset), (px - 25, py - 4 + bank_offset),
                (px - 35, py - 12 + bank_offset), (px - 30, py + bank_offset),
                (px - 25, py + 4 + bank_offset)
            ]
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, body)
            wing = [
                (px - 4, py - 20 + bank_offset), (px + 10, py + bank_offset),
                (px - 4, py + 20 + bank_offset), (px - 10, py + bank_offset)
            ]
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, wing)
            pygame.draw.rect(surface, COLOR_SILHOUETTE, (px - 2, py - 14 + bank_offset, 8, 4))
            pygame.draw.rect(surface, COLOR_SILHOUETTE, (px - 2, py + 10 + bank_offset, 8, 4))

            # Propeller blur disc
            prop_r = 5
            prop_surf = pygame.Surface((prop_r * 2, prop_r * 2), pygame.SRCALPHA)
            pygame.draw.line(prop_surf, (80, 80, 85, 120), (prop_r, 2), (prop_r, prop_r * 2 - 2), 2)
            pygame.draw.line(prop_surf, (80, 80, 85, 120), (2, prop_r), (prop_r * 2 - 2, prop_r), 2)
            surface.blit(prop_surf, (px + 32, py + bank_offset - prop_r))
        else:
            # Fighter with sharper bank
            body = [
                (px + 22, py + bank_offset), (px - 14, py - 3 + bank_offset),
                (px - 20, py - 7 + bank_offset), (px - 16, py + bank_offset),
                (px - 14, py + 3 + bank_offset)
            ]
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, body)
            wing = [
                (px + 2, py - 12 + bank_offset * 1.3), (px + 8, py + bank_offset),
                (px + 2, py + 12 + bank_offset * 1.3), (px - 4, py + bank_offset)
            ]
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, wing)
            # Afterburner on fast fighters
            if abs(self.speed) > 7:
                ab = pygame.Surface((16, 6), pygame.SRCALPHA)
                pygame.draw.ellipse(ab, (255, 130, 40, 140), (0, 0, 16, 6))
                surface.blit(ab, (px - 28, py + bank_offset - 3))


class TankRecoilSystem:
    """Spring-damped barrel recoil instead of binary snap."""

    def __init__(self):
        self.recoil_pos = 0.0
        self.recoil_vel = 0.0
        self.fire_cooldown = 0
        self.muzzle_smoke = 0
        self.casing_x = None
        self.casing_vx = 0.0
        self.casing_vy = 0.0
        self.casing_life = 0
        self.track_offset = 0.0

    def update(self, cycle):
        self.fire_cooldown = max(0, self.fire_cooldown - 1)
        fire_phase = math.sin(cycle * 6.0)
        if fire_phase > 0.92 and self.fire_cooldown == 0:
            self.recoil_vel = 14.0
            self.fire_cooldown = 18
            self.muzzle_smoke = 25
            self.casing_x = 0.0
            self.casing_vx = random.uniform(2.0, 4.0)
            self.casing_vy = random.uniform(-3.5, -2.0)
            self.casing_life = 30

        # Spring back toward rest
        self.recoil_vel += -self.recoil_pos * 0.35
        self.recoil_vel *= 0.72
        self.recoil_pos += self.recoil_vel
        self.recoil_pos = max(0.0, self.recoil_pos)
        self.muzzle_smoke = max(0, self.muzzle_smoke - 1)
        self.track_offset = (self.track_offset + 1.8) % 20

        if self.casing_life > 0:
            self.casing_x += self.casing_vx
            self.casing_vy += 0.25
            self.casing_life -= 1

    @property
    def barrel_offset(self):
        return int(self.recoil_pos)

    @property
    def is_firing(self):
        return self.recoil_pos > 2.0 or self.muzzle_smoke > 18


tank_recoil = TankRecoilSystem()


# ==============================================================================
# PROCEDURAL SCENE DRAWING ROUTINES
# ==============================================================================
def draw_gradient_sky(surface, top_color, bottom_color):
    for y in range(0, HEIGHT, 2):
        ratio = y / HEIGHT
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y), 2)


def draw_parallax_clouds(surface, current_sec, layer, color, alpha, speed, y_base):
    """Drifting cloud layers for depth."""
    cloud_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(5):
        cx = ((i * 220 - current_sec * speed * 30) % (WIDTH + 200)) - 100
        cy = y_base + (i % 3) * 35 + layer * 20
        w, h = 90 + layer * 30, 28 + layer * 8
        pygame.draw.ellipse(cloud_surf, (*color, alpha), (int(cx), cy, w, h))
        pygame.draw.ellipse(cloud_surf, (*color, alpha), (int(cx) + w // 3, cy - 8, w // 2, h))
    surface.blit(cloud_surf, (0, 0))


def draw_war_table_scene(surface, current_sec):
    """Scene: Shadowy generals leaning over a strategy map."""
    draw_gradient_sky(surface, (12, 8, 12), (35, 15, 18))

    # Swinging ceiling light with flicker
    light_angle = math.sin(current_sec * 2.2) * 0.35
    flicker = 0.85 + 0.15 * math.sin(current_sec * 17.3) + random.uniform(-0.04, 0.04)
    lamp_x = WIDTH // 2 + math.sin(light_angle) * 90
    lamp_y = 60 + math.cos(light_angle) * 15
    pygame.draw.line(surface, (40, 40, 40), (WIDTH // 2, 0), (int(lamp_x), int(lamp_y)), 2)

    # Overhead light cone with flickering intensity
    cone_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    p1 = (lamp_x, lamp_y)
    p2 = (lamp_x - 240 + math.sin(light_angle) * 60, HEIGHT)
    p3 = (lamp_x + 240 + math.sin(light_angle) * 60, HEIGHT)
    cone_alpha = int(45 * flicker)
    pygame.draw.polygon(cone_surf, (255, 230, 160, cone_alpha), [p1, p2, p3])
    # Inner brighter core
    p2i = (lamp_x - 120 + math.sin(light_angle) * 30, HEIGHT)
    p3i = (lamp_x + 120 + math.sin(light_angle) * 30, HEIGHT)
    pygame.draw.polygon(cone_surf, (255, 240, 200, int(25 * flicker)), [p1, p2i, p3i])
    surface.blit(cone_surf, (0, 0))

    # Lamp bulb glow
    bulb = pygame.Surface((40, 40), pygame.SRCALPHA)
    pygame.draw.circle(bulb, (255, 220, 140, int(120 * flicker)), (20, 20), 12)
    surface.blit(bulb, (int(lamp_x) - 20, int(lamp_y) - 20), special_flags=pygame.BLEND_ADD)

    # The Strategic Table
    table_y = HEIGHT - 130
    pygame.draw.polygon(surface, (18, 14, 18), [
        (160, HEIGHT), (220, table_y), (WIDTH - 220, table_y), (WIDTH - 160, HEIGHT)
    ])
    # Glowing Map Grid & Battle Markers
    for gx in range(260, WIDTH - 240, 50):
        pygame.draw.line(surface, (90, 30, 30), (gx, table_y + 10), (gx - 30, HEIGHT - 15), 1)
    for gy in range(table_y + 20, HEIGHT - 10, 25):
        pygame.draw.line(surface, (90, 30, 30), (200 + (gy - table_y), gy), (WIDTH - 200 - (gy - table_y), gy), 1)

    # Chess / War Tokens
    tokens = [(380, table_y + 35), (450, table_y + 55), (540, table_y + 40), (590, table_y + 65)]
    for tx, ty in tokens:
        pygame.draw.circle(surface, COLOR_AMBER, (tx, ty), 4)

    # General Left (Puffing cigar with animated smoke)
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
        (130, HEIGHT), (170, table_y - 40), (220, table_y + 20), (260, HEIGHT)
    ])
    pygame.draw.circle(surface, COLOR_SILHOUETTE, (195, table_y - 55), 20)
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [(180, table_y - 75), (225, table_y - 65), (175, table_y - 60)])
    ember_glow = int(180 + 75 * (0.5 + 0.5 * math.sin(current_sec * 3.0)))
    pygame.draw.circle(surface, (255, ember_glow // 2, 20), (218, table_y - 48), 2)
    if int(current_sec * 10) % 8 == 0:
        smoke_puffs.append(SmokePuff(220, table_y - 52, 0.3, -0.6, 3, 20, color=(60, 55, 50), grow=0.2))

    # General Right (Pointing at map — arm sways slightly)
    arm_sway = math.sin(current_sec * 1.5) * 8
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
        (WIDTH - 140, HEIGHT), (WIDTH - 190, table_y - 35), (WIDTH - 240, table_y + 30), (WIDTH - 280, HEIGHT)
    ])
    pygame.draw.circle(surface, COLOR_SILHOUETTE, (WIDTH - 210, table_y - 50), 22)
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [(WIDTH - 190, table_y - 70), (WIDTH - 235, table_y - 62), (WIDTH - 185, table_y - 56)])
    pygame.draw.line(surface, COLOR_SILHOUETTE, (WIDTH - 230, table_y - 20), (WIDTH - 360 + arm_sway, table_y + 45), 9)

    # Cast shadows from generals onto table
    shadow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(shadow_surf, (0, 0, 0, 60), [
        (195, table_y + 5), (260, table_y + 5), (240, table_y + 40), (170, table_y + 30)
    ])
    pygame.draw.polygon(shadow_surf, (0, 0, 0, 55), [
        (WIDTH - 210, table_y + 8), (WIDTH - 280, table_y + 8), (WIDTH - 300, table_y + 45), (WIDTH - 230, table_y + 35)
    ])
    surface.blit(shadow_surf, (0, 0))


def draw_tank_and_artillery(surface, x, y, cycle, recoil_system=None):
    """Draws a heavy tracked tank with spring recoil, animated tracks, and muzzle effects."""
    recoil = recoil_system if recoil_system is not None else tank_recoil
    recoil.update(cycle)
    offset = recoil.barrel_offset

    # Animated track treads
    track_y = y - 4
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
        (x - 60, y), (x + 60, y), (x + 50, y - 22), (x - 50, y - 22)
    ])
    for tx in range(int(x - 48), int(x + 48), 10):
        notch_x = tx + int(recoil.track_offset) % 10
        pygame.draw.line(surface, (25, 25, 30), (notch_x, track_y - 18), (notch_x, track_y - 2), 2)
    # Road wheels
    for wx in range(int(x - 40), int(x + 45), 16):
        pygame.draw.circle(surface, (18, 18, 22), (wx, track_y - 8), 6, 2)

    # Hull & Turret
    pygame.draw.rect(surface, COLOR_SILHOUETTE, (x - 45, y - 38, 90, 18))
    pygame.draw.arc(surface, COLOR_SILHOUETTE, (x - 30, y - 56, 55, 35), 0, math.pi, 16)

    # Recoiling gun barrel
    barrel_start = (x + 15 - offset, y - 44)
    barrel_end = (x + 85 - offset, y - 56)
    pygame.draw.line(surface, COLOR_SILHOUETTE, barrel_start, barrel_end, 6)

    # Muzzle flash & smoke
    if recoil.is_firing:
        flash_x, flash_y = barrel_end[0] + 8, barrel_end[1] - 2
        flash_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(flash_surf, (255, 240, 180, 200), (30, 30), 22)
        pygame.draw.circle(flash_surf, (255, 200, 80, 150), (30, 30), 32)
        surface.blit(flash_surf, (int(flash_x) - 30, int(flash_y) - 30), special_flags=pygame.BLEND_ADD)
        if recoil.muzzle_smoke > 15:
            spawn_smoke_column(flash_x, flash_y, 2, spread=0.3)

    # Ejected shell casing
    if recoil.casing_life > 0:
        cx = x + 10 + recoil.casing_x
        cy = y - 30 + (30 - recoil.casing_life) * 0.5
        pygame.draw.rect(surface, COLOR_AMBER, (int(cx), int(cy), 4, 2))


def draw_soldier(surface, x, y, cycle_time, scale=1.0):
    """Inverse-kinematics-style march: body bob, knee bend, arm swing."""
    h = 55 * scale
    stride = cycle_time * 2.0
    # Body vertical bob — peaks at mid-stride
    bob = abs(math.sin(stride)) * 3 * scale
    base_y = y - bob

    # Leg phase — opposite legs
    leg_phase_l = math.sin(stride)
    leg_phase_r = math.sin(stride + math.pi)

    hip_y = base_y - h * 0.45
    hip = (int(x), int(hip_y))

    def leg_points(phase):
        knee_bend = max(0, phase) * 14 * scale
        foot_x = x + phase * 14 * scale
        knee_x = x + phase * 7 * scale
        knee_y = hip_y + h * 0.22 + knee_bend * 0.3
        foot_y = base_y
        return (int(knee_x), int(knee_y)), (int(foot_x), int(foot_y))

    knee_l, foot_l = leg_points(leg_phase_l)
    knee_r, foot_r = leg_points(leg_phase_r)

    head_r = int(6 * scale)
    head_center = (int(x), int(base_y - h + head_r))
    torso_top = (int(x), int(base_y - h + head_r * 2))
    torso_bottom = hip

    # Legs (draw behind body)
    pygame.draw.line(surface, COLOR_SILHOUETTE, hip, knee_l, int(4 * scale))
    pygame.draw.line(surface, COLOR_SILHOUETTE, knee_l, foot_l, int(3 * scale))
    pygame.draw.line(surface, COLOR_SILHOUETTE, hip, knee_r, int(4 * scale))
    pygame.draw.line(surface, COLOR_SILHOUETTE, knee_r, foot_r, int(3 * scale))

    # Torso with slight forward lean
    lean_x = int(2 * scale)
    pygame.draw.line(surface, COLOR_SILHOUETTE, (torso_top[0] + lean_x, torso_top[1]), (torso_bottom[0], torso_bottom[1]), int(7 * scale))

    # Head
    pygame.draw.circle(surface, COLOR_SILHOUETTE, head_center, head_r)
    pygame.draw.line(surface, COLOR_SILHOUETTE, (head_center[0] - 8 * scale, head_center[1] + 1),
                     (head_center[0] + 8 * scale, head_center[1] + 1), int(3 * scale))

    # Arms swing opposite to legs
    shoulder = (int(x + lean_x), int(base_y - h * 0.75))
    arm_swing = leg_phase_r * 10 * scale
    hand = (int(x + 12 * scale + arm_swing), int(base_y - h * 0.55))
    pygame.draw.line(surface, COLOR_SILHOUETTE, shoulder, hand, int(3 * scale))

    # Rifle sways with arm
    rifle_start = (int(hand[0] - 10 * scale), int(hand[1] + 6 * scale))
    rifle_end = (int(hand[0] + 20 * scale + arm_swing * 0.3), int(hand[1] - 22 * scale))
    pygame.draw.line(surface, COLOR_SILHOUETTE, rifle_start, rifle_end, int(2 * scale))
    pygame.draw.line(surface, (180, 180, 180), rifle_end,
                     (int(rifle_end[0] + 4 * scale), int(rifle_end[1] - 7 * scale)), 1)


def draw_muzzle_flash(surface, x, y):
    flash = pygame.Surface((20, 20), pygame.SRCALPHA)
    pygame.draw.circle(flash, (255, 220, 120, 200), (10, 10), 6)
    surface.blit(flash, (int(x) - 10, int(y) - 10), special_flags=pygame.BLEND_ADD)


def draw_tracer_round(surface, x1, y1, x2, y2):
    tracer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.line(tracer, (255, 200, 80, 180), (int(x1), int(y1)), (int(x2), int(y2)), 2)
    pygame.draw.line(tracer, (255, 240, 180, 120), (int(x1), int(y1)), (int(x2), int(y2)), 1)
    surface.blit(tracer, (0, 0))


def draw_ground_battle_scene(surface, current_sec, explosions, camera, tank_recoils):
    """Large-scale frontline ground battle — soldiers, tanks, tracers, and impacts."""
    beat = (math.sin(current_sec * 10.0) + 1) * 0.5
    if beat > 0.82:
        camera.add_impulse(1.8)

    haze = int(30 + beat * 25)
    draw_gradient_sky(surface, (55, 18, 12), (120 + haze, 45 + haze // 2, 18))
    draw_parallax_clouds(surface, current_sec, 1, (60, 35, 25), 45, 0.6, 30)
    draw_parallax_clouds(surface, current_sec, 0, (40, 25, 20), 30, 0.35, 90)

    ground_y = HEIGHT - 58
    pygame.draw.rect(surface, COLOR_SILHOUETTE, (0, ground_y, WIDTH, 58))
    # Battlefield debris / crater rim silhouettes
    for cx in (120, 340, 580, 760):
        pygame.draw.ellipse(surface, (18, 16, 20), (cx - 35, ground_y - 8, 70, 16))

    # Barbed wire line across no-man's-land
    wire_y = ground_y - 28
    for wx in range(40, WIDTH - 40, 35):
        post_h = 18 + (wx % 3) * 4
        pygame.draw.line(surface, (30, 28, 32), (wx, wire_y), (wx, wire_y + post_h), 2)
        if wx % 70 < 35:
            pygame.draw.line(surface, (35, 32, 36), (wx, wire_y + 6), (wx + 30, wire_y + 2), 1)

    # Left column advancing east
    for i in range(12):
        sx = (i * 75 + int(current_sec * 85)) % (WIDTH + 160) - 80
        draw_soldier(surface, sx, ground_y + 10, cycle_time=current_sec * 10.0 + i * 0.7, scale=0.95)
        if random.random() < 0.015:
            draw_muzzle_flash(surface, sx + 18, ground_y - 20)

    # Right column advancing west
    for i in range(10):
        sx = WIDTH - ((i * 80 + int(current_sec * 65)) % (WIDTH + 140)) + 60
        draw_soldier(surface, sx, ground_y + 14, cycle_time=current_sec * 9.5 + i * 0.9 + 2.0, scale=0.9)
        if random.random() < 0.012:
            draw_muzzle_flash(surface, sx - 12, ground_y - 18)

    # Three tanks across the line, staggered fire cycles
    tank_positions = [(180, 1.0), (480, 2.4), (780, 0.6)]
    for idx, (tx, phase_offset) in enumerate(tank_positions):
        draw_tank_and_artillery(surface, tx, ground_y + 8, cycle=current_sec + phase_offset, recoil_system=tank_recoils[idx])

    # Tracer fire crisscrossing no-man's-land
    if random.random() < 0.25:
        y_mid = ground_y - random.randint(15, 45)
        if random.random() < 0.5:
            draw_tracer_round(surface, 0, y_mid + 10, random.randint(200, WIDTH), y_mid)
        else:
            draw_tracer_round(surface, WIDTH, y_mid + 8, random.randint(0, WIDTH - 200), y_mid)

    # Mortar and artillery impacts
    if random.random() < 0.07:
        ex = random.randint(80, WIDTH - 80)
        explosions.append(Explosion(ex, ground_y + random.randint(-5, 5), max_radius=random.randint(25, 50)))
        camera.add_impulse(random.uniform(2.5, 5.0), (ex - WIDTH // 2) / WIDTH)

    # Drifting battle smoke
    if random.random() < 0.12:
        smoke_puffs.append(SmokePuff(
            random.randint(0, WIDTH), ground_y - random.randint(5, 50),
            random.uniform(-0.4, 0.4), random.uniform(-0.3, -0.05),
            random.uniform(6, 14), random.randint(35, 70),
            color=(45, 38, 35), grow=0.25
        ))


def draw_atmospheric_particles(surface):
    for puff in smoke_puffs[:]:
        puff.update()
        puff.draw(surface)
        if not puff.alive:
            smoke_puffs.remove(puff)

    for spark in spark_particles[:]:
        spark.update()
        spark.draw(surface)
        if not spark.alive:
            spark_particles.remove(spark)

    for mark in scorch_marks[:]:
        mark.update()
        mark.draw(surface)
        if mark.alpha <= 0:
            scorch_marks.remove(mark)


# ==============================================================================
# MAIN ENGINE & TIMELINE
# ==============================================================================
def main():
    args = parse_args()
    export_mode = args.export

    if export_mode and args.no_preview:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    caption = "Black Sabbath - War Pigs (Exporting…)" if export_mode else "Black Sabbath - War Pigs (Dynamic Cinematic Cut)"
    pygame.display.set_caption(caption)
    clock = pygame.time.Clock()
    camera = CameraShake()

    has_audio = False
    if not export_mode:
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(str(AUDIO_PATH))
            pygame.mixer.music.play()
            has_audio = True
        except Exception:
            pass

    recorder = None
    if export_mode:
        random.seed(42)
        audio_for_mux = AUDIO_PATH if AUDIO_PATH.is_file() else None
        recorder = FfmpegRecorder(args.output, audio_path=audio_for_mux)
        total_frames = int(SONG_DURATION_SEC * FPS)
        print(f"Exporting {total_frames} frames ({SONG_DURATION_SEC:.0f}s @ {FPS}fps) → {args.output}")
        if audio_for_mux:
            print(f"Muxing audio from {audio_for_mux.name}")

    # Scene Simulation Pools
    planes = []
    bombs = []
    explosions = []
    flak_bursts = []

    # Pre-populate plane squads
    for i in range(4):
        planes.append(Plane(WIDTH + i * 220, 90 + (i % 2) * 45, speed=-3.2, plane_type="bomber"))

    ground_battle_recoils = [TankRecoilSystem() for _ in range(3)]

    start_ticks = pygame.time.get_ticks()
    time_offset = 0.0
    frame_index = 0
    total_frames = int(SONG_DURATION_SEC * FPS)

    running = True
    while running:
        if export_mode:
            if frame_index >= total_frames:
                break
            current_sec = frame_index / FPS
        else:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RIGHT:
                        time_offset += 15.0
                    elif event.key == pygame.K_LEFT:
                        time_offset = max(0.0, time_offset - 15.0)

            raw_sec = (pygame.mixer.music.get_pos() / 1000.0) if has_audio else ((pygame.time.get_ticks() - start_ticks) / 1000.0)
            current_sec = min(SONG_DURATION_SEC, raw_sec + time_offset)

        # ----------------------------------------------------------------------
        # SCENE CUT CONTROLLER
        # ----------------------------------------------------------------------
        scene_id = 0
        if 22.0 <= current_sec < 46.0: scene_id = 1
        elif 46.0 <= current_sec < 75.0: scene_id = 2
        elif 75.0 <= current_sec < 105.0: scene_id = 3
        elif 105.0 <= current_sec < SCENE_SOLO_START: scene_id = 4
        elif SCENE_SOLO_START <= current_sec < SCENE_SOLO_END: scene_id = 5
        elif SCENE_SOLO_END <= current_sec < SCENE_GROUND_BATTLE_END: scene_id = 6
        elif current_sec >= SCENE_AFTERMATH_START: scene_id = 7

        frame = pygame.Surface((WIDTH, HEIGHT))

        # --- SCENE 0: RED AIR RAID SIREN ---
        if scene_id == 0:
            siren = (math.sin(current_sec * 4.0) + 1) * 0.5
            draw_gradient_sky(frame, (int(25 + siren * 65), 6, 10), (int(70 + siren * 100), 20, 10))
            draw_parallax_clouds(frame, current_sec, 0, (40, 15, 18), 40, 0.3, 80)
            beam_x = WIDTH // 2 + math.sin(current_sec * 1.5) * 350
            sl_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            beam_alpha = int(35 + siren * 25)
            pygame.draw.polygon(sl_surf, (255, 240, 190, beam_alpha), [(WIDTH // 2, HEIGHT), (beam_x - 50, 0), (beam_x + 50, 0)])
            # Dust in beam
            for _ in range(3):
                dx = random.randint(int(beam_x - 40), int(beam_x + 40))
                dy = random.randint(100, HEIGHT - 60)
                pygame.draw.circle(sl_surf, (255, 230, 180, 30), (dx, dy), random.randint(1, 2))
            frame.blit(sl_surf, (0, 0))
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, HEIGHT - 50, WIDTH, 50))
            for i in range(0, WIDTH, 120):
                pygame.draw.rect(frame, COLOR_SILHOUETTE, (i, HEIGHT - 110 - (i % 70), 55, 120))

        # --- SCENE 1: BOMBER FLEET & FLAK SKY ---
        elif scene_id == 1:
            draw_gradient_sky(frame, (10, 10, 18), (80, 25, 20))
            draw_parallax_clouds(frame, current_sec, 1, (30, 20, 25), 35, 0.5, 50)
            draw_parallax_clouds(frame, current_sec, 0, (20, 15, 20), 25, 0.25, 120)
            if random.random() < 0.12:
                fx, fy = random.randint(60, WIDTH - 60), random.randint(60, 260)
                flak_bursts.append(FlakBurst(fx, fy))
                camera.add_impulse(1.5, random.uniform(-1, 1))
            for p in planes:
                p.update(bombs, current_sec)
                p.draw(frame)
                if p.x < -100:
                    p.x = WIDTH + 100

        # --- SCENE 2: HEAVY RIFF (TROOPS + TANKS) ---
        elif scene_id == 2:
            beat = (math.sin(current_sec * 10.0) + 1) * 0.5
            if beat > 0.85:
                camera.add_impulse(2.5)
            draw_gradient_sky(frame, (45, 10, 15), (140 + int(beat * 40), 40, 20))
            ground_y = HEIGHT - 65
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, ground_y, WIDTH, 65))
            for i in range(8):
                sx = (i * 125 - int(current_sec * 90)) % (WIDTH + 100) - 50
                draw_soldier(frame, sx, ground_y + 12, cycle_time=current_sec * 9.0 + i, scale=1.0)
            draw_tank_and_artillery(frame, 780, ground_y + 10, cycle=current_sec)

        # --- SCENE 3: THE WAR TABLE (PUPPETEERS) ---
        elif scene_id == 3:
            draw_war_table_scene(frame, current_sec)

        # --- SCENE 4: FRONTLINE CARPET BOMBING ---
        elif scene_id == 4:
            draw_gradient_sky(frame, (20, 8, 12), (110, 35, 20))
            draw_parallax_clouds(frame, current_sec, 1, (50, 25, 20), 30, 0.8, 40)
            if random.random() < 0.08:
                planes.append(Plane(-60, random.randint(50, 160), speed=random.uniform(5.5, 8.5), plane_type="fighter"))
            for p in planes[:]:
                p.update(bombs, current_sec)
                p.draw(frame)
                if p.x > WIDTH + 120 or p.x < -150:
                    planes.remove(p)
            ground_y = HEIGHT - 50
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, ground_y, WIDTH, 50))
            for b in bombs[:]:
                b.update()
                b.draw(frame)
                if b.exploded:
                    exp = Explosion(b.x, ground_y + 5, max_radius=random.randint(40, 75))
                    explosions.append(exp)
                    dist_factor = 1.0 - abs(b.x - WIDTH // 2) / (WIDTH // 2)
                    camera.add_impulse(4.0 + dist_factor * 4.0, (b.x - WIDTH // 2) / WIDTH)
                    bombs.remove(b)

        # --- SCENE 5: GUITAR SOLO CATACLYSM ---
        elif scene_id == 5:
            strobe = (int(current_sec * 16) % 2 == 0)
            camera.add_impulse(random.uniform(2.0, 5.0))
            if strobe:
                draw_gradient_sky(frame, (220, 180, 60), (180, 20, 20))
            else:
                draw_gradient_sky(frame, (10, 6, 8), (70, 10, 15))

            ground_y = HEIGHT - 50
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, ground_y, WIDTH, 50))

            if random.random() < 0.4:
                ex = random.randint(40, WIDTH - 40)
                explosions.append(Explosion(ex, ground_y + random.randint(-10, 10), max_radius=80))
                camera.add_impulse(random.uniform(5.0, 9.0), random.uniform(-1, 1))

            if random.random() < 0.15:
                planes.append(Plane(WIDTH + 50, random.randint(120, 240), speed=-11.0, plane_type="fighter"))
            for p in planes[:]:
                p.update(bombs, current_sec)
                p.draw(frame)
                if p.x < -100:
                    planes.remove(p)

        # --- SCENE 6: FRONTLINE GROUND BATTLE ---
        elif scene_id == 6:
            draw_ground_battle_scene(frame, current_sec, explosions, camera, ground_battle_recoils)

        # --- SCENE 7: DESOLATE AFTERMATH & OUTRO ---
        elif scene_id == 7:
            fade = max(0.0, 1.0 - (current_sec - SCENE_AFTERMATH_START) / 38.0)
            draw_gradient_sky(frame, (int(12 * fade), int(10 * fade), int(14 * fade)), (int(45 * fade), int(20 * fade), int(15 * fade)))
            ground_y = HEIGHT - 50
            pygame.draw.rect(frame, (int(10 * fade), int(10 * fade), int(14 * fade)), (0, ground_y, WIDTH, 50))
            grave_x = WIDTH // 2
            pygame.draw.line(frame, COLOR_SILHOUETTE, (grave_x, ground_y - 65), (grave_x, ground_y), 5)
            pygame.draw.line(frame, COLOR_SILHOUETTE, (grave_x - 18, ground_y - 48), (grave_x + 18, ground_y - 48), 4)
            pygame.draw.circle(frame, COLOR_SILHOUETTE, (grave_x, ground_y - 65), 10)
            # Drifting ash in aftermath
            if random.random() < 0.15:
                smoke_puffs.append(SmokePuff(
                    random.randint(0, WIDTH), ground_y - random.randint(10, 80),
                    random.uniform(-0.3, 0.3), random.uniform(-0.5, -0.1),
                    random.uniform(2, 5), random.randint(50, 100), color=(40, 38, 42), grow=0.08
                ))

        # ----------------------------------------------------------------------
        # UNIVERSAL PARTICLE UPDATES & DRAW
        # ----------------------------------------------------------------------
        for exp in explosions[:]:
            exp.update()
            exp.draw(frame)
            if not exp.alive:
                explosions.remove(exp)

        for flak in flak_bursts[:]:
            flak.update()
            flak.draw(frame)
            if flak.alpha <= 0:
                flak_bursts.remove(flak)

        draw_atmospheric_particles(frame)

        # ----------------------------------------------------------------------
        # POST-PROCESSING: CINEMATIC LETTERBOX & CAMERA SHAKE
        # ----------------------------------------------------------------------
        camera.update()
        sx, sy = camera.offset()

        screen.fill(COLOR_BLACK)
        screen.blit(frame, (sx, sy))

        # Letterbox Bars
        bar_height = 42
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, WIDTH, bar_height))
        pygame.draw.rect(screen, (0, 0, 0), (0, HEIGHT - bar_height, WIDTH, bar_height))

        # Scene Tracker & HUD
        show_hud = (not export_mode) or args.hud
        if show_hud:
            mins = int(current_sec // 60)
            secs = int(current_sec % 60)
            scene_names = [
                "AIR RAID SIREN", "BOMBERS INBOUND", "HEAVY RIFF BATTALION",
                "WAR TABLE / GENERALS", "CARPET BOMBING", "SOLO CATACLYSM",
                "FRONTLINE GROUND BATTLE", "DESOLATE AFTERMATH",
            ]
            font = pygame.font.SysFont("monospace", 13, bold=True)
            hud_suffix = " | [<-/-> Seek]" if not export_mode else ""
            hud_text = font.render(
                f"[{mins:02d}:{secs:02d} / 03:33] SCENE: {scene_names[scene_id]}{hud_suffix}",
                True, (160, 140, 140),
            )
            screen.blit(hud_text, (20, 14))

        if export_mode:
            recorder.write_frame(screen)
            frame_index += 1
            if not args.no_preview:
                pygame.display.flip()
            if frame_index % (FPS * 5) == 0 or frame_index == total_frames:
                pct = 100.0 * frame_index / total_frames
                print(f"  {frame_index}/{total_frames} frames ({pct:.0f}%)")
        else:
            pygame.display.flip()
            clock.tick(FPS)

    if recorder:
        out = recorder.close()
        print(f"Done → {out}")

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
