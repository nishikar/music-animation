#!/usr/bin/env python3
"""Desecration Smile — ModernGL + Pygame music video engine.

Preview:  python main.py
          python main.py --preview
Export:   python main.py --export
          python main.py --export --output out.mp4
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pygame

from engine.audio import AudioClock, ensure_audio
from engine.config import (
    DEFAULT_EXPORT_PATH,
    EXPORT_HEIGHT,
    EXPORT_WIDTH,
    FPS,
    PREVIEW_HEIGHT,
    PREVIEW_WIDTH,
    SONG_DURATION,
    TOTAL_FRAMES,
)
from engine.context import create_app, pump_events
from engine.export import FFmpegExporter
from scenes.timeline import evaluate_frame
from scenes.world import WorldRenderer


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Desecration Smile — ModernGL music video")
    p.add_argument("--preview", action="store_true", help="Interactive real-time preview (default)")
    p.add_argument("--export", action="store_true", help="Offline 1080p MP4 export via ffmpeg")
    p.add_argument("--output", "-o", type=Path, default=DEFAULT_EXPORT_PATH, help="Export MP4 path")
    p.add_argument("--start", type=float, default=0.0, help="Start time in seconds")
    p.add_argument("--duration", type=float, default=None, help="Override duration (seconds)")
    p.add_argument("--no-audio", action="store_true", help="Mute preview audio")
    p.add_argument("--headless", action="store_true", help="Force SDL dummy driver (export)")
    return p.parse_args(argv)


def run_preview(args) -> int:
    width, height = PREVIEW_WIDTH, PREVIEW_HEIGHT
    app = create_app(width, height, title="Desecration Smile — Preview", headless=False)
    world = WorldRenderer(app.ctx, width, height)
    audio_path = ensure_audio()
    clock_audio = AudioClock(audio_path, start_muted=args.no_audio)
    clock_audio.play(args.start)

    frame0 = int(args.start * FPS)
    duration = args.duration if args.duration is not None else SONG_DURATION - args.start
    frame_end = frame0 + int(duration * FPS)
    frame_end = min(frame_end, TOTAL_FRAMES)

    clock = pygame.time.Clock()
    running = True
    frame_idx = frame0
    print(f"[preview] audio={audio_path} frames={frame0}..{frame_end} @ {FPS}fps")

    while running and frame_idx < frame_end:
        running = pump_events()
        t = frame_idx / float(FPS)
        frame = evaluate_frame(t)
        world.render_frame(frame, display=True)
        pygame.display.flip()
        clock.tick(FPS)
        frame_idx += 1

    clock_audio.stop()
    pygame.quit()
    return 0


def run_export(args) -> int:
    width, height = EXPORT_WIDTH, EXPORT_HEIGHT
    # Prefer a real X11/GLX context (xvfb or local display). Only use the SDL
    # dummy driver when explicitly requested — it cannot create OpenGL contexts.
    headless = bool(args.headless)
    app = create_app(width, height, title="Desecration Smile — Export", headless=headless)
    world = WorldRenderer(app.ctx, width, height)
    audio_path = ensure_audio()

    frame0 = int(args.start * FPS)
    duration = args.duration if args.duration is not None else SONG_DURATION - args.start
    total = int(duration * FPS)
    frame_end = min(frame0 + total, TOTAL_FRAMES)

    exporter = FFmpegExporter(
        output=args.output,
        width=width,
        height=height,
        fps=FPS,
        audio_path=audio_path,
        duration=duration,
    )

    print(f"[export] {width}x{height} @ {FPS}fps → {args.output}")
    print(f"[export] audio={audio_path} frames={frame0}..{frame_end} ({frame_end - frame0})")

    t0 = time.time()
    try:
        for frame_idx in range(frame0, frame_end):
            if frame_idx % 90 == 0:
                # keep event queue drained
                pump_events()
                done = frame_idx - frame0
                elapsed = time.time() - t0
                fps_now = done / max(elapsed, 1e-3)
                eta = (frame_end - frame_idx) / max(fps_now, 1e-3)
                print(f"  frame {frame_idx}/{frame_end}  ({fps_now:.1f} fps, ETA {eta/60:.1f}m)")

            t = frame_idx / float(FPS)
            frame = evaluate_frame(t)
            world.render_frame(frame, display=False)
            mv = world.post.read_final_into()
            exporter.write_rgba(mv)
    except Exception:
        exporter.close()
        raise

    out = exporter.close()
    elapsed = time.time() - t0
    print(f"[export] done → {out} ({exporter.frames_written} frames in {elapsed:.1f}s)")
    pygame.quit()
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.export:
        return run_export(args)
    return run_preview(args)


if __name__ == "__main__":
    sys.exit(main())
