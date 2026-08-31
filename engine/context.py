"""Pygame window + ModernGL 3.3 Core context bootstrap."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

import moderngl
import pygame


@dataclass
class GLApp:
    ctx: moderngl.Context
    width: int
    height: int
    screen: Optional[pygame.Surface]
    headless: bool


def _configure_sdl_video(headless: bool) -> None:
    """Pick a sane SDL video driver without breaking macOS / Windows."""
    if headless:
        # SDL dummy cannot create an OpenGL context — only useful for non-GL tests.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        return

    # Never force x11 on Darwin/Windows — Cocoa / Windows drivers are required.
    # On Linux, leave the default alone unless the caller already set a driver.
    if sys.platform == "darwin":
        # Drop a stale x11/dummy override that would leave the video system dead.
        driver = os.environ.get("SDL_VIDEODRIVER", "").lower()
        if driver in ("x11", "dummy", "wayland"):
            del os.environ["SDL_VIDEODRIVER"]
        return

    if sys.platform.startswith("win"):
        driver = os.environ.get("SDL_VIDEODRIVER", "").lower()
        if driver in ("x11", "dummy", "cocoa"):
            del os.environ["SDL_VIDEODRIVER"]
        return

    # Linux: only prefer x11 when a display is available and nothing is set yet.
    if "SDL_VIDEODRIVER" not in os.environ and os.environ.get("DISPLAY"):
        os.environ["SDL_VIDEODRIVER"] = "x11"


def create_app(
    width: int,
    height: int,
    title: str = "Desecration Smile",
    headless: bool = False,
) -> GLApp:
    _configure_sdl_video(headless)

    # mixer must be configured before pygame.init()
    try:
        pygame.mixer.pre_init(44100, -16, 2, 1024)
    except pygame.error:
        pass

    pygame.init()

    # Ensure the display subsystem is actually up before GL attribute calls.
    if not pygame.display.get_init():
        try:
            pygame.display.init()
        except pygame.error as exc:
            raise RuntimeError(
                "Pygame video system failed to initialize. "
                "On macOS do not set SDL_VIDEODRIVER=x11. "
                f"Unset it and retry. Underlying error: {exc}"
            ) from exc

    if not pygame.display.get_init():
        raise RuntimeError(
            "Pygame video system is not initialized. "
            "Unset SDL_VIDEODRIVER (especially 'x11' or 'dummy') and run again."
        )

    # GL attributes must be set after display init and before set_mode().
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, 1)
    pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)
    pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
    # Helps on some macOS / Mesa setups requesting a true color buffer.
    pygame.display.gl_set_attribute(pygame.GL_RED_SIZE, 8)
    pygame.display.gl_set_attribute(pygame.GL_GREEN_SIZE, 8)
    pygame.display.gl_set_attribute(pygame.GL_BLUE_SIZE, 8)
    pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)

    flags = pygame.OPENGL | pygame.DOUBLEBUF
    try:
        screen = pygame.display.set_mode((width, height), flags)
    except pygame.error as exc:
        raise RuntimeError(
            "Failed to create an OpenGL 3.3 Core window. "
            "On Apple Silicon Macs install a recent pygame wheel "
            f"(pip install -U pygame) and retry. Underlying error: {exc}"
        ) from exc

    pygame.display.set_caption(title)

    # Share the pygame-created context with ModernGL.
    try:
        ctx = moderngl.create_context(require=330, standalone=False)
    except Exception:
        ctx = moderngl.create_context(require=330)

    ctx.enable(moderngl.DEPTH_TEST)
    ctx.enable(moderngl.BLEND)
    ctx.enable(moderngl.CULL_FACE)
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
