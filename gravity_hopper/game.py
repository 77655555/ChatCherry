from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

import pygame as pg

from .assets import draw_parallax_background, make_star_layers
from .config import (
    AIR_HORIZONTAL_DECAY,
    BASE_JUMP_SPEED_PX_PER_FRAME,
    BOOSTER_MULTIPLIER,
    BOOSTER_SPAWN_CHANCE,
    COLOR_BOOSTER,
    COLOR_CRYSTAL,
    COLOR_MULTIPLIER,
    COLOR_PLATFORM_FRAGILE,
    COLOR_PLATFORM_MOVING,
    COLOR_PLATFORM_NORMAL,
    COLOR_PLAYER,
    COLOR_SHIELD,
    COLOR_TOP_BAR,
    COLOR_UI_SHADOW,
    COLOR_UI_TEXT,
    CRYSTAL_SCORE,
    FPS,
    FRAGILE_LIFETIME_AFTER_TOUCH_S,
    GROUND_HORIZONTAL_DECAY,
    GRAVITY_PX_PER_FRAME2,
    JUMP_HOLD_MAX_S,
    JUMP_HOLD_MIN_S,
    MAX_HORIZONTAL_SPEED_PX_PER_FRAME,
    MAX_JUMP_MULTIPLIER,
    MIN_JUMP_MULTIPLIER,
    MULTIPLIER_DURATION_S,
    MULTIPLIER_SPAWN_CHANCE,
    MULTIPLIER_VALUE,
    PIXELS_PER_METER,
    PLATFORM_HEIGHT_PX,
    PLATFORM_MOVE_SPEED_MAX,
    PLATFORM_MOVE_SPEED_MIN,
    PLATFORM_WEIGHT_FRAGILE,
    PLATFORM_WEIGHT_MOVING,
    PLATFORM_WEIGHT_NORMAL,
    PLATFORM_WIDTH_MAX_PX,
    PLATFORM_WIDTH_MIN_PX,
    PLAYER_GLOW_PULSE_S,
    PLAYER_GLOW_RADIUS_PX,
    PLAYER_SIZE_PX,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHIELD_SPAWN_CHANCE,
    STARTING_PLATFORM_COUNT,
    SWIPE_IMPULSE_PX_PER_FRAME,
    SWIPE_THRESHOLD_PX,
    TERMINAL_VELOCITY_PX_PER_FRAME,
    TOP_BAR_HEIGHT_PX,
    VERTICAL_GAP_MAX_PX,
    VERTICAL_GAP_MIN_PX,
)
from .util import draw_text


class PlatformType(Enum):
    NORMAL = auto()
    MOVING = auto()
    FRAGILE = auto()


@dataclass
class Platform:
    x: float
    y: float
    width: int
    height: int
    type: PlatformType
    vx: float = 0.0
    move_dir: int = 1
    touched_time_s: Optional[float] = None
    alpha: int = 255
    has_booster: bool = False

    def rect(self) -> pg.Rect:
        return pg.Rect(int(self.x), int(self.y), int(self.width), int(self.height))

    def update(self, dt: float, world_bounds: Tuple[int, int]) -> None:
        if self.type == PlatformType.MOVING:
            self.x += self.vx * self.move_dir
            if self.x <= 0:
                self.x = 0
                self.move_dir = 1
            elif self.x + self.width >= world_bounds[0]:
                self.x = world_bounds[0] - self.width
                self.move_dir = -1

    def mark_touched(self, now_s: float) -> None:
        if self.type == PlatformType.FRAGILE and self.touched_time_s is None:
            self.touched_time_s = now_s

    def is_dead(self, now_s: float) -> bool:
        if self.type != PlatformType.FRAGILE:
            return False
        if self.touched_time_s is None:
            return False
        return (now_s - self.touched_time_s) >= FRAGILE_LIFETIME_AFTER_TOUCH_S

    def compute_alpha(self, now_s: float) -> int:
        if self.type != PlatformType.FRAGILE or self.touched_time_s is None:
            return 255
        t = (now_s - self.touched_time_s) / FRAGILE_LIFETIME_AFTER_TOUCH_S
        t = max(0.0, min(1.0, t))
        return int(255 * (1.0 - t))


