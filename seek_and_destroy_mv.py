import math
import os
import sys
import cairo
import pygame

# ==============================================================================
# 1. TIMELINE, BPM & CONSTANTS
# ==============================================================================
WINDOW_W, WINDOW_H = 1080, 720
BPM = 72.0
BEAT_FREQ = BPM / 60.0  # 1.2 Hz
SONG_DURATION = 313.0   # 5m 13s
SINGING_START_TIME = 33.0

AUDIO_FILE = "seek_and_destory_nepali.mp3"

COLOR_SKIN = (0.88, 0.72, 0.58)
COLOR_GOLD = (0.95, 0.78, 0.22)
COLOR_WHITE = (0.95, 0.95, 0.95)
COLOR_DARK = (0.12, 0.12, 0.14)

# ==============================================================================
# 2. VECTOR BACKGROUND: HIMALAYAS, STUPA, PAGODA & MOON
# ==============================================================================
class HimalayanStageRenderer:
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def draw_background(self, t, camera_x=0.0):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        ctx.save()
        ctx.translate(-camera_x * 0.25, 0)

        # Night Sky Gradient
        sky_grad = cairo.LinearGradient(0, 0, 0, self.h)
        sky_grad.add_color_stop_rgb(0.0, 0.05, 0.06, 0.14)
        sky_grad.add_color_stop_rgb(0.65, 0.12, 0.14, 0.26)
        sky_grad.add_color_stop_rgb(1.0, 0.20, 0.18, 0.28)
        ctx.set_source(sky_grad)
        ctx.paint()

        # Moon & Glow Halo
        ctx.set_source_rgba(1.0, 0.96, 0.85, 0.20)
        ctx.arc(880, 140, 68, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.98, 0.96, 0.90)
        ctx.arc(880, 140, 44, 0, 2 * math.pi)
        ctx.fill()

        # Twinkling Stars
        ctx.set_source_rgb(1.0, 1.0, 1.0)
        for i, (sx, sy) in enumerate([(120, 80), (260, 110), (410, 60), (580, 130), (740, 75), (960, 95)]):
            twinkle = (math.sin(t * 3.0 + i) + 1.0) * 0.5
            ctx.arc(sx, sy, 1.2 + twinkle * 1.5, 0, 2 * math.pi)
            ctx.fill()

        # Himalayan Peaks (Snow Silhouette)
        ctx.set_source_rgb(0.85, 0.90, 0.96)
        ctx.move_to(-100, 380)
        ctx.line_to(140, 180)
        ctx.line_to(320, 310)
        ctx.line_to(560, 140)   # Fishtail Peak
        ctx.line_to(760, 300)
        ctx.line_to(940, 160)
        ctx.line_to(1200, 380)
        ctx.line_to(1200, self.h)
        ctx.line_to(-100, self.h)
        ctx.close_path()
        ctx.fill()

        # Mountain Blue Ridge Shading
        ctx.set_source_rgb(0.25, 0.30, 0.45)
        ctx.move_to(-100, 380)
        ctx.line_to(140, 180)
        ctx.line_to(220, 380)
        ctx.line_to(560, 140)
        ctx.line_to(680, 380)
        ctx.line_to(940, 160)
        ctx.line_to(1060, 380)
        ctx.line_to(1200, 380)
        ctx.line_to(1200, self.h)
        ctx.line_to(-100, self.h)
        ctx.close_path()
        ctx.fill()

        # Buddhist Stupa (Left)
        self.draw_stupa(ctx, 160, 460)

        # Multi-Tier Pagoda Temple (Right)
        self.draw_pagoda(ctx, 920, 460)

        # Stone Stage Courtyard Floor
        ctx.set_source_rgb(0.16, 0.16, 0.22)
        ctx.rectangle(-100, 460, self.w + 300, self.h - 460)
        ctx.fill()
        ctx.set_line_width(3)
        ctx.set_source_rgb(0.32, 0.34, 0.44)
        ctx.move_to(-100, 460)
        ctx.line_to(self.w + 200, 460)
        ctx.stroke()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")

    def draw_stupa(self, ctx, x, y):
        ctx.save()
        ctx.translate(x, y)

        # White Dome (Garbha)
        ctx.set_source_rgb(0.92, 0.92, 0.90)
        ctx.arc(0, 0, 72, math.pi, 2 * math.pi)
        ctx.close_path()
        ctx.fill()

        # Square Harmika
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.rectangle(-26, -114, 52, 42)
        ctx.fill()

        # Eyes of Buddha
        ctx.set_source_rgb(0.1, 0.1, 0.12)
        ctx.set_line_width(2.0)
        ctx.arc(-12, -94, 6, 0.2, math.pi - 0.2)
        ctx.stroke()
        ctx.arc(12, -94, 6, 0.2, math.pi - 0.2)
        ctx.stroke()
        ctx.move_to(0, -96)
        ctx.curve_to(4, -90, -4, -84, 0, -80)
        ctx.stroke()

        # Spire Steps (13 tiers)
        ctx.set_source_rgb(0.85, 0.68, 0.18)
        for step in range(13):
            sw = 44 - step * 2.8
            ctx.rectangle(-sw / 2, -118 - (step * 5), sw, 4)
            ctx.fill()

        # Pinnacle (Gajur)
        ctx.arc(0, -186, 6, 0, 2 * math.pi)
        ctx.fill()

        # Prayer Flags
        ctx.set_line_width(1.5)
        for i, col in enumerate([(0.2, 0.4, 0.8), (0.9, 0.9, 0.9), (0.8, 0.1, 0.1), (0.2, 0.7, 0.3), (0.9, 0.8, 0.2)]):
            ctx.set_source_rgb(*col)
            ctx.move_to(0, -186)
            ctx.line_to(-75 + i * 15, -60)
            ctx.stroke()
            ctx.move_to(0, -186)
            ctx.line_to(75 - i * 15, -60)
            ctx.stroke()

        ctx.restore()

    def draw_pagoda(self, ctx, x, y):
        ctx.save()
        ctx.translate(x, y)

        # Brick Base
        ctx.set_source_rgb(0.45, 0.20, 0.16)
        ctx.rectangle(-70, -20, 140, 20)
        ctx.fill()

        # Roof Tiers
        self._draw_roof_tier(ctx, 0, -20, 150, 24)
        ctx.set_source_rgb(0.38, 0.18, 0.14)
        ctx.rectangle(-42, -90, 84, 50)
        ctx.fill()
        self._draw_roof_tier(ctx, 0, -90, 115, 20)
        ctx.set_source_rgb(0.35, 0.16, 0.12)
        ctx.rectangle(-26, -145, 52, 35)
        ctx.fill()
        self._draw_roof_tier(ctx, 0, -145, 80, 18)

        # Pinnacle
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.move_to(0, -195)
        ctx.line_to(6, -170)
        ctx.line_to(-6, -170)
        ctx.close_path()
        ctx.fill()

        ctx.restore()

    def _draw_roof_tier(self, ctx, cx, cy, span, h):
        ctx.set_source_rgb(0.55, 0.14, 0.10)
        ctx.move_to(cx - span / 2, cy)
        ctx.curve_to(cx - span / 2 - 10, cy - h * 0.4, cx - span / 3, cy - h, cx, cy - h)
        ctx.curve_to(cx + span / 3, cy - h, cx + span / 2 + 10, cy - h * 0.4, cx + span / 2, cy)
        ctx.close_path()
        ctx.fill()


