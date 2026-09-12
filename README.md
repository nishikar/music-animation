# Shake It Off — Himalayan Synthwave Visualizer

Production-style music visualizer built with **ModernGL** + **Pygame**, driven by FFT / beat analysis and a six-scene Himalayan synthwave timeline.

## Requirements

- Python 3.10+
- macOS / Linux / Windows with OpenGL 3.3+
- ffmpeg on `PATH` (for `--export`)

```bash
pip install -r requirements.txt
```

## Audio

Place your track as `shake_it_off.mp3` next to `shake_it_off_mv.py` (118 BPM, 4:32 cover).

If missing, the app falls back to `shake_it_off_stub.mp3` (included) or a procedural beat.

```bash
# optional override
python shake_it_off_mv.py --audio /path/to/shake_it_off.mp3
```

## Run

```bash
# Interactive (Esc / Q to quit)
python shake_it_off_mv.py

# Force a scene while previewing
python shake_it_off_mv.py --scene corridor --start 80 --duration 20

# Screenshot a moment
python shake_it_off_mv.py --screenshot-at 20 --screenshot-path mountain.png

# Export MP4 (muxes audio when available)
python shake_it_off_mv.py --export -o shake_it_off.mp4
```

## Timeline

| Time | Scene |
|------|-------|
| 0:00–0:41 | Mountain Pass & Temple Bell |
| 0:41–1:12 | Sacred Mandala & Marigold Storm |
| 1:12–2:38 | Infinite Prayer-Wheel Corridor |
| 2:38–3:06 | Chai Stall Arcade Intermission |
| 3:06–3:55 | Golden Pagoda Overdrive |
| 3:55–4:32 | Himalayan Twilight Dissolve |

## macOS notes

- Uses an OpenGL 3.3 **core** profile via Pygame/Cocoa (do **not** set `SDL_VIDEODRIVER=x11`).
- Install deps: `pip install -r requirements.txt` and `brew install ffmpeg`
- Run from Terminal.app / iTerm (a normal GUI login session).
- On Apple Silicon, use a native Python/venv for best performance.