class CollectibleType(Enum):
    CRYSTAL = auto()
    MULTIPLIER = auto()
    SHIELD = auto()


@dataclass
class Collectible:
    x: float
    y: float
    radius: int
    type: CollectibleType
    taken: bool = False
    pulse_t: float = 0.0

    def rect(self) -> pg.Rect:
        return pg.Rect(int(self.x - self.radius), int(self.y - self.radius), self.radius * 2, self.radius * 2)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life_s: float
    color: Tuple[int, int, int]
    radius: float
    age_s: float = 0.0

    def is_dead(self) -> bool:
        return self.age_s >= self.life_s


@dataclass
class Player:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    radius: int = PLAYER_SIZE_PX // 2
    on_platform: bool = False

    def rect(self) -> pg.Rect:
        return pg.Rect(int(self.x - self.radius), int(self.y - self.radius), self.radius * 2, self.radius * 2)


@dataclass
class InputState:
    is_holding: bool = False
    hold_start_ms: int = 0
    last_release_ms: int = 0
    last_hold_duration_s: float = 0.0
    press_pos: Tuple[int, int] = (0, 0)
    swipe_applied: bool = False

    def current_hold_seconds(self, now_ms: int) -> float:
        if not self.is_holding:
            return 0.0
        return max(0.0, (now_ms - self.hold_start_ms) / 1000.0)

    def charge_multiplier(self, now_ms: int) -> float:
        # If holding, compute from current hold; otherwise use last release if it was recent
        hold_s = self.current_hold_seconds(now_ms) if self.is_holding else self.last_hold_duration_s
        if hold_s <= 0.0:
            return MIN_JUMP_MULTIPLIER
        t = max(JUMP_HOLD_MIN_S, min(JUMP_HOLD_MAX_S, hold_s))
        # Map [min,max] -> [MIN_JUMP_MULTIPLIER, MAX_JUMP_MULTIPLIER]
        if JUMP_HOLD_MAX_S == JUMP_HOLD_MIN_S:
            return MAX_JUMP_MULTIPLIER
        k = (t - JUMP_HOLD_MIN_S) / (JUMP_HOLD_MAX_S - JUMP_HOLD_MIN_S)
        return MIN_JUMP_MULTIPLIER + k * (MAX_JUMP_MULTIPLIER - MIN_JUMP_MULTIPLIER)


@dataclass
class Game:
    screen: pg.Surface
    clock: pg.time.Clock
    font_small: pg.font.Font
    font_big: pg.font.Font

    player: Player
    platforms: List[Platform]
    collectibles: List[Collectible] = field(default_factory=list)
    particles: List[Particle] = field(default_factory=list)

    camera_y: float = 0.0
    spawn_cursor_y: float = 0.0  # highest (smallest) y created so far

    input: InputState = field(default_factory=InputState)

    score: int = 0
    best_score: int = 0
    crystals_collected: int = 0
    multiplier: int = 1
    multiplier_ends_ms: int = 0
    shield_charges: int = 0

    last_height_m_whole: int = 0
    game_over: bool = False

    stars_layers: list = field(default_factory=make_star_layers)

    def add_score(self, amount: int) -> None:
        add = amount * (self.multiplier if amount > 0 else 1)
        self.score += add
        if self.score > self.best_score:
            self.best_score = self.score

    def set_multiplier_for_seconds(self, seconds: float, now_ms: int) -> None:
        self.multiplier = MULTIPLIER_VALUE
        self.multiplier_ends_ms = now_ms + int(seconds * 1000)

    def update_multiplier(self, now_ms: int) -> None:
        if self.multiplier > 1 and now_ms >= self.multiplier_ends_ms:
            self.multiplier = 1


# Utility functions

