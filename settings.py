from __future__ import annotations

# Display settings
SCREEN_WIDTH: int = 360
SCREEN_HEIGHT: int = 640
LOGICAL_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
FPS: int = 60

# Physics
GRAVITY: float = 0.35
JUMP_MIN_SPEED: float = 7.0
JUMP_MAX_SPEED: float = 14.0
TERMINAL_VELOCITY: float = 12.0
RESTITUTION: float = 0.7
HORIZONTAL_AIR_DAMPING: float = 0.95
HORIZONTAL_SWIPE_IMPULSE_LIMIT: float = 3.0

# Player
PLAYER_SIZE: int = 20
PLAYER_GLOW_LAYERS: int = 3

# Platforms
PLATFORM_HEIGHT: int = 10
PLATFORM_MIN_WIDTH: int = 60
PLATFORM_MAX_WIDTH: int = 100
MOVING_PLATFORM_SPEED_RANGE = (1.0, 3.0)
FRAGILE_PLATFORM_FADE_TIME: float = 0.5

# Generators / probabilities
PLATFORM_DISTRIBUTION = {
    "normal": 0.60,
    "moving": 0.25,
    "fragile": 0.15,
}
SPRING_CHANCE: float = 0.08
# Spring effect
SPRING_JUMP_MULTIPLIER: float = 1.5

# Collectibles
CRYSTAL_VALUE: int = 10
CRYSTAL_CHANCE: float = 0.20
MULTIPLIER_CHANCE: float = 0.06
SHIELD_CHANCE: float = 0.04
MULTIPLIER_DURATION: float = 10.0

# Scoring / world scale
PIXELS_PER_METER: float = 50.0
GENERATION_BUFFER_SCREENS: float = 3.0

# Colors (RGB)
COLOR_BG_DARK = (8, 10, 20)
COLOR_BG_MID = (14, 18, 36)
COLOR_BG_LIGHT = (28, 36, 72)

COLOR_WHITE = (240, 240, 255)
COLOR_GRAY = (150, 160, 180)
COLOR_GREEN = (76, 187, 23)
COLOR_BLUE = (45, 136, 255)
COLOR_ORANGE = (255, 149, 64)
COLOR_YELLOW = (255, 219, 77)
COLOR_CYAN = (102, 255, 255)
COLOR_MAGENTA = (255, 102, 204)

HUD_BG = (0, 0, 0)
HUD_TEXT = COLOR_WHITE
HUD_ACCENT = COLOR_CYAN

# UI
TOP_PANEL_HEIGHT: int = 36

# Derived constants
# Rough safe maximum gap between platforms so the next is reachable by max jump.
# h = v^2 / (2g) with a safety factor.
MAX_VERTICAL_GAP: int = int((JUMP_MAX_SPEED * JUMP_MAX_SPEED) / (2 * GRAVITY) * 0.8)

