from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List, Tuple

import pygame as pg

from .config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    COLOR_BG_DARK,
    COLOR_BG_MID,
    COLOR_BG_LIGHT,
)


@dataclass
class StarLayer:
    stars: List[Tuple[float, float, int]]
    parallax: float
    color: Tuple[int, int, int]


def make_star_layers(seed: int | None = None) -> list[StarLayer]:
    rnd = random.Random(seed)
    layers: list[StarLayer] = []
    # back -> front
    layer_specs = [
        (0.25, COLOR_BG_LIGHT, 40),
        (0.5, COLOR_BG_MID, 60),
        (0.85, COLOR_BG_DARK, 90),
    ]
    for parallax, color, count in layer_specs:
        stars: list[tuple[float, float, int]] = []
        for _ in range(count):
            x = rnd.uniform(0, SCREEN_WIDTH)
            y = rnd.uniform(0, SCREEN_HEIGHT * 4)
            r = rnd.randint(1, 2)
            stars.append((x, y, r))
        layers.append(StarLayer(stars=stars, parallax=parallax, color=color))
    return layers


def draw_parallax_background(surface: pg.Surface, layers: list[StarLayer], camera_y: float) -> None:
    surface.fill((8, 10, 14))
    for layer in layers:
        offset_y = camera_y * layer.parallax
        for (x, y, r) in layer.stars:
            y_screen = int((y - offset_y) % (SCREEN_HEIGHT * 4))
            pg.draw.circle(surface, layer.color, (int(x), y_screen), r)
