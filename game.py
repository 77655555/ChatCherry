from __future__ import annotations
import math
from typing import List

import pygame
from pygame import Vector2

import settings as S
from camera import Camera
from background import ParallaxBackground
from particles import ParticleSystem
from platforms import Platform, MovingPlatform, FragilePlatform, SpringBooster, PlatformGenerator
from items import Collectible, Crystal, Multiplier, Shield, spawn_collectibles_for_platform
from player import Player
from utils import clamp


class Game:
    def __init__(self) -> None:
        pygame.init()
        flags = pygame.SCALED | pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode(S.LOGICAL_SIZE, flags, vsync=1)
        except TypeError:
            self.screen = pygame.display.set_mode(S.LOGICAL_SIZE, flags)
        pygame.display.set_caption("Gravity Hopper")
        self.clock = pygame.time.Clock()

        self.camera = Camera()
        self.background = ParallaxBackground()
        self.particles = ParticleSystem(max_particles=250)
        self.hud = None  # Lazy init after fonts are ready

        self.best_score = 0

        self.reset()

    def reset(self) -> None:
        self.score = 0
        self.multiplier_active = False
        self.multiplier_time_left = 0.0
        self.camera = Camera()

        # World
        self.platforms_gen = PlatformGenerator()
        self.platforms_gen.reset()
        self.platforms_gen.create_start()

        # Player starts on base platform
        base = self.platforms_gen.platforms[0]
        start_x = base.rect.centerx - S.PLAYER_SIZE // 2
        start_y = base.rect.top - S.PLAYER_SIZE
        self.player = Player(start_x, start_y)

        self.collectibles: List[Collectible] = []
        for p in self.platforms_gen.platforms[1:4]:
            self.collectibles.extend(spawn_collectibles_for_platform(p.rect))

        self.state = "running"  # or "game_over"

        # Input state
        self.pointer_down = False
        self.pointer_down_time = 0
        self.pointer_start_pos = Vector2(0, 0)
        self.accumulated_swipe_dx = 0.0

    def add_score(self, base_points: int) -> None:
        points = base_points * (2 if self.multiplier_active else 1)
        self.score += points

    def activate_multiplier(self) -> None:
        self.multiplier_active = True
        self.multiplier_time_left = S.MULTIPLIER_DURATION

    def give_shield(self) -> None:
        self.player.has_shield = True

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise SystemExit
            if self.state == "game_over":
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                    self.reset()
                continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.pointer_down = True
                self.pointer_down_time = pygame.time.get_ticks()
                self.pointer_start_pos = Vector2(event.pos)
                self.accumulated_swipe_dx = 0.0

            elif event.type == pygame.MOUSEMOTION and self.pointer_down:
                dx = event.pos[0] - self.pointer_start_pos.x
                self.accumulated_swipe_dx = dx
                # In air, allow gentle corrections by applying small impulses over time
                if not self.player.is_grounded:
                    impulse = clamp(dx * 0.0025, -0.25, 0.25)
                    self.player.apply_horizontal_impulse(impulse)
                    self.pointer_start_pos = Vector2(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.pointer_down:
                hold_ms = max(0, pygame.time.get_ticks() - self.pointer_down_time)
                self.pointer_down = False
                # Jump only if grounded
                if self.player.is_grounded:
                    t = clamp(hold_ms / 500.0, 0.0, 1.0)
                    speed = S.JUMP_MIN_SPEED + (S.JUMP_MAX_SPEED - S.JUMP_MIN_SPEED) * t
                    # Add small horizontal on release to nudge
                    impulse = clamp(self.accumulated_swipe_dx * 0.01, -S.HORIZONTAL_SWIPE_IMPULSE_LIMIT, S.HORIZONTAL_SWIPE_IMPULSE_LIMIT)
                    self.player.apply_horizontal_impulse(impulse)
                    self.player.jump(speed)
                    self.particles.emit_burst(Vector2(self.player.rect.centerx, self.player.rect.bottom), (120, 220, 255), 10)

    def update(self, delta_time: float) -> None:
        if self.state != "running":
            return

        # Update springs follow
        for s in self.platforms_gen.springs:
            s.update(delta_time)

        # Update platforms (moving/fragile)
        for p in self.platforms_gen.platforms:
            p.update(delta_time)

        # Player physics and collisions
        self.player.update_physics(delta_time)
        landed, platform = self.player.resolve_platform_collisions(self.platforms_gen.platforms)
        if landed and isinstance(platform, FragilePlatform):
            platform.mark_touched()

        # Spring booster check
        if landed:
            for spring in self.platforms_gen.springs:
                if spring.platform is platform and spring.active:
                    if self.player.rect.colliderect(spring.rect.inflate(6, 6)):
                        self.player.jump_boost_multiplier = S.SPRING_JUMP_MULTIPLIER
                        spring.active = False
                        self.particles.emit_burst(Vector2(spring.rect.centerx, spring.rect.centery), S.COLOR_YELLOW, 12)

        # Collectibles
        for c in self.collectibles:
            c.update(delta_time)
        self.collectibles = [c for c in self.collectibles if c.alive]
        for c in list(self.collectibles):
            if self.player.rect.colliderect(c.rect):
                c.apply(self)

        # Camera follows player upward only
        self.camera.update(self.player.rect.y)

        # Platform generation ahead of camera
        prev_count = len(self.platforms_gen.platforms)
        self.platforms_gen.ensure_ahead(self.camera.y)
        if len(self.platforms_gen.platforms) != prev_count:
            # For newly added near top, sprinkle collectibles
            for p in self.platforms_gen.platforms[-3:]:
                # Do not flood
                if len(self.collectibles) < 50:
                    self.collectibles.extend(spawn_collectibles_for_platform(p.rect))

        # Scoring from height gain
        current_meters = int(self.player.max_height_pixels / S.PIXELS_PER_METER)
        # Add differential meters as points each frame (x2 if multiplier active)
        if not hasattr(self, "_last_meters"):
            self._last_meters = current_meters
        delta_m = current_meters - self._last_meters
        if delta_m > 0:
            self.add_score(delta_m)
            self._last_meters = current_meters

        # Multiplier timer
        if self.multiplier_active:
            self.multiplier_time_left -= delta_time
            if self.multiplier_time_left <= 0:
                self.multiplier_active = False
                self.multiplier_time_left = 0.0

        # Particles
        self.particles.update(delta_time)

        # Death check (fell below bottom)
        bottom = self.camera.y + S.SCREEN_HEIGHT
        if self.player.rect.top > bottom:
            if self.player.has_shield:
                self.player.has_shield = False
                self.player.position.y = bottom - 120
                self.player.rect.top = int(self.player.position.y)
                self.player.velocity.y = -S.JUMP_MIN_SPEED * 1.2
            else:
                self.best_score = max(self.best_score, self.score)
                self.state = "game_over"

    def draw(self) -> None:
        self.background.draw(self.screen, self.camera.y)

        # Platforms and springs
        for p in self.platforms_gen.platforms:
            p.draw(self.screen, self.camera.y)
        for s in self.platforms_gen.springs:
            s.draw(self.screen, self.camera.y)

        # Collectibles
        for c in self.collectibles:
            c.draw(self.screen, self.camera.y)

        # Player and particles on top
        self.player.draw(self.screen, self.camera.y)
        self.particles.draw(self.screen, self.camera.y)

        # HUD
        if self.hud is None:
            from ui import HUD
            self.hud = HUD()
        self.hud.draw_top(self.screen, self.score, self.best_score, self.multiplier_active, self.multiplier_time_left)

        if self.state == "game_over":
            self.hud.draw_game_over(self.screen, self.score, self.best_score)

        pygame.display.flip()

    def run(self) -> None:
        while True:
            self.handle_events()
            delta_time = min(0.05, self.clock.tick(S.FPS) / 1000.0)
            self.update(delta_time)
            self.draw()