def choose_platform_type(rnd: random.Random) -> PlatformType:
    roll = rnd.randint(1, 100)
    if roll <= PLATFORM_WEIGHT_FRAGILE:
        return PlatformType.FRAGILE
    elif roll <= PLATFORM_WEIGHT_FRAGILE + PLATFORM_WEIGHT_MOVING:
        return PlatformType.MOVING
    else:
        return PlatformType.NORMAL


def create_platform(y: float, rnd: random.Random) -> Platform:
    width = rnd.randint(PLATFORM_WIDTH_MIN_PX, PLATFORM_WIDTH_MAX_PX)
    x = rnd.uniform(0, SCREEN_WIDTH - width)
    ptype = choose_platform_type(rnd)
    platform = Platform(x=x, y=y, width=width, height=PLATFORM_HEIGHT_PX, type=ptype)
    if ptype == PlatformType.MOVING:
        platform.vx = rnd.uniform(PLATFORM_MOVE_SPEED_MIN, PLATFORM_MOVE_SPEED_MAX)
        platform.move_dir = rnd.choice([-1, 1])
    # Booster chance
    if rnd.random() < BOOSTER_SPAWN_CHANCE and ptype != PlatformType.FRAGILE:
        platform.has_booster = True
    return platform


def maybe_spawn_collectibles(above_platform: Platform, rnd: random.Random) -> List[Collectible]:
    items: List[Collectible] = []
    cx = above_platform.x + above_platform.width / 2
    base_y = above_platform.y - 18
    if rnd.random() < 0.35:  # spread multiple small crystals chance cluster
        items.append(Collectible(cx, base_y, 6, CollectibleType.CRYSTAL))
        if rnd.random() < 0.4:
            items.append(Collectible(cx - 14, base_y - 10, 5, CollectibleType.CRYSTAL))
        if rnd.random() < 0.4:
            items.append(Collectible(cx + 14, base_y - 10, 5, CollectibleType.CRYSTAL))
    if rnd.random() < MULTIPLIER_SPAWN_CHANCE:
        items.append(Collectible(cx + rnd.uniform(-40, 40), base_y - 26, 7, CollectibleType.MULTIPLIER))
    if rnd.random() < SHIELD_SPAWN_CHANCE:
        items.append(Collectible(cx + rnd.uniform(-40, 40), base_y - 18, 8, CollectibleType.SHIELD))
    return items


# Drawing helpers