# ==============================================================================
# 3. CHARACTER RIGS (BGRA BUFFER CONVERSIONS)
# ==============================================================================

# --- A. NARAYAN GOPAL ---
class NarayanGopalRig:
    def __init__(self):
        self.w, self.h = 320, 360
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_singing):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        vibrato = math.sin(t * 8.0) * 0.03 if is_singing else 0.0
        sing_intensity = max(0.0, math.sin(t * BEAT_FREQ * 2 * math.pi)) if is_singing else 0.1
        bellows = (math.sin(t * BEAT_FREQ * 2 * math.pi) + 1.0) * 0.5

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)

        # Cross-legged posture
        ctx.set_line_width(20)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.2, 0.2, 0.24)
        ctx.move_to(-40, -5)
        ctx.line_to(-60, 20)
        ctx.line_to(60, 20)
        ctx.line_to(40, -5)
        ctx.stroke()

        # Torso & Tweed Blazer
        ctx.save()
        ctx.rotate(math.sin(t * BEAT_FREQ * math.pi) * 0.03)
        ctx.set_source_rgb(0.25, 0.24, 0.28)
        ctx.rectangle(-22, -75, 44, 75)
        ctx.fill()

        # Wrapped Cream Muffler
        ctx.set_source_rgb(0.88, 0.82, 0.70)
        ctx.rectangle(-18, -74, 36, 18)
        ctx.fill()
        ctx.rectangle(-6, -60, 12, 45)
        ctx.fill()

        # Head, Hair & Glasses
        ctx.save()
        ctx.translate(0, -92)
        ctx.rotate(-0.05 - (sing_intensity * 0.12) + vibrato)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 0, 14, 0, 2 * math.pi)
        ctx.fill()

        # Wavy Hair
        ctx.set_source_rgb(0.12, 0.10, 0.10)
        ctx.arc(0, -6, 15, math.pi, 2 * math.pi)
        ctx.fill()

        # Signature Glasses
        ctx.set_line_width(2.4)
        ctx.set_source_rgb(0.1, 0.1, 0.1)
        ctx.rectangle(-11, -5, 9, 7)
        ctx.stroke()
        ctx.rectangle(2, -5, 9, 7)
        ctx.stroke()
        ctx.move_to(-2, -2)
        ctx.line_to(2, -2)
        ctx.stroke()

        # Singing mouth
        mouth_h = 2 + sing_intensity * 7.0
        ctx.set_source_rgb(0.45, 0.1, 0.12)
        ctx.rectangle(-4, 5, 8, mouth_h)
        ctx.fill()
        ctx.restore()

        # Left Arm (Pumping Harmonium Bellows)
        ctx.save()
        ctx.translate(-22, -65)
        ctx.rotate(-0.8 - bellows * 0.25)
        ctx.set_line_width(10)
        ctx.set_source_rgb(0.25, 0.24, 0.28)
        ctx.line_to(0, 34)
        ctx.stroke()
        ctx.translate(0, 34)
        ctx.rotate(-0.7 + bellows * 0.4)
        ctx.line_to(0, 30)
        ctx.stroke()
        ctx.restore()

        # Right Arm (Playing Keys)
        ctx.save()
        ctx.translate(22, -65)
        ctx.rotate(0.6)
        ctx.set_line_width(10)
        ctx.set_source_rgb(0.25, 0.24, 0.28)
        ctx.line_to(0, 34)
        ctx.stroke()
        ctx.translate(0, 34)
        ctx.rotate(0.9 + math.sin(t * 6.0) * 0.08)
        ctx.line_to(0, 30)
        ctx.stroke()
        ctx.restore()

        ctx.restore()

        # Harmonium
        ctx.save()
        ctx.translate(0, 10)
        ctx.set_source_rgb(0.48, 0.22, 0.12)
        ctx.rectangle(-55, -45, 110, 45)
        ctx.fill()
        # Bellows
        bw = 18 + bellows * 15
        ctx.set_source_rgb(0.75, 0.15, 0.18)
        ctx.rectangle(-55 - bw, -43, bw, 41)
        ctx.fill()
        # Keys
        ctx.set_source_rgb(0.95, 0.95, 0.90)
        ctx.rectangle(-5, -43, 55, 18)
        ctx.fill()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


