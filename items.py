from __future__ import annotations
import math
import random
from typing import List, Tuple
import pygame
from pygame import Rect
import settings as S


class Collectible:
    def __init__(self, rect: Rect) -> None:
        self.rect = rect
        self.alive = True
        self.float_phase = random.uniform(0, 6.28318)

    def update(self, delta_time: float) -> None:
        self.float_phase += delta_time * 2.0

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        raise NotImplementedError

    def apply(self, game: "Game") -> None:
        raise NotImplementedError


class Crystal(Collectible):
    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        x, y, w, h = self.rect
        y_offset = int(math.sin(self.float_phase) * 2)
        points = [
            (x + w // 2, y - camera_y + y_offset),
            (x + w, y - camera_y + h // 2 + y_offset),
            (x + w // 2, y - camera_y + h + y_offset),
            (x, y - camera_y + h // 2 + y_offset),
        ]
        pygame.draw.polygon(surface, S.COLOR_CYAN, points)

    def apply(self, game: "Game") -> None:
        game.add_score(S.CRYSTAL_VALUE)
        self.alive = False


class Multiplier(Collectible):
    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        x, y, w, h = self.rect
        y_offset = int(math.sin(self.float_phase) * 2)
        pygame.draw.circle(surface, S.COLOR_MAGENTA, (x + w // 2, y - camera_y + h // 2 + y_offset), w // 2)
        pygame.draw.line(surface, S.COLOR_WHITE, (x + 5, y - camera_y + h // 2 + y_offset), (x + w - 5, y - camera_y + h // 2 + y_offset), 2)
        pygame.draw.line(surface, S.COLOR_WHITE, (x + w // 2, y - camera_y + 5 + y_offset), (x + w // 2, y - camera_y + h - 5 + y_offset), 2)

    def apply(self, game: "Game") -> None:
        game.activate_multiplier()
        self.alive = False


class Shield(Collectible):
    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        x, y, w, h = self.rect
        y_offset = int(math.sin(self.float_phase) * 2)
        pygame.draw.circle(surface, S.COLOR_YELLOW, (x + w // 2, y - camera_y + h // 2 + y_offset), w // 2, 2)

    def apply(self, game: "Game") -> None:
        game.give_shield()
        self.alive = False


def spawn_collectibles_for_platform(rect: Rect) -> List[Collectible]:
    results: List[Collectible] = []
    # Crystal
    if random.random() < S.CRYSTAL_CHANCE:
        c_rect = Rect(rect.centerx - 6, rect.top - 18, 12, 12)
        results.append(Crystal(c_rect))
    # Multiplier
    if random.random() < S.MULTIPLIER_CHANCE:
        m_rect = Rect(rect.left + 6, rect.top - 18, 12, 12)
        results.append(Multiplier(m_rect))
    # Shield
    if random.random() < S.SHIELD_CHANCE:
        s_rect = Rect(rect.right - 18, rect.top - 18, 12, 12)
        results.append(Shield(s_rect))
    return results