def draw_platform(surface: pg.Surface, platform: Platform, camera_y: float, now_s: float) -> None:
    rect = platform.rect()
    rect.y -= int(camera_y)
    if platform.type == PlatformType.NORMAL:
        color = COLOR_PLATFORM_NORMAL
        pg.draw.rect(surface, color, rect, border_radius=4)
    elif platform.type == PlatformType.MOVING:
        color = COLOR_PLATFORM_MOVING
        pg.draw.rect(surface, color, rect, border_radius=4)
        # Blink indicator: small bar on side
        if (int(now_s * 4) % 2) == 0:
            blink_rect = pg.Rect(rect.x + rect.width // 2 - 6, rect.y - 3, 12, 3)
            pg.draw.rect(surface, color, blink_rect)
    else:  # FRAGILE
        alpha = platform.compute_alpha(now_s)
        color = (*COLOR_PLATFORM_FRAGILE[:3], alpha)
        frag_surface = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
        pg.draw.rect(frag_surface, color, frag_surface.get_rect(), border_radius=4)
        surface.blit(frag_surface, rect.topleft)

    if platform.has_booster:
        spring_rect = pg.Rect(rect.centerx - 12, rect.y - 10, 24, 10)
        # Simple compress-stretch animation
        phase = (math.sin(now_s * 8.0) + 1.0) * 0.5
        h = max(6, int(10 - 4 * phase))
        spring_rect = pg.Rect(rect.centerx - 12, rect.y - h, 24, h)
        pg.draw.rect(surface, COLOR_BOOSTER, spring_rect, border_radius=3)


def draw_collectible(surface: pg.Surface, item: Collectible, camera_y: float, now_s: float) -> None:
    if item.taken:
        return
    pos = (int(item.x), int(item.y - camera_y))
    pulse = (math.sin(now_s * 6.0 + (item.x + item.y) * 0.05) + 1.0) * 0.5
    radius = item.radius + int(1 * pulse)
    if item.type == CollectibleType.CRYSTAL:
        color = COLOR_CRYSTAL
        pg.draw.circle(surface, color, pos, radius)
    elif item.type == CollectibleType.MULTIPLIER:
        color = COLOR_MULTIPLIER
        pg.draw.circle(surface, color, pos, radius)
        # plus sign
        pg.draw.line(surface, (20, 10, 30), (pos[0] - radius // 2, pos[1]), (pos[0] + radius // 2, pos[1]), 2)
        pg.draw.line(surface, (20, 10, 30), (pos[0], pos[1] - radius // 2), (pos[0], pos[1] + radius // 2), 2)
    else:
        color = COLOR_SHIELD
        pg.draw.circle(surface, color, pos, radius, 2)


def draw_player(surface: pg.Surface, player: Player, camera_y: float, now_s: float) -> None:
    center = (int(player.x), int(player.y - camera_y))
    # Glow
    pulse = (math.sin(now_s * (2 * math.pi) / max(PLAYER_GLOW_PULSE_S, 0.1)) + 1.0) * 0.5
    glow_r = int(PLAYER_GLOW_RADIUS_PX * (0.9 + 0.2 * pulse))
    glow_surface = pg.Surface((glow_r * 2, glow_r * 2), pg.SRCALPHA)
    pg.draw.circle(glow_surface, (*COLOR_PLAYER, 40), (glow_r, glow_r), glow_r)
    surface.blit(glow_surface, (center[0] - glow_r, center[1] - glow_r))
    # Core
    pg.draw.circle(surface, COLOR_PLAYER, center, player.radius)


def draw_particles(surface: pg.Surface, particles: List[Particle], camera_y: float) -> None:
    for p in particles:
        if p.is_dead():
            continue
        alpha = int(255 * max(0.0, 1.0 - p.age_s / max(0.001, p.life_s)))
        color = (*p.color, alpha)
        s = pg.Surface((int(p.radius * 2), int(p.radius * 2)), pg.SRCALPHA)
        pg.draw.circle(s, color, (int(p.radius), int(p.radius)), int(p.radius))
        surface.blit(s, (int(p.x - p.radius), int(p.y - p.radius - camera_y)))


# Core systems

def generate_initial_world(rnd: random.Random) -> Tuple[List[Platform], float]:
    platforms: List[Platform] = []
    # Ground-like starting platform near bottom third
    start_y = SCREEN_HEIGHT - 80
    base = Platform(x=SCREEN_WIDTH * 0.5 - 50, y=start_y, width=100, height=PLATFORM_HEIGHT_PX, type=PlatformType.NORMAL)
    platforms.append(base)

    # Stack upwards
    cursor_y = start_y
    for _ in range(STARTING_PLATFORM_COUNT - 1):
        gap = rnd.randint(VERTICAL_GAP_MIN_PX, VERTICAL_GAP_MAX_PX)
        cursor_y -= gap
        p = create_platform(cursor_y, rnd)
        platforms.append(p)
    # spawn cursor beyond topmost
    spawn_cursor_y = cursor_y
    return platforms, spawn_cursor_y


def ensure_spawn_ahead(game: Game, rnd: random.Random) -> None:
    # Keep at least one screen worth of platforms above the top of the camera
    target_y = game.camera_y - SCREEN_HEIGHT
    while game.spawn_cursor_y > target_y:
        gap = rnd.randint(VERTICAL_GAP_MIN_PX, VERTICAL_GAP_MAX_PX)
        game.spawn_cursor_y -= gap
        p = create_platform(game.spawn_cursor_y, rnd)
        game.platforms.append(p)
        # Maybe spawn collectibles over this platform
        game.collectibles.extend(maybe_spawn_collectibles(p, rnd))


def cleanup_below(game: Game, now_s: float) -> None:
    # Remove platforms far below the camera or broken fragile platforms
    keep_platforms: List[Platform] = []
    for p in game.platforms:
        if p.is_dead(now_s):
            continue
        if (p.y - game.camera_y) > (SCREEN_HEIGHT + 80):
            continue
        keep_platforms.append(p)
    game.platforms = keep_platforms

    keep_collectibles: List[Collectible] = []
    for c in game.collectibles:
        if c.taken:
            continue
        if (c.y - game.camera_y) > (SCREEN_HEIGHT + 60):
            continue
        keep_collectibles.append(c)
    game.collectibles = keep_collectibles


def handle_input(game: Game, events: List[pg.event.Event]) -> None:
    now_ms = pg.time.get_ticks()
    for ev in events:
        if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1 and not game.game_over:
            game.input.is_holding = True
            game.input.hold_start_ms = now_ms
            game.input.press_pos = ev.pos
            game.input.swipe_applied = False
        elif ev.type == pg.MOUSEBUTTONUP and ev.button == 1:
            # Record last hold duration for near-future use on landing
            if game.input.is_holding:
                game.input.last_hold_duration_s = max(0.0, (now_ms - game.input.hold_start_ms) / 1000.0)
                game.input.last_release_ms = now_ms
            game.input.is_holding = False
            game.input.swipe_applied = False
            if game.game_over:
                # Restart on tap
                new_game_state(game)
        elif ev.type == pg.MOUSEMOTION and game.input.is_holding and not game.input.swipe_applied and not game.player.on_platform:
            dx = ev.pos[0] - game.input.press_pos[0]
            if abs(dx) >= SWIPE_THRESHOLD_PX:
                impulse = SWIPE_IMPULSE_PX_PER_FRAME if dx > 0 else -SWIPE_IMPULSE_PX_PER_FRAME
                game.player.vx += impulse
                game.player.vx = max(-MAX_HORIZONTAL_SPEED_PX_PER_FRAME, min(MAX_HORIZONTAL_SPEED_PX_PER_FRAME, game.player.vx))
                game.input.swipe_applied = True


def apply_physics_and_collisions(game: Game, dt: float, now_s: float, rnd: random.Random) -> None:
    player = game.player
    player.on_platform = False

    # Gravity
    player.vy += GRAVITY_PX_PER_FRAME2
    if player.vy > TERMINAL_VELOCITY_PX_PER_FRAME:
        player.vy = TERMINAL_VELOCITY_PX_PER_FRAME

    # Horizontal damping
    player.vx *= AIR_HORIZONTAL_DECAY

    # Integrate
    prev_x, prev_y = player.x, player.y
    prev_bottom = prev_y + player.radius
    player.x += player.vx
    player.y += player.vy

    # Wall clamp
    if player.x - player.radius < 0:
        player.x = player.radius
        player.vx = -player.vx * 0.2
    elif player.x + player.radius > SCREEN_WIDTH:
        player.x = SCREEN_WIDTH - player.radius
        player.vx = -player.vx * 0.2

    # Platforms update
    for p in game.platforms:
        p.update(dt, (SCREEN_WIDTH, math.inf))

    # Collision with platform (top surface) only when falling
    if player.vy > 0:
        for p in game.platforms:
            pre_bottom = prev_bottom
            post_bottom = player.y + player.radius
            top = p.y
            if pre_bottom <= top <= post_bottom:
                # Check horizontal overlap
                if (player.x >= p.x - player.radius) and (player.x <= p.x + p.width + player.radius):
                    # Land on platform
                    player.y = p.y - player.radius
                    player.on_platform = True

                    # Determine jump power from input
                    now_ms = pg.time.get_ticks()
                    recent_release = (now_ms - game.input.last_release_ms) <= 350
                    if game.input.is_holding or recent_release:
                        mult = game.input.charge_multiplier(now_ms)
                        # After using release-based charge, clear it to avoid re-use
                        if not game.input.is_holding:
                            game.input.last_hold_duration_s = 0.0
                            game.input.last_release_ms = 0
                    else:
                        mult = MIN_JUMP_MULTIPLIER

                    jump_speed = BASE_JUMP_SPEED_PX_PER_FRAME * mult

                    # Booster effect
                    if p.has_booster:
                        jump_speed *= BOOSTER_MULTIPLIER
                        # Simple booster "squash" particles
                        emit_jump_particles(game, count=10)

                    # Bounce
                    player.vy = -jump_speed

                    # Horizontal friction and platform transfer
                    player.vx = max(-MAX_HORIZONTAL_SPEED_PX_PER_FRAME,
                                     min(MAX_HORIZONTAL_SPEED_PX_PER_FRAME, player.vx * GROUND_HORIZONTAL_DECAY + p.vx * 0.5 * p.move_dir))

                    # Fragile handling
                    p.mark_touched(now_s)

                    # Particles
                    emit_jump_particles(game)

                    break

    # Particles update
    for prt in game.particles:
        prt.age_s += dt
        prt.x += prt.vx
        prt.y += prt.vy
        prt.vy *= 0.98
    game.particles = [p for p in game.particles if not p.is_dead()]

    # Collectibles
    player_rect = player.rect()
    for c in game.collectibles:
        if c.taken:
            continue
        if player_rect.colliderect(c.rect()):
            c.taken = True
            if c.type == CollectibleType.CRYSTAL:
                game.crystals_collected += 1
                game.add_score(CRYSTAL_SCORE)
            elif c.type == CollectibleType.MULTIPLIER:
                game.set_multiplier_for_seconds(MULTIPLIER_DURATION_S, pg.time.get_ticks())
            elif c.type == CollectibleType.SHIELD:
                game.shield_charges += 1

    # Camera follows upward only
    anchor_screen_y = SCREEN_HEIGHT * 0.4
    target_camera = player.y - anchor_screen_y
    if target_camera > game.camera_y:
        game.camera_y = target_camera

    # Height-based scoring (1 point per meter ascended)
    height_m = int(max(0.0, game.camera_y) / max(PIXELS_PER_METER, 1.0))
    if height_m > game.last_height_m_whole:
        gained = height_m - game.last_height_m_whole
        game.add_score(gained)
        game.last_height_m_whole = height_m

    # Death check (fell below screen)
    if (player.y - game.camera_y) - player.radius > SCREEN_HEIGHT:
        if game.shield_charges > 0:
            game.shield_charges -= 1
            # Recover the player slightly above bottom
            player.x = SCREEN_WIDTH / 2
            player.y = game.camera_y + SCREEN_HEIGHT * 0.6
            player.vx = 0
            player.vy = -BASE_JUMP_SPEED_PX_PER_FRAME
        else:
            game.game_over = True


def emit_jump_particles(game: Game, count: int = 8) -> None:
    rnd = random.Random()
    for _ in range(count):
        ang = rnd.uniform(0, math.pi)
        spd = rnd.uniform(1.0, 3.0)
        vx = math.cos(ang) * spd
        vy = -abs(math.sin(ang) * spd)
        p = Particle(
            x=game.player.x + rnd.uniform(-4, 4),
            y=game.player.y + game.player.radius,
            vx=vx,
            vy=vy,
            life_s=rnd.uniform(0.4, 0.8),
            color=(200, 220, 255),
            radius=rnd.uniform(1.5, 3.0),
        )
        game.particles.append(p)


def draw_ui(game: Game) -> None:
    surf = game.screen
    # Top bar
    bar = pg.Surface((SCREEN_WIDTH, TOP_BAR_HEIGHT_PX), pg.SRCALPHA)
    bar.fill((*COLOR_TOP_BAR, 120))
    surf.blit(bar, (0, 0))

    # Texts
    score_text = f"Score: {game.score}"
    best_text = f"Best: {game.best_score}"
    mult_text = f"x{game.multiplier}" if game.multiplier > 1 else ""
    height_text = f"{game.last_height_m_whole} m"

    draw_text(surf, score_text, (8, 6), game.font_small, COLOR_UI_TEXT, COLOR_UI_SHADOW)
    if mult_text:
        draw_text(surf, mult_text, (8, 18), game.font_small, COLOR_UI_TEXT, COLOR_UI_SHADOW)
    draw_text(surf, best_text, (SCREEN_WIDTH - 8 - game.font_small.size(best_text)[0], 6), game.font_small, COLOR_UI_TEXT, COLOR_UI_SHADOW)
    draw_text(surf, height_text, (SCREEN_WIDTH // 2 - game.font_small.size(height_text)[0] // 2, 6), game.font_small, COLOR_UI_TEXT, COLOR_UI_SHADOW)

    if game.game_over:
        msg = "Game Over — Tap to Restart"
        w, h = game.font_big.size(msg)
        draw_text(surf, msg, (SCREEN_WIDTH // 2 - w // 2, SCREEN_HEIGHT // 2 - h // 2), game.font_big, COLOR_UI_TEXT, COLOR_UI_SHADOW)


def new_game_state(game: Game | None = None) -> Game:
    # Initialize pygame state if needed
    if game is None:
        raise ValueError("Game surface must be initialized before resetting state")

    rnd = random.Random()
    platforms, spawn_cursor_y = generate_initial_world(rnd)

    start_x = SCREEN_WIDTH / 2
    start_y = SCREEN_HEIGHT - 120
    player = Player(x=start_x, y=start_y)

    game.player = player
    game.platforms = platforms
    game.collectibles = []
    game.particles = []
    game.camera_y = 0
    game.spawn_cursor_y = spawn_cursor_y
    game.score = 0
    game.crystals_collected = 0
    game.multiplier = 1
    game.multiplier_ends_ms = 0
    game.shield_charges = 0
    game.last_height_m_whole = 0
    game.game_over = False

    ensure_spawn_ahead(game, rnd)
    return game


def run_game() -> None:
    # Safe defaults for headless environments (optional)
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    pg.init()
    try:
        screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    except pg.error:
        # Fallback for environments without a display
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pg.display.quit()
        pg.display.init()
        screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    pg.display.set_caption("Gravity Hopper")
    clock = pg.time.Clock()

    font_small = pg.font.SysFont("DejaVu Sans", 16)
    font_big = pg.font.SysFont("DejaVu Sans", 22, bold=True)

    # Create initial game object
    game = Game(
        screen=screen,
        clock=clock,
        font_small=font_small,
        font_big=font_big,
        player=Player(x=SCREEN_WIDTH / 2, y=SCREEN_HEIGHT - 120),
        platforms=[],
        stars_layers=make_star_layers(),
    )
    new_game_state(game)

    rnd = random.Random()

    running = True
    while running:
        dt_ms = clock.tick(FPS)
        dt = dt_ms / 1000.0
        now_ms = pg.time.get_ticks()
        now_s = now_ms / 1000.0

        events = pg.event.get()
        for ev in events:
            if ev.type == pg.QUIT:
                running = False
        handle_input(game, events)

        if not game.game_over:
            apply_physics_and_collisions(game, dt, now_s, rnd)
            ensure_spawn_ahead(game, rnd)
            cleanup_below(game, now_s)
            game.update_multiplier(now_ms)

        # Draw
        draw_parallax_background(screen, game.stars_layers, game.camera_y)
        # Platforms and collectibles
        for p in game.platforms:
            draw_platform(screen, p, game.camera_y, now_s)
        for c in game.collectibles:
            draw_collectible(screen, c, game.camera_y, now_s)
        # Player and particles
        draw_particles(screen, game.particles, game.camera_y)
        draw_player(screen, game.player, game.camera_y, now_s)
        # UI overlay
        draw_ui(game)

        pg.display.flip()

    pg.quit()
