"""Scene base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

import cairo


class Scene(ABC):
    """Each scene draws Background then Foreground into the same context."""

    name: str = "scene"

    def __init__(self, width: int, height: int):
        self.w = width
        self.h = height
        self.cx = width / 2.0
        self.cy = height / 2.0

    @abstractmethod
    def draw_bg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        """Background layer. progress ∈ [0,1] within scene."""

    @abstractmethod
    def draw_fg(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        """Foreground layer."""

    def draw(self, ctx: cairo.Context, t: float, local_t: float, progress: float):
        self.draw_bg(ctx, t, local_t, progress)
        self.draw_fg(ctx, t, local_t, progress)
