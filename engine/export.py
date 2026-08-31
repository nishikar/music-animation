"""Zero-allocation FFmpeg pipe exporter for 1080p MP4."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class FFmpegExporter:
    def __init__(
        self,
        output: Path,
        width: int,
        height: int,
        fps: int,
        audio_path: Optional[Path] = None,
        duration: float = 337.0,
    ):
        self.output = Path(output)
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_bytes = width * height * 4  # RGBA
        self._proc: Optional[subprocess.Popen] = None
        self.frames_written = 0

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "-",
        ]
        has_audio = audio_path is not None and Path(audio_path).is_file()
        if has_audio:
            cmd.extend(["-i", str(audio_path)])

        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ]
        )
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.extend(["-t", str(duration)])
        cmd.append(str(self.output))

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write_rgba(self, data: memoryview | bytes) -> None:
        if self._proc is None or self._proc.stdin is None:
            return
        self._proc.stdin.write(data)
        self.frames_written += 1

    def close(self) -> Path:
        if self._proc is None:
            return self.output
        if self._proc.stdin:
            self._proc.stdin.close()
        stderr = b""
        if self._proc.stderr:
            stderr = self._proc.stderr.read()
        rc = self._proc.wait()
        self._proc = None
        if rc != 0:
            msg = stderr.decode("utf-8", errors="replace")[-2500:]
            raise RuntimeError(f"ffmpeg failed (exit {rc}):\n{msg}")
        return self.output