# --- B. NEPALI FOLK DANCERS ---
class NepaliDancersRig:
    def __init__(self):
        self.w, self.h = 420, 400
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_twirling=False):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        sway = math.sin(t * BEAT_FREQ * 2 * math.pi)
        twirl_scale = math.cos(t * 5.0) if is_twirling else 1.0

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)

        # 1. Female Dancer (Left)
        ctx.save()
        ctx.translate(-70, 0)
        ctx.scale(twirl_scale, 1.0)
        self._draw_female(ctx, sway, t)
        ctx.restore()

        # 2. Male Dancer (Right)
        ctx.save()
        ctx.translate(70, 0)
        ctx.scale(twirl_scale, 1.0)
        self._draw_male(ctx, -sway, t)
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")

    def _draw_female(self, ctx, sway, t):
        flare = 45 + abs(sway) * 15
        ctx.set_source_rgb(0.12, 0.12, 0.14)
        ctx.move_to(-12, -75)
        ctx.line_to(-flare, 0)
        ctx.line_to(flare, 0)
        ctx.line_to(12, -75)
        ctx.close_path()
        ctx.fill()
        # Gold Border
        ctx.set_line_width(4)
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.move_to(-flare, 0)
        ctx.line_to(flare, 0)
        ctx.stroke()
        # Red Cholo Blouse
        ctx.set_source_rgb(0.80, 0.12, 0.15)
        ctx.rectangle(-14, -135, 28, 60)
        ctx.fill()
        # Head & Bun
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, -152, 12, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.1, 0.1, 0.1)
        ctx.arc(-10, -156, 8, 0, 2 * math.pi)
        ctx.fill()
        # Mudra Arms
        ctx.set_line_width(7)
        ctx.set_source_rgb(0.80, 0.12, 0.15)
        ctx.move_to(-14, -130)
        ctx.line_to(-38, -165 + sway * 12)
        ctx.stroke()
        ctx.move_to(14, -130)
        ctx.line_to(38, -165 - sway * 12)
        ctx.stroke()

    def _draw_male(self, ctx, sway, t):
        ctx.set_line_width(10)
        ctx.set_source_rgb(0.92, 0.90, 0.86)
        ctx.move_to(-10, -70)
        ctx.line_to(-16 + sway * 10, 0)
        ctx.stroke()
        ctx.move_to(10, -70)
        ctx.line_to(16 - sway * 10, 0)
        ctx.stroke()
        # Daura Coat & Waistcoat
        ctx.set_source_rgb(0.92, 0.90, 0.86)
        ctx.rectangle(-15, -140, 30, 70)
        ctx.fill()
        ctx.set_source_rgb(0.15, 0.16, 0.24)
        ctx.rectangle(-15, -140, 10, 50)
        ctx.fill()
        ctx.rectangle(5, -140, 10, 50)
        ctx.fill()
        # Patuka
        ctx.set_source_rgb(0.80, 0.12, 0.15)
        ctx.rectangle(-17, -78, 34, 12)
        ctx.fill()
        # Dhaka Topi & Head
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, -156, 12, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.75, 0.18, 0.20)
        ctx.move_to(-11, -166)
        ctx.line_to(-10, -180)
        ctx.line_to(4, -184)
        ctx.line_to(11, -172)
        ctx.line_to(11, -166)
        ctx.close_path()
        ctx.fill()
        # Arms
        ctx.set_line_width(8)
        ctx.set_source_rgb(0.92, 0.90, 0.86)
        ctx.move_to(-14, -135)
        ctx.line_to(-42, -110 + sway * 15)
        ctx.stroke()
        ctx.move_to(14, -135)
        ctx.line_to(42, -110 - sway * 15)
        ctx.stroke()


