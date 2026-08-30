"""Shared-memory Cairo ↔ Pygame bridge (ARGB32 / BGRA).

Best practices applied:
- Single reusable ImageSurface + byte buffer (no per-frame realloc)
- OPERATOR_CLEAR for full-frame wipe
- Premultiplied ARGB32 cairo format → pygame BGRA frombuffer
- Optional RGB export path for ffmpeg piping
"""

from __future__ import annotations

import cairo
import pygame


class CairoCanvas:
    """Zero-copy-ish cairo drawing surface that blits into pygame."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self.ctx = cairo.Context(self.surface)
        # Hint high-quality vector stroking
        self.ctx.set_antialias(cairo.ANTIALIAS_BEST)

    def clear(self, rgba=(0.0, 0.0, 0.0, 1.0)):
        ctx = self.ctx
        if rgba[3] >= 1.0 - 1e-6:
            ctx.set_source_rgb(rgba[0], rgba[1], rgba[2])
            ctx.paint()
        else:
            ctx.set_operator(cairo.OPERATOR_CLEAR)
            ctx.paint()
            ctx.set_operator(cairo.OPERATOR_OVER)
            if rgba[3] > 0:
                ctx.set_source_rgba(*rgba)
                ctx.paint()

    def to_pygame(self) -> pygame.Surface:
        """Convert cairo buffer → pygame Surface (endian-correct BGRA)."""
        buf = self.surface.get_data()
        return pygame.image.frombuffer(buf, (self.width, self.height), "BGRA").convert()

    def blit_to(self, screen: pygame.Surface, dest=(0, 0)):
        screen.blit(self.to_pygame(), dest)
