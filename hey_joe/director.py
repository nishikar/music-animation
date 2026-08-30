"""Director: timeline, crossfades, render orchestration."""

from __future__ import annotations

from typing import Optional, Tuple

import cairo

from hey_joe import config as C
from hey_joe.canvas import CairoCanvas
from hey_joe.geometry import clamp, set_rgb
from hey_joe.scenes import SCENE_CLASSES


class Director:
    def __init__(self, width: int = C.WIDTH, height: int = C.HEIGHT):
        self.w = width
        self.h = height
        self.canvas = CairoCanvas(width, height)
        self.scenes = {key: cls(width, height) for key, cls in SCENE_CLASSES.items()}
        # Offscreen for crossfade
        self._fade_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self._fade_ctx = cairo.Context(self._fade_surface)

    def scene_at(self, t: float) -> Tuple[str, float, float, float]:
        """Return (name, local_t, progress, scene_index)."""
        t = clamp(t, 0.0, C.SONG_DURATION)
        for i, (start, end, name) in enumerate(C.SCENE_TIMES):
            if t < end or i == len(C.SCENE_TIMES) - 1:
                local = t - start
                dur = max(end - start, 1e-6)
                return name, local, clamp(local / dur), float(i)
        name = C.SCENE_TIMES[-1][2]
        start, end, _ = C.SCENE_TIMES[-1]
        local = t - start
        return name, local, 1.0, float(len(C.SCENE_TIMES) - 1)

    def _transition_weight(self, t: float) -> Tuple[Optional[str], Optional[str], float]:
        """If near a boundary, return (prev, next, blend) where blend→1 means fully next."""
        for i in range(1, len(C.SCENE_TIMES)):
            boundary = C.SCENE_TIMES[i][0]
            half = C.TRANSITION_SEC * 0.5
            if abs(t - boundary) <= half:
                # map [-half, +half] → [0, 1]
                blend = clamp((t - (boundary - half)) / C.TRANSITION_SEC)
                prev = C.SCENE_TIMES[i - 1][2]
                nxt = C.SCENE_TIMES[i][2]
                return prev, nxt, blend
        return None, None, 0.0

    def render(self, t: float) -> cairo.Context:
        ctx = self.canvas.ctx
        self.canvas.clear((0, 0, 0, 1))

        prev, nxt, blend = self._transition_weight(t)
        if prev and nxt and 0.0 < blend < 1.0:
            # draw prev into main
            self._draw_scene(ctx, prev, t)
            # draw next into fade surface
            fctx = self._fade_ctx
            fctx.set_operator(cairo.OPERATOR_CLEAR)
            fctx.paint()
            fctx.set_operator(cairo.OPERATOR_OVER)
            self._draw_scene(fctx, nxt, t)
            # composite with alpha
            ctx.set_source_surface(self._fade_surface, 0, 0)
            ctx.paint_with_alpha(blend)
        else:
            name, _, _, _ = self.scene_at(t)
            self._draw_scene(ctx, name, t)

        return ctx

    def _draw_scene(self, ctx: cairo.Context, name: str, t: float):
        # Find timing for this named scene
        start = 0.0
        end = C.SONG_DURATION
        for s, e, n in C.SCENE_TIMES:
            if n == name:
                start, end = s, e
                break
        local = max(0.0, t - start)
        progress = clamp(local / max(end - start, 1e-6))
        scene = self.scenes[name]
        scene.draw(ctx, t, local, progress)

    def render_pygame(self, screen, t: float, hud: bool = False):
        self.render(t)
        self.canvas.blit_to(screen)
        if hud:
            self._draw_hud(screen, t)

    def _draw_hud(self, screen, t: float):
        import pygame

        name, local, progress, idx = self.scene_at(t)
        font = pygame.font.SysFont("dejavusans", 16, bold=True)
        mins = int(t) // 60
        secs = int(t) % 60
        label = f"S{int(idx)+1}:{name.upper()}  {mins:02d}:{secs:02d} / 07:51  local={local:05.1f}s"
        bar = pygame.Surface((self.w, 28), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 160))
        screen.blit(bar, (0, 0))
        txt = font.render(label, True, (240, 210, 120))
        screen.blit(txt, (16, 5))
        # progress tick
        pygame.draw.rect(screen, (80, 60, 20), (0, 28, self.w, 3))
        pygame.draw.rect(screen, (240, 190, 60), (0, 28, int(self.w * (t / C.SONG_DURATION)), 3))