# --- C. ROYAL GUARD ---
class RoyalGuardRig:
    def __init__(self):
        self.w, self.h = 360, 420
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_attacking=False):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        slash = math.sin(t * (BEAT_FREQ * 4 * math.pi if is_attacking else BEAT_FREQ * 2 * math.pi))

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)

        # Grounded Legs
        ctx.set_line_width(12)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.14, 0.16, 0.20)
        ctx.move_to(-15, -75)
        ctx.line_to(-35, 0)
        ctx.stroke()
        ctx.move_to(15, -75)
        ctx.line_to(35, 0)
        ctx.stroke()

        # Scarlet Tunic & Belts
        ctx.set_source_rgb(0.76, 0.10, 0.14)
        ctx.rectangle(-18, -150, 36, 75)
        ctx.fill()
        ctx.set_line_width(4)
        ctx.set_source_rgb(0.95, 0.95, 0.95)
        ctx.move_to(-16, -148)
        ctx.line_to(16, -80)
        ctx.stroke()
        ctx.move_to(16, -148)
        ctx.line_to(-16, -80)
        ctx.stroke()

        # Head & Plumed Royal Cap
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, -168, 13, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.14, 0.16, 0.20)
        ctx.rectangle(-13, -188, 26, 14)
        ctx.fill()
        ctx.set_source_rgb(0.9, 0.1, 0.1)
        ctx.move_to(0, -188)
        ctx.curve_to(4, -204, -4, -214, 0, -220)
        ctx.stroke()

        # Left Arm (Torch)
        ctx.save()
        ctx.translate(-18, -142)
        ctx.rotate(-1.6 + math.sin(t * 3.0) * 0.08)
        ctx.set_line_width(9)
        ctx.set_source_rgb(0.76, 0.10, 0.14)
        ctx.line_to(0, 36)
        ctx.stroke()
        ctx.translate(0, 36)
        ctx.rotate(-0.8)
        ctx.line_to(0, 34)
        ctx.stroke()
        ctx.translate(0, 34)
        ctx.set_line_width(6)
        ctx.set_source_rgb(0.35, 0.22, 0.14)
        ctx.line_to(0, -32)
        ctx.stroke()
        # Flame
        flick = math.sin(t * 16.0) * 3
        ctx.set_source_rgb(1.0, 0.35, 0.05)
        ctx.arc(flick, -42, 14, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(1.0, 0.9, 0.2)
        ctx.arc(0, -42, 7, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Right Arm (Khukuri)
        ctx.save()
        ctx.translate(18, -142)
        arm_rot = 0.4 + slash * 1.1 if is_attacking else 0.5 + slash * 0.3
        ctx.rotate(arm_rot)
        ctx.set_line_width(9)
        ctx.set_source_rgb(0.76, 0.10, 0.14)
        ctx.line_to(0, 36)
        ctx.stroke()
        ctx.translate(0, 36)
        ctx.rotate(1.1)
        ctx.line_to(0, 32)
        ctx.stroke()
        # Blade
        ctx.translate(0, 32)
        ctx.set_source_rgb(0.88, 0.92, 0.96)
        ctx.move_to(0, 0)
        ctx.curve_to(6, -14, 12, -28, 2, -44)
        ctx.curve_to(-8, -30, -6, -12, 0, 0)
        ctx.close_path()
        ctx.fill()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


# --- D. JAMES HETFIELD ---
class JamesHetfieldRig:
    def __init__(self):
        self.w, self.h = 420, 420
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_swinging=False):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        downpick = math.sin(t * 24.0) * 6.0
        headbang = math.sin(t * BEAT_FREQ * 4 * math.pi) * 0.28
        guitar_tilt = -0.35 - (0.65 if is_swinging else 0.0)

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)

        # Power Stance Legs
        ctx.set_line_width(14)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.16, 0.17, 0.22)
        ctx.move_to(-20, -75)
        ctx.line_to(-48, 0)
        ctx.stroke()
        ctx.move_to(20, -75)
        ctx.line_to(48, 0)
        ctx.stroke()

        # Torso
        ctx.set_source_rgb(0.12, 0.12, 0.14)
        ctx.rectangle(-22, -150, 44, 75)
        ctx.fill()

        # Head & Blonde Hair
        ctx.save()
        ctx.translate(0, -168)
        ctx.rotate(headbang)
        ctx.set_source_rgb(0.75, 0.60, 0.36)
        ctx.arc(0, 0, 18, 0, 2 * math.pi)
        ctx.fill()
        ctx.move_to(-16, 0)
        ctx.line_to(-28, 30)
        ctx.line_to(28, 30)
        ctx.line_to(16, 0)
        ctx.fill()
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 2, 12, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.4, 0.08, 0.1)
        ctx.rectangle(-5, 4, 10, 8)
        ctx.fill()
        ctx.set_line_width(2)
        ctx.set_source_rgb(0.45, 0.34, 0.18)
        ctx.arc(0, 6, 6, 0, math.pi)
        ctx.stroke()
        ctx.restore()

        # White Flying V Guitar
        ctx.save()
        ctx.translate(-10, -90)
        ctx.rotate(guitar_tilt)
        ctx.set_source_rgb(0.2, 0.15, 0.1)
        ctx.rectangle(-110, -5, 110, 10)
        ctx.fill()
        ctx.set_source_rgb(0.95, 0.95, 0.92)
        ctx.move_to(0, -14)
        ctx.line_to(85, -42)
        ctx.line_to(45, 0)
        ctx.line_to(85, 42)
        ctx.line_to(0, 14)
        ctx.close_path()
        ctx.fill()
        ctx.restore()

        # Right Arm (Downpicking)
        ctx.save()
        ctx.translate(22, -142)
        ctx.rotate(0.6)
        ctx.set_line_width(11)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.line_to(0, 36)
        ctx.stroke()
        ctx.translate(0, 36)
        ctx.rotate(1.1 + downpick * 0.02)
        ctx.line_to(0, 32)
        ctx.stroke()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


