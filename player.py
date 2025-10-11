from __future__ import annotations
from typing import Tuple
import pygame
from pygame import Rect, Vector2
import settings as S
from utils import clamp


class Player:
    def __init__(self, x: int, y: int) -> None:
        self.position = Vector2(x, y)
        self.velocity = Vector2(0, 0)
        self.size = S.PLAYER_SIZE
        self.rect = Rect(int(self.position.x), int(self.position.y), self.size, self.size)
        self.is_grounded = False
        self.jump_boost_multiplier = 1.0
        self.has_shield = False
        self.glow_time = 0.0
        self.max_height_pixels = 0  # Track ascent relative to spawn
        self.spawn_y = y

    def update_physics(self, delta_time: float) -> None:
        self.velocity.y += S.GRAVITY
        if self.velocity.y > S.TERMINAL_VELOCITY:
            self.velocity.y = S.TERMINAL_VELOCITY
        self.velocity.x *= S.HORIZONTAL_AIR_DAMPING
        self.position += self.velocity
        self.rect.topleft = (int(self.position.x), int(self.position.y))
        self.glow_time += delta_time
        # Track highest ascent (lower y is higher)
        ascent = max(0, self.spawn_y - self.rect.y)
        if ascent > self.max_height_pixels:
            self.max_height_pixels = ascent

    def apply_horizontal_impulse(self, impulse: float) -> None:
        impulse = clamp(impulse, -S.HORIZONTAL_SWIPE_IMPULSE_LIMIT, S.HORIZONTAL_SWIPE_IMPULSE_LIMIT)
        self.velocity.x += impulse

    def jump(self, base_speed: float) -> None:
        jump_speed = base_speed * self.jump_boost_multiplier
        self.velocity.y = -jump_speed
        self.is_grounded = False
        self.jump_boost_multiplier = 1.0

    def resolve_platform_collisions(self, platforms: list) -> Tuple[bool, 'object | None']:
        # Returns (landed, platform)
        landed = False
        landed_platform = None
        if self.velocity.y >= 0:  # Only when falling
            prev_rect = self.rect.move(0, -int(self.velocity.y))
            for p in platforms:
                if not p.solid:
                    continue
                if p.top_collision(prev_rect, self.rect):
                    self.position.y = p.rect.top - self.rect.height
                    self.rect.top = int(self.position.y)
                    # Small bounce if falling fast; otherwise stop and ground
                    if self.velocity.y > 5.0:
                        self.velocity.y = -self.velocity.y * S.RESTITUTION
                    else:
                        self.velocity.y = 0
                        self.is_grounded = True
                    landed = True
                    landed_platform = p
                    break
        return landed, landed_platform

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        # Glow layers
        cx = int(self.rect.centerx)
        cy = int(self.rect.centery - camera_y)
        for i in range(S.PLAYER_GLOW_LAYERS, 0, -1):
            radius = int(self.size // 2 + i * 2)
            alpha = int(28 * i)
            pygame.draw.circle(surface, (80, 180, 255, alpha), (cx, cy), radius)
        pygame.draw.circle(surface, (120, 220, 255), (cx, cy), self.size // 2)

