#!/usr/bin/env python3
"""Shake It Off — Himalayan synthwave music visualizer (ModernGL + Pygame).

Place ``shake_it_off.mp3`` next to this script (or pass ``--audio``).
If missing, a generated stub / procedural fallback is used.

Examples:
  python shake_it_off_mv.py
  python shake_it_off_mv.py --export -o shake_it_off.mp4
  python shake_it_off_mv.py --screenshot-at 20 --screenshot-path shot.png
  python shake_it_off_mv.py --scene pagoda --start 190 --duration 8
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pygame
from pygame.locals import DOUBLEBUF, OPENGL

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sio import FPS, HEIGHT, SONG_DURATION, WIDTH
from sio.audio import AudioEngine, resolve_audio_path
from sio.pipeline import Pipeline
from sio.scenes import SceneManager, scene_id_at


def parse_args():
    p = argparse.ArgumentParser(description="Shake It Off Himalayan synthwave visualizer")
    p.add_argument("--export", "-e", action="store_true", help="Export MP4 via ffmpeg")
    p.add_argument("--output", "-o", type=Path, default=ROOT / "shake_it_off.mp4")
    p.add_argument("--audio", type=Path, default=None, help="Path to shake_it_off.mp3")
    p.add_argument("--no-preview", action="store_true", help="Headless SDL video driver")
    p.add_argument("--scene", type=str, default=None, help="Force scene id")
    p.add_argument("--start", type=float, default=0.0, help="Start time (seconds)")
    p.add_argument("--duration", type=float, default=None, help="Limit duration")
    p.add_argument("--screenshot-at", type=float, default=None, help="Capture one frame at time")
    p.add_argument("--screenshot-path", type=Path, default=ROOT / "screenshot.png")
    p.add_argument("--hud", action="store_true", help="Burn HUD/banners into screenshots & exports")
    return p.parse_args()


def make_gl_window(width: int, height: int, title: str, headless: bool):
    # Prefer a real display; fall back to available driver.
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    elif not os.environ.get("SDL_VIDEODRIVER"):
        os.environ.setdefault("SDL_VIDEODRIVER", "x11")
    pygame.init()
    try:
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.mixer.init()
    except pygame.error:
        pass
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)
    try:
        pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
    except pygame.error:
        # Last resort: try without forcing dummy earlier
        if headless:
            raise
        os.environ["SDL_VIDEODRIVER"] = "x11"
        pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption(title)


class FfmpegRecorder:
    def __init__(self, output: Path, fps: int, width: int, height: int, audio_path: Path | None):
        self.output = Path(output)
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{width}x{height}", "-pix_fmt", "rgb24",
            "-r", str(fps), "-i", "-",
        ]
        self.has_audio = audio_path is not None and Path(audio_path).is_file()
        if self.has_audio:
            cmd.extend(["-i", str(audio_path)])
        cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"])
        if self.has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.append("-an")
        cmd.append(str(self.output))
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        self.frames = 0

    def write(self, rgb_bytes: bytes):
        assert self.proc.stdin is not None
        self.proc.stdin.write(rgb_bytes)
        self.frames += 1

    def close(self) -> Path:
        if self.proc.stdin:
            self.proc.stdin.close()
        stderr = self.proc.stderr.read().decode("utf-8", errors="replace") if self.proc.stderr else ""
        rc = self.proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed ({rc}):\n{stderr[-2000:]}")
        return self.output


def apply_hud(rgb: bytes, t: float, fps_val: float, scene: str, banner, enabled: bool) -> bytes:
    if not enabled and banner is None:
        return rgb
    arr = np.frombuffer(rgb, dtype=np.uint8).reshape((HEIGHT, WIDTH, 3)).copy()
    surf = pygame.image.frombuffer(arr.tobytes(), (WIDTH, HEIGHT), "RGB").convert()
    font = pygame.font.SysFont("dejavusansmono", 18)
    big = pygame.font.SysFont("dejavusansmono", 28, bold=True)
    if enabled:
        for i, line in enumerate((f"SHAKE IT OFF | {scene.upper()}", f"t={t:06.2f}  fps={fps_val:5.1f}")):
            img = font.render(line, True, (240, 240, 255))
            surf.blit(img, (12, 10 + i * 22))
    if banner:
        for i, text in enumerate(banner):
            img = big.render(str(text), True, (255, 220, 80) if i == 0 else (120, 220, 255))
            rect = img.get_rect(center=(WIDTH // 2, HEIGHT - 90 + i * 34))
            pad = pygame.Surface((rect.width + 24, rect.height + 10), pygame.SRCALPHA)
            pad.fill((0, 0, 0, 150))
            surf.blit(pad, (rect.x - 12, rect.y - 5))
            surf.blit(img, rect)
    return pygame.image.tostring(surf, "RGB")


def main():
    args = parse_args()
    headless = bool(args.no_preview or args.screenshot_at is not None)
    # OpenGL on dummy driver fails — for screenshots/export use x11 when available
    if headless and os.environ.get("DISPLAY"):
        headless = False
        os.environ["SDL_VIDEODRIVER"] = "x11"
    make_gl_window(WIDTH, HEIGHT, "Shake It Off — Himalayan Synthwave", headless=headless)

    import moderngl

    ctx = moderngl.create_context()
    pipe = Pipeline(ctx, WIDTH, HEIGHT)
    scenes = SceneManager(pipe)

    audio_path = resolve_audio_path(ROOT, args.audio)
    engine = AudioEngine(audio_path)
    print(f"Audio: {audio_path if audio_path else '(procedural stub)'}")

    playing_music = False
    if audio_path and not args.export and args.screenshot_at is None:
        try:
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play(start=max(0.0, args.start))
            playing_music = True
        except pygame.error as exc:
            print(f"Warning: could not play audio ({exc})")

    duration = args.duration if args.duration is not None else (SONG_DURATION - args.start)
    duration = max(0.1, min(duration, SONG_DURATION - args.start))

    recorder = FfmpegRecorder(args.output, FPS, WIDTH, HEIGHT, audio_path) if args.export else None

    clock = pygame.time.Clock()
    start_wall = time.perf_counter()
    frame = 0
    force = args.scene

    if args.screenshot_at is not None:
        t = float(args.screenshot_at)
        audio = engine.analyze(t)
        scenes.render(t, audio, force_scene=force)
        rgb = apply_hud(
            pipe.read_rgb(), t, 60.0, force or scene_id_at(t), scenes.active_banner, True
        )
        arr = np.frombuffer(rgb, dtype=np.uint8).reshape((HEIGHT, WIDTH, 3))
        surf = pygame.image.frombuffer(arr.tobytes(), (WIDTH, HEIGHT), "RGB")
        args.screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(surf, str(args.screenshot_path))
        print(f"Wrote {args.screenshot_path}")
        pygame.quit()
        return

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False

        if args.export:
            t = args.start + frame / float(FPS)
            if t >= args.start + duration:
                break
            dt = 1.0 / FPS
        else:
            if playing_music:
                pos = pygame.mixer.music.get_pos()
                t = (pos / 1000.0 + args.start) if pos >= 0 else args.start + (time.perf_counter() - start_wall)
            else:
                t = args.start + (time.perf_counter() - start_wall)
            if t >= args.start + duration:
                break
            dt = max(clock.get_time() / 1000.0, 1e-3)

        audio = engine.analyze(t, dt)
        scenes.render(t, audio, force_scene=force)

        if recorder is not None:
            rgb = pipe.read_rgb()
            if args.hud or scenes.active_banner:
                rgb = apply_hud(rgb, t, FPS, force or scene_id_at(t), scenes.active_banner, args.hud)
            recorder.write(rgb)
            if frame % 30 == 0:
                print(f"export {t:6.2f}s / {args.start + duration:.1f}s  scene={force or scene_id_at(t)}")
        else:
            pipe.blit_to_screen()
            pygame.display.flip()
            clock.tick(FPS)

        frame += 1

    if recorder is not None:
        out = recorder.close()
        print(f"Wrote {out} ({recorder.frames} frames)")

    pygame.quit()


if __name__ == "__main__":
    main()
