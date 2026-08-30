# Hey Joe — Music Visualization

Production-grade layered vector animation driven by **pycairo** + **pygame**, scored to `hey_joe.mp3` (7:51).

## Setup

```bash
# System
sudo apt-get install -y libcairo2-dev pkg-config ffmpeg

# Python
pip install -r requirements-hey-joe.txt
```

Place your audio file beside the runner:

```text
hey_joe.mp3
```

## Run

```bash
# Interactive (Space=pause, ←/→ skip 10s, H=HUD, Esc=quit)
python hey_joe_mv.py
python hey_joe_mv.py --hud

# Headless MP4 export (muxes hey_joe.mp3 when present)
python hey_joe_mv.py --export --no-preview -o hey_joe.mp4

# Partial export
python hey_joe_mv.py --export --no-preview --start 240 --duration 30 -o jhala_clip.mp4

# Scene midpoints demo reel (~18s)
python hey_joe_mv.py --preview-scenes --no-preview

# Stills
python hey_joe_mv.py --no-preview --screenshot 20 --screenshot 280 -o shots/
```

## Scenes

| # | Time | Key |
|---|------|-----|
| 1 | 0:00–0:45 | Primordial Resonance / Nada Brahma |
| 2 | 0:45–1:30 | The Revolving Enigma |
| 3 | 1:30–2:20 | The Flare of Raudra |
| 4 | 2:20–3:05 | Fatal Descent & Paisley Tears |
| 5 | 3:05–4:00 | Polyrhythmic Confession |
| 6 | 4:00–5:20 | Jhala Vortex |
| 7 | 5:20–6:20 | Desert Flight South |
| 8 | 6:20–7:15 | Unraveling Noose & Wings |
| 9 | 7:15–7:51 | Dissolution / Samadhi |

Each scene renders a **Background** layer then a **Foreground** layer. Soft crossfades bridge scene boundaries.

## Architecture

```text
hey_joe_mv.py          CLI / playback / ffmpeg export
hey_joe/
  canvas.py            shared ARGB32 ↔ pygame BGRA bridge
  config.py            timeline, palette, paths
  geometry.py          lotus, yantra, paisley, chakra, spirals…
  director.py          scene clock + transitions
  scenes/              one module per scene (BG/FG)
```
