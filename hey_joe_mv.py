#!/usr/bin/env python3
"""
Hey Joe — production music visualization (pycairo + pygame).

Scenes follow the nine-part Nada Brahma → Samadhi arc (0:00–7:51).
Audio: hey_joe.mp3 (place beside this script).

Usage:
  python hey_joe_mv.py                  # interactive playback
  python hey_joe_mv.py --hud            # with timecode overlay
  python hey_joe_mv.py --export -o out.mp4
  python hey_joe_mv.py --export --no-preview
  python hey_joe_mv.py --screenshot 45 --screenshot 140 -o shots
  python hey_joe_mv.py --preview-scenes  # 2s per scene demo reel
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure package import when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pygame

from hey_joe import config as C
from hey_joe.director import Director


class FfmpegRecorder:
    """Pipe raw RGB frames to ffmpeg; mux hey_joe.mp3 when present."""

    def __init__(self, output_path, fps, width, height, audio_path, duration):
        self.output_path = Path(output_path)
        self._proc = None
        self.frames_written = 0
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{width}x{height}", "-pix_fmt", "rgb24",
            "-r", str(fps), "-i", "-",
        ]
        self._has_audio = audio_path is not None and Path(audio_path).is_file()
        if self._has_audio:
            cmd.extend(["-i", str(audio_path)])
        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
        ])
        if self._has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.extend(["-t", str(duration)])
        cmd.append(str(self.output_path))
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    def write_frame(self, surface):
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
    p = argparse.ArgumentParser(description="Hey Joe pycairo/pygame music visualization")
    p.add_argument("--export", "-e", action="store_true", help="Render MP4 via ffmpeg")
    p.add_argument("--output", "-o", type=Path, default=None, help="Output MP4 or screenshot dir")
    p.add_argument("--no-preview", action="store_true", help="Headless (SDL dummy driver)")
    p.add_argument("--hud", action="store_true", help="Show timecode HUD")
    p.add_argument("--fps", type=int, default=C.FPS)
    p.add_argument("--start", type=float, default=0.0, help="Start time seconds")
    p.add_argument("--duration", type=float, default=None, help="Limit duration seconds")
    p.add_argument(
        "--screenshot", type=float, action="append", default=[],
        help="Save PNG at given timestamp (repeatable)",
    )
    p.add_argument(
        "--preview-scenes", action="store_true",
        help="Export short demo: 2 seconds from each scene midpoint",
    )
    p.add_argument("--audio", type=Path, default=C.AUDIO_FILE, help="Path to hey_joe.mp3")
    return p.parse_args()


def init_display(args):
    if args.no_preview or (args.export and args.no_preview):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass
    flags = 0
    if args.no_preview:
        screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    else:
        screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    pygame.display.set_caption("Hey Joe — Nada Brahma → Samadhi")
    return screen


def save_screenshots(director, times, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    # temp pygame surface
    surf = pygame.Surface((C.WIDTH, C.HEIGHT))
    paths = []
    for t in times:
        director.render_pygame(surf, t, hud=True)
        name, _, _, idx = director.scene_at(t)
        path = out_dir / f"scene{int(idx)+1:02d}_{name}_{int(t):04d}s.png"
        pygame.image.save(surf, str(path))
        paths.append(path)
        print(f"[shot] t={t:.1f}s → {path.name}")
    return paths


def run_preview_scenes_export(director, screen, args):
    """2s clip from each scene midpoint → demo MP4."""
    out = args.output or (C.SCRIPT_DIR / "hey_joe_scenes_preview.mp4")
    fps = args.fps
    # Build timestamp list
    stamps = []
    for start, end, name in C.SCENE_TIMES:
        mid = (start + end) / 2.0
        for i in range(int(2 * fps)):
            stamps.append(mid - 1.0 + i / fps)
    rec = FfmpegRecorder(out, fps, C.WIDTH, C.HEIGHT, None, duration=len(stamps) / fps)
    clock_t0 = time.time()
    for i, t in enumerate(stamps):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                break
        director.render_pygame(screen, max(0.0, t), hud=True)
        if not args.no_preview:
            pygame.display.flip()
        rec.write_frame(screen)
        if i % 30 == 0:
            print(f"[preview] frame {i}/{len(stamps)}")
    rec.close()
    print(f"[preview] wrote {out} in {time.time() - clock_t0:.1f}s")
    return out


def run_export(director, screen, args):
    out = args.output or C.DEFAULT_EXPORT
    start = args.start
    duration = args.duration if args.duration is not None else (C.SONG_DURATION - start)
    fps = args.fps
    n_frames = int(duration * fps)
    rec = FfmpegRecorder(out, fps, C.WIDTH, C.HEIGHT, args.audio, duration)
    t0 = time.time()
    for i in range(n_frames):
        t = start + i / fps
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                n_frames = i
                break
        director.render_pygame(screen, t, hud=args.hud)
        if not args.no_preview:
            pygame.display.flip()
        rec.write_frame(screen)
        if i % (fps * 5) == 0:
            elapsed = time.time() - t0
            eta = (elapsed / max(i, 1)) * (n_frames - i)
            print(f"[export] {i}/{n_frames} t={t:.1f}s elapsed={elapsed:.0f}s eta={eta:.0f}s")
    path = rec.close()
    print(f"[export] done → {path} ({n_frames} frames)")
    return path


def run_interactive(director, screen, args):
    clock = pygame.time.Clock()
    audio = Path(args.audio)
    if audio.is_file():
        try:
            pygame.mixer.music.load(str(audio))
            pygame.mixer.music.play()
            if args.start > 0:
                pygame.mixer.music.set_pos(args.start)
            print(f"[audio] playing {audio.name}")
        except Exception as e:
            print(f"[audio] could not play ({e}); continuing silent")
    else:
        print(f"[audio] {audio} not found — silent preview (add hey_joe.mp3 later)")

    anim_t = args.start
    running = True
    paused = False
    while running:
        dt = clock.tick(args.fps) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                    if audio.is_file():
                        if paused:
                            pygame.mixer.music.pause()
                        else:
                            pygame.mixer.music.unpause()
                elif event.key == pygame.K_RIGHT:
                    anim_t = min(C.SONG_DURATION, anim_t + 10.0)
                elif event.key == pygame.K_LEFT:
                    anim_t = max(0.0, anim_t - 10.0)
                elif event.key == pygame.K_h:
                    args.hud = not args.hud

        if not paused:
            anim_t += dt
            if anim_t >= C.SONG_DURATION:
                anim_t = 0.0
                if audio.is_file() and pygame.mixer.get_init():
                    try:
                        pygame.mixer.music.play()
                    except Exception:
                        pass

        director.render_pygame(screen, anim_t, hud=args.hud)
        pygame.display.flip()


def main():
    args = parse_args()
    if args.no_preview:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    screen = init_display(args)
    director = Director(C.WIDTH, C.HEIGHT)

    try:
        if args.screenshot:
            out_dir = args.output if args.output and args.output.suffix == "" or (
                args.output and not str(args.output).endswith(".mp4")
            ) else (C.SCRIPT_DIR / "hey_joe_shots")
            if args.output and args.output.suffix.lower() == ".mp4":
                out_dir = C.SCRIPT_DIR / "hey_joe_shots"
            elif args.output:
                out_dir = args.output
            else:
                out_dir = C.SCRIPT_DIR / "hey_joe_shots"
            save_screenshots(director, args.screenshot, Path(out_dir))
        elif args.preview_scenes:
            if args.no_preview:
                os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            run_preview_scenes_export(director, screen, args)
        elif args.export:
            run_export(director, screen, args)
        else:
            run_interactive(director, screen, args)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
