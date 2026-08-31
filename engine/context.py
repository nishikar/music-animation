"""Pygame window + ModernGL 3.3 Core context bootstrap."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

import moderngl
import pygame


@dataclass
class GLApp:
    ctx: moderngl.Context
    width: int
    height: int
    screen: Optional[pygame.Surface]
    headless: bool


def create_app(
    width: int,
    height: int,
    title: str = "Desecration Smile",
    headless: bool = False,
) -> GLApp:
    if headless:
        # SDL dummy has no OpenGL — only use when an offscreen GL loader is provided.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    else:
        # Prefer X11 when available (Cloud Agent / xvfb).
        os.environ.setdefault("SDL_VIDEODRIVER", os.environ.get("SDL_VIDEODRIVER", "x11"))

    # mixer must be configured before pygame.init()
    try:
        pygame.mixer.pre_init(44100, -16, 2, 1024)
    except pygame.error:
        pass
    pygame.init()
    pygame.display.set_caption(title)

    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, 1)
    pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)
    pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)

    flags = pygame.OPENGL | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((width, height), flags)

    # Share the pygame-created context with ModernGL (standalone=False).
    try:
        ctx = moderngl.create_context(require=330, standalone=False)
    except Exception:
        ctx = moderngl.create_context(require=330)
    ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND | moderngl.CULL_FACE)
    ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
    ctx.viewport = (0, 0, width, height)
    return GLApp(ctx=ctx, width=width, height=height, screen=screen, headless=headless)


def pump_events() -> bool:
    """Return False if the user requested quit."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return False
    return True