# --- E. LARS ULRICH ---
class LarsUlrichRig:
    def __init__(self):
        self.w, self.h = 420, 420
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surface)

    def render(self, t, is_twirling=False):
        ctx = self.ctx
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        snare_hit = max(0.0, -math.sin(t * BEAT_FREQ * 4 * math.pi))
        twirl_rot = (t * 14.0) % (2 * math.pi) if is_twirling else 0.4

        ctx.save()
        ctx.translate(self.w / 2, self.h - 40)

        # Torso
        ctx.set_source_rgb(0.15, 0.15, 0.18)
        ctx.rectangle(-20, -140, 40, 70)
        ctx.fill()

        # Head & Cap
        ctx.save()
        ctx.translate(0, -158)
        ctx.rotate(math.sin(t * 6.0) * 0.15)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.arc(0, 0, 13, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.1, 0.1, 0.12)
        ctx.arc(0, -2, 14, math.pi, 2 * math.pi)
        ctx.fill()
        ctx.rectangle(-18, -4, 8, 4)
        ctx.fill()
        ctx.set_source_rgb(0.9, 0.3, 0.35)
        ctx.rectangle(-3, 6, 6, 8)
        ctx.fill()
        ctx.restore()

        # Drums & Cymbal
        ctx.set_source_rgb(0.65, 0.68, 0.74)
        ctx.rectangle(-35, -50, 70, 35)
        ctx.fill()
        ctx.set_source_rgb(*COLOR_GOLD)
        ctx.save()
        ctx.translate(85, -110)
        ctx.scale(1.0, 0.3)
        ctx.arc(0, 0, 45, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

        # Left Arm (Snare strike)
        ctx.save()
        ctx.translate(-18, -135)
        ctx.rotate(-0.8 + snare_hit * 0.6)
        ctx.set_line_width(9)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.line_to(0, 32)
        ctx.stroke()
        ctx.translate(0, 32)
        ctx.rotate(-0.8)
        ctx.line_to(0, 28)
        ctx.stroke()
        ctx.set_line_width(3.5)
        ctx.set_source_rgb(0.9, 0.85, 0.7)
        ctx.line_to(0, -40)
        ctx.stroke()
        ctx.restore()

        # Right Arm (Cymbal / Twirl)
        ctx.save()
        ctx.translate(18, -135)
        ctx.rotate(0.9 - snare_hit * 0.5)
        ctx.set_line_width(9)
        ctx.set_source_rgb(*COLOR_SKIN)
        ctx.line_to(0, 32)
        ctx.stroke()
        ctx.translate(0, 32)
        ctx.rotate(0.8)
        ctx.line_to(0, 28)
        ctx.stroke()
        ctx.translate(0, 28)
        ctx.rotate(twirl_rot)
        ctx.set_line_width(3.5)
        ctx.set_source_rgb(0.9, 0.85, 0.7)
        ctx.move_to(0, 15)
        ctx.line_to(0, -40)
        ctx.stroke()
        ctx.restore()

        ctx.restore()
        return pygame.image.frombuffer(self.surface.get_data(), (self.w, self.h), "BGRA")


# ==============================================================================
# 4. DIRECTOR ENGINE
# ==============================================================================
class MusicVideoDirector:
    def __init__(self):
        self.stage = HimalayanStageRenderer(WINDOW_W, WINDOW_H)
        self.narayan = NarayanGopalRig()
        self.dancers = NepaliDancersRig()
        self.guard = RoyalGuardRig()
        self.hetfield = JamesHetfieldRig()
        self.ulrich = LarsUlrichRig()

    def get_scene_descriptor(self, t):
        if t < SINGING_START_TIME:
            return "INTRO_ESTABLISHING"
        elif 33 <= t < 78:
            return "SCENE_SINGING_1"
        elif 78 <= t < 125:
            return "SCENE_FIGHT_HETFIELD"
        elif 125 <= t < 172:
            return "SCENE_SINGING_2"
        elif 172 <= t < 218:
            return "SCENE_FIGHT_ULRICH"
        elif 218 <= t < 265:
            return "SCENE_FIGHT_TRIO"
        else:
            return "SCENE_GRAND_FINALE"

    def render_frame(self, screen, t):
        scene = self.get_scene_descriptor(t)
        camera_pan = math.sin(t * 0.15) * 80.0

        # Background
        bg_surface = self.stage.draw_background(t, camera_pan)
        screen.blit(bg_surface, (0, 0))

        # Scene Layouts
        if scene == "INTRO_ESTABLISHING":
            guard_x = int(WINDOW_W * 0.5 + math.sin(t * 0.5) * 200)
            screen.blit(self.guard.render(t, is_attacking=False), (guard_x - 180, 220))
            self._render_hud_title(screen, "INTRO: HIMALAYAN MOONLIGHT (72 BPM)", t)

        elif scene in ("SCENE_SINGING_1", "SCENE_SINGING_2"):
            screen.blit(self.dancers.render(t, is_twirling=(scene == "SCENE_SINGING_2")), (WINDOW_W // 2 - 210, 220))
            screen.blit(self.narayan.render(t, is_singing=True), (WINDOW_W // 2 - 160, 260))
            self._render_hud_title(screen, "SWAR SAMRAT NARAYAN GOPAL - 'SEEK & DESTROY' (ADHUNIK)", t)

        elif scene == "SCENE_FIGHT_HETFIELD":
            screen.blit(self.hetfield.render(t, is_swinging=math.sin(t * 2.0) > 0.3), (160, 220))
            screen.blit(self.guard.render(t, is_attacking=True), (580, 220))
            self._render_hud_title(screen, "DUEL 1: HETFIELD (FLYING V) vs PALACE GUARD (KHUKURI)", t)

        elif scene == "SCENE_FIGHT_ULRICH":
            screen.blit(self.ulrich.render(t, is_twirling=True), (160, 220))
            screen.blit(self.guard.render(t, is_attacking=True), (580, 220))
            self._render_hud_title(screen, "DUEL 2: ULRICH (DRUMSTICKS) vs PALACE GUARD (TORCH)", t)

        elif scene == "SCENE_FIGHT_TRIO":
            screen.blit(self.hetfield.render(t, is_swinging=True), (80, 220))
            screen.blit(self.guard.render(t, is_attacking=True), (380, 220))
            screen.blit(self.ulrich.render(t, is_twirling=True), (660, 220))
            self._render_hud_title(screen, "CLASH 3: METALLICA DUO vs ROYAL GUARD STANDOFF", t)

        elif scene == "SCENE_GRAND_FINALE":
            screen.blit(self.hetfield.render(t, is_swinging=False), (-20, 230))
            screen.blit(self.ulrich.render(t, is_twirling=True), (200, 230))
            screen.blit(self.dancers.render(t, is_twirling=True), (WINDOW_W // 2 - 210, 210))
            screen.blit(self.narayan.render(t, is_singing=True), (WINDOW_W // 2 - 160, 260))
            screen.blit(self.guard.render(t, is_attacking=False), (WINDOW_W - 320, 220))
            self._render_hud_title(screen, "FINALE: EAST-WEST ADHUNIK THRASHER CONVERGENCE", t)

    def _render_hud_title(self, screen, title, t):
        font = pygame.font.SysFont("arial", 18, bold=True)
        pygame.draw.rect(screen, (10, 10, 15), (0, 0, WINDOW_W, 46))
        pygame.draw.rect(screen, (10, 10, 15), (0, WINDOW_H - 36, WINDOW_W, 36))
        txt = font.render(title, True, (240, 220, 140))
        screen.blit(txt, (24, 12))
        mins = int(t) // 60
        secs = int(t) % 60
        tc = font.render(f"TIMECODE: {mins:02d}:{secs:02d} / 05:13", True, (200, 200, 200))
        screen.blit(tc, (WINDOW_W - 240, 12))


# ==============================================================================
# 5. MAIN LOOP
# ==============================================================================
def main():
    pygame.init()
    pygame.mixer.init()
    pygame.display.set_caption("Seek & Destroy - Narayan Gopal x Metallica (Fixed BGRA Bridge)")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock = pygame.time.Clock()

    if os.path.exists(AUDIO_FILE):
        try:
            pygame.mixer.music.load(AUDIO_FILE)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"[AUDIO] {e}")

    director = MusicVideoDirector()
    anim_time = 0.0
    running = True

    while running:
        dt = clock.tick(60) / 1000.0
        anim_time += dt

        if anim_time > SONG_DURATION:
            anim_time = 0.0
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.play()

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                anim_time = min(SONG_DURATION, anim_time + 30.0)

        director.render_frame(screen, anim_time)
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
