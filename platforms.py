from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple
import pygame
from pygame import Rect
import settings as S
from utils import weighted_choice, chance


@dataclass
class Platform:
    rect: Rect
    color: Tuple[int, int, int]
    solid: bool = True
    alpha: int = 255

    def update(self, delta_time: float) -> None:
        pass

    def top_collision(self, prev_rect: Rect, new_rect: Rect) -> bool:
        # Detect landing: moving downward, intersects, and previous bottom above top
        return (
            prev_rect.bottom <= self.rect.top <= new_rect.bottom
            and prev_rect.centery <= new_rect.centery
            and new_rect.colliderect(self.rect)
        )

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        if self.alpha <= 0:
            return
        r = Rect(self.rect.x, int(self.rect.y - camera_y), self.rect.w, self.rect.h)
        srf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        srf.fill((*self.color, self.alpha))
        surface.blit(srf, (r.x, r.y))


class MovingPlatform(Platform):
    def __init__(self, rect: Rect, color: Tuple[int, int, int], speed_x: float) -> None:
        super().__init__(rect, color)
        self.speed_x = speed_x
        self.direction = 1.0 if speed_x >= 0 else -1.0
        self.blink_t = 0.0

    def update(self, delta_time: float) -> None:
        self.rect.x += int(self.speed_x * self.direction)
        if self.rect.left < 0:
            self.rect.left = 0
            self.direction *= -1
        if self.rect.right > S.SCREEN_WIDTH:
            self.rect.right = S.SCREEN_WIDTH
            self.direction *= -1
        self.blink_t += delta_time

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        super().draw(surface, camera_y)
        # Blink indicator in center
        blink_on = int(self.blink_t * 4) % 2 == 0
        if blink_on:
            cx = self.rect.centerx
            cy = int(self.rect.y - camera_y + self.rect.h // 2)
            pygame.draw.circle(surface, S.COLOR_WHITE, (cx, cy), 2)


class FragilePlatform(Platform):
    def __init__(self, rect: Rect, color: Tuple[int, int, int]) -> None:
        super().__init__(rect, color)
        self.touched = False
        self.timer = 0.0

    def mark_touched(self) -> None:
        if not self.touched:
            self.touched = True
            self.timer = 0.0

    def update(self, delta_time: float) -> None:
        if self.touched:
            self.timer += delta_time
            t = min(1.0, self.timer / S.FRAGILE_PLATFORM_FADE_TIME)
            self.alpha = int(255 * (1.0 - t))
            if self.alpha <= 0:
                self.solid = False


class SpringBooster:
    def __init__(self, platform: Platform) -> None:
        self.platform = platform
        self.scale = 1.0
        self.scale_dir = -1.0
        pad = 6
        size = 10
        self.rect = Rect(platform.rect.centerx - size // 2, platform.rect.top - pad - size, size, size)
        self.active = True

    def update(self, delta_time: float) -> None:
        if not self.active:
            return
        self.scale += self.scale_dir * delta_time * 2.0
        if self.scale < 0.8:
            self.scale = 0.8
            self.scale_dir = 1.0
        elif self.scale > 1.0:
            self.scale = 1.0
            self.scale_dir = -1.0
        # Follow platform horizontally
        self.rect.centerx = self.platform.rect.centerx
        self.rect.bottom = self.platform.rect.top - 2

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        if not self.active:
            return
        r = Rect(self.rect.x, int(self.rect.y - camera_y), self.rect.w, self.rect.h)
        srf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        color = (*S.COLOR_YELLOW, 230)
        pygame.draw.rect(srf, color, srf.get_rect(), border_radius=3)
        surface.blit(pygame.transform.scale(srf, (int(r.w * self.scale), int(r.h * self.scale))), (r.centerx - int(r.w * self.scale) // 2, r.centery - int(r.h * self.scale) // 2))


class PlatformGenerator:
    def __init__(self) -> None:
        self.platforms: List[Platform] = []
        self.springs: List[SpringBooster] = []
        self.highest_y: float = float("inf")  # minimal y among platforms (higher up)

    def reset(self) -> None:
        self.platforms.clear()
        self.springs.clear()
        self.highest_y = float("inf")

    def create_start(self) -> None:
        # Base platform near bottom
        width = 100
        rect = Rect((S.SCREEN_WIDTH - width) // 2, S.SCREEN_HEIGHT - 60, width, S.PLATFORM_HEIGHT)
        base = Platform(rect, S.COLOR_GREEN)
        self.platforms.append(base)
        self.highest_y = min(self.highest_y, base.rect.y)
        # A few initial platforms upwards
        y = base.rect.y - 120
        for _ in range(6):
            self._spawn_one(y)
            y -= random.randint(S.MAX_VERTICAL_GAP // 2, S.MAX_VERTICAL_GAP)

    def ensure_ahead(self, camera_y: float) -> None:
        target_top = camera_y - int(S.SCREEN_HEIGHT * S.GENERATION_BUFFER_SCREENS)
        while self.highest_y > target_top:
            self._spawn_one(self.highest_y - random.randint(S.MAX_VERTICAL_GAP // 2, S.MAX_VERTICAL_GAP))

        # Cleanup far below
        bottom_limit = camera_y + S.SCREEN_HEIGHT * (S.GENERATION_BUFFER_SCREENS + 1)
        self.platforms = [p for p in self.platforms if p.rect.y < bottom_limit and p.alpha > 0]
        self.springs = [s for s in self.springs if s.platform in self.platforms and s.active]

    def _spawn_one(self, y: int) -> None:
        kind = weighted_choice(S.PLATFORM_DISTRIBUTION)
        width = random.randint(S.PLATFORM_MIN_WIDTH, S.PLATFORM_MAX_WIDTH)
        x = random.randint(0, S.SCREEN_WIDTH - width)
        rect = Rect(x, y, width, S.PLATFORM_HEIGHT)
        if kind == "moving":
            speed = random.uniform(*S.MOVING_PLATFORM_SPEED_RANGE)
            plat: Platform = MovingPlatform(rect, S.COLOR_BLUE, speed)
        elif kind == "fragile":
            plat = FragilePlatform(rect, S.COLOR_ORANGE)
        else:
            plat = Platform(rect, S.COLOR_GREEN)
        self.platforms.append(plat)
        self.highest_y = min(self.highest_y, plat.rect.y)
        if chance(S.SPRING_CHANCE):
            spring = SpringBooster(plat)
            self.springs.append(spring)

