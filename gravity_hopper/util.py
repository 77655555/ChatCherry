from __future__ import annotations
from typing import Tuple

import pygame as pg


def draw_text(
    surface: pg.Surface,
    text: str,
    pos: Tuple[int, int],
    font: pg.font.Font,
    color: Tuple[int, int, int] = (255, 255, 255),
    shadow_color: Tuple[int, int, int] | None = (0, 0, 0),
    shadow_offset: Tuple[int, int] = (1, 1),
) -> None:
    if shadow_color is not None:
        shadow = font.render(text, True, shadow_color)
        surface.blit(shadow, (pos[0] + shadow_offset[0], pos[1] + shadow_offset[1]))
    img = font.render(text, True, color)
    surface.blit(img, pos)
