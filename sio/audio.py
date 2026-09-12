"""Audio loading, stub fallback, FFT bands, and beat detection."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from . import BEAT_SEC, BPM, SONG_DURATION


class AudioAnalysis:
    __slots__ = ("bass", "mid", "treble", "amp", "spectrum", "beat", "drop")

    def __init__(self):
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self.amp = 0.0
        self.spectrum = np.zeros(64, dtype=np.float32)
        self.beat = False
        self.drop = False


class AudioEngine:
    """Offline sample buffer + live FFT driven by song time."""

    def __init__(self, path: Path | None, duration: float = SONG_DURATION):
        self.duration = duration
        self.sample_rate = 44100
        self.samples = None  # mono float32
        self._bass_hist = []
        self._prev_bass = 0.0
        self._beat_cooldown = 0.0
        self.path = path
        if path and path.is_file():
            self._load(path)
        else:
            self._synthesize_stub()

    def _load(self, path: Path):
        # Decode via ffmpeg to raw mono f32
        import subprocess
        import tempfile
        import os

        raw = Path(tempfile.gettempdir()) / f"sio_decode_{path.stem}.f32"
        cmd = [
            "ffmpeg", "-y", "-i", str(path),
            "-ac", "1", "-ar", str(self.sample_rate),
            "-f", "f32le", str(raw),
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            data = np.fromfile(raw, dtype=np.float32)
            self.samples = data
            self.duration = len(data) / self.sample_rate
            try:
                os.remove(raw)
            except OSError:
                pass
        except Exception:
            self._synthesize_stub()

    def _synthesize_stub(self):
        sr = self.sample_rate
        n = int(sr * self.duration)
        t = np.arange(n, dtype=np.float32) / sr
        audio = np.zeros(n, dtype=np.float32)
        kick = 0
        while True:
            start = int(kick * BEAT_SEC * sr)
            if start >= n:
                break
            length = int(0.12 * sr)
            end = min(n, start + length)
            lt = np.arange(end - start, dtype=np.float32) / sr
            env = np.exp(-lt * 28)
            freq = 80 * np.exp(-lt * 20)
            audio[start:end] += 0.85 * env * np.sin(2 * np.pi * freq * lt)
            if kick % 8 == 0:
                length2 = int(0.22 * sr)
                end2 = min(n, start + length2)
                lt2 = np.arange(end2 - start, dtype=np.float32) / sr
                audio[start:end2] += 0.5 * np.exp(-lt2 * 12) * np.sin(2 * np.pi * 55 * lt2)
            kick += 1
        # hats
        hh = 0
        rng = np.random.default_rng(7)
        while True:
            start = int(hh * BEAT_SEC * 0.5 * sr)
            if start >= n:
                break
            length = int(0.035 * sr)
            end = min(n, start + length)
            noise = rng.standard_normal(end - start).astype(np.float32)
            env = np.exp(-np.arange(end - start, dtype=np.float32) / sr * 70)
            audio[start:end] += 0.1 * noise * env
            hh += 1
        self.samples = np.clip(audio, -1, 1)

    def analyze(self, time_sec: float, dt: float = 1 / 60) -> AudioAnalysis:
        out = AudioAnalysis()
        if self.samples is None or len(self.samples) == 0:
            # procedural fallback from BPM
            phase = (time_sec % BEAT_SEC) / BEAT_SEC
            pulse = math.exp(-phase * 8) 
            out.bass = pulse
            out.amp = pulse * 0.6
            out.spectrum[:] = pulse * np.linspace(1, 0.2, 64)
            out.beat = phase < 0.08
            out.drop = (int(time_sec / BEAT_SEC) % 8 == 0) and out.beat
            return out

        sr = self.sample_rate
        center = int(time_sec * sr)
        win = 2048
        i0 = max(0, center - win // 2)
        i1 = min(len(self.samples), i0 + win)
        chunk = np.zeros(win, dtype=np.float32)
        chunk[: i1 - i0] = self.samples[i0:i1]
        chunk *= np.hanning(win).astype(np.float32)
        spec = np.abs(np.fft.rfft(chunk))
        spec = spec / (np.max(spec) + 1e-6)

        # bands
        freqs = np.fft.rfftfreq(win, 1 / sr)
        def band(lo, hi):
            mask = (freqs >= lo) & (freqs < hi)
            if not np.any(mask):
                return 0.0
            return float(np.sqrt(np.mean(spec[mask] ** 2)))

        bass = band(30, 150)
        mid = band(150, 2000)
        treble = band(2000, 8000)
        amp = float(np.sqrt(np.mean(chunk ** 2))) * 4.0

        # smooth spectrum down to 64 bins
        usable = spec[1:513]
        bins = np.zeros(64, dtype=np.float32)
        step = max(1, len(usable) // 64)
        for i in range(64):
            bins[i] = float(np.mean(usable[i * step : (i + 1) * step]))
        bins = bins / (np.max(bins) + 1e-6)

        self._bass_hist.append(bass)
        if len(self._bass_hist) > 43:
            self._bass_hist.pop(0)
        mean = sum(self._bass_hist) / len(self._bass_hist)
        std = (sum((b - mean) ** 2 for b in self._bass_hist) / len(self._bass_hist)) ** 0.5

        self._beat_cooldown = max(0.0, self._beat_cooldown - dt)
        beat = False
        drop = False
        if self._beat_cooldown <= 0 and bass > mean + 1.25 * (std + 0.02) and bass > self._prev_bass:
            beat = True
            self._beat_cooldown = BEAT_SEC * 0.45
            if bass > mean + 2.0 * (std + 0.02):
                drop = True

        out.bass = min(1.0, bass * 1.8)
        out.mid = min(1.0, mid * 1.6)
        out.treble = min(1.0, treble * 1.5)
        out.amp = min(1.0, amp)
        out.spectrum = bins
        out.beat = beat
        out.drop = drop
        self._prev_bass = bass
        return out


def resolve_audio_path(script_dir: Path, override: Path | None = None) -> Path | None:
    if override is not None:
        return override if override.is_file() else None
    from . import AUDIO_CANDIDATES

    for name in AUDIO_CANDIDATES:
        for base in (script_dir, Path.cwd()):
            p = base / name
            if p.is_file():
                return p
    return None
