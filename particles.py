from __future__ import annotations
import pygame
from pygame import Vector2
from typing import List, Tuple
from utils import clamp


class Particle:
    def __init__(
        self,
        position: Vector2,
        velocity: Vector2,
        life_seconds: float,
        start_radius: float,
        end_radius: float,
        color: Tuple[int, int, int],
    ) -> None:
        self.position = Vector2(position)
        self.velocity = Vector2(velocity)
        self.life_seconds = life_seconds
        self.remaining = life_seconds
        self.start_radius = start_radius
        self.end_radius = end_radius
        self.color = color

    def update(self, delta_time: float) -> bool:
        self.remaining -= delta_time
        if self.remaining <= 0:
            return False
        self.position += self.velocity * delta_time * 60.0
        return True

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        t = 1.0 - clamp(self.remaining / self.life_seconds, 0.0, 1.0)
        radius = self.start_radius + (self.end_radius - self.start_radius) * t
        alpha = int(255 * (1.0 - t))
        if alpha <= 0 or radius <= 0.5:
            return
        temp = pygame.Surface((int(radius * 2 + 2), int(radius * 2 + 2)), pygame.SRCALPHA)
        pygame.draw.circle(temp, (*self.color, alpha), (int(radius + 1), int(radius + 1)), int(radius))
        screen_pos = (int(self.position.x - radius), int(self.position.y - camera_y - radius))
        surface.blit(temp, screen_pos)


class ParticleSystem:
    def __init__(self, max_particles: int = 200) -> None:
        self.particles: List[Particle] = []
        self.max_particles = max_particles

    def emit_burst(self, position: Vector2, color: Tuple[int, int, int], count: int = 8) -> None:
        import random
        for _ in range(count):
            if len(self.particles) >= self.max_particles:
                break
            angle = random.uniform(0, 6.28318)
            speed = random.uniform(0.5, 2.5)
            vel = Vector2(speed, 0).rotate_rad(angle)
            life = random.uniform(0.3, 0.8)
            start_r = random.uniform(2, 4)
            end_r = random.uniform(0.5, 1.5)
            self.particles.append(Particle(position, vel, life, start_r, end_r, color))

    def update(self, delta_time: float) -> None:
        self.particles = [p for p in self.particles if p.update(delta_time)]

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        for p in self.particles:
            p.draw(surface, camera_y)

