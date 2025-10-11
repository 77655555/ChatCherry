from __future__ import annotations

# Screen / timing
SCREEN_WIDTH: int = 360
SCREEN_HEIGHT: int = 640
FPS: int = 60

# Physics
GRAVITY_PX_PER_FRAME2: float = 0.55
TERMINAL_VELOCITY_PX_PER_FRAME: float = 12.0
BASE_JUMP_SPEED_PX_PER_FRAME: float = 10.0
MAX_JUMP_MULTIPLIER: float = 1.6
MIN_JUMP_MULTIPLIER: float = 0.9

JUMP_HOLD_MIN_S: float = 0.05
JUMP_HOLD_MAX_S: float = 0.60

AIR_HORIZONTAL_DECAY: float = 0.98
GROUND_HORIZONTAL_DECAY: float = 0.80

SWIPE_THRESHOLD_PX: int = 40
SWIPE_IMPULSE_PX_PER_FRAME: float = 3.5
MAX_HORIZONTAL_SPEED_PX_PER_FRAME: float = 5.0

# Player
PLAYER_SIZE_PX: int = 20
PLAYER_GLOW_RADIUS_PX: int = 26
PLAYER_GLOW_PULSE_S: float = 1.2

# Platforms
PLATFORM_HEIGHT_PX: int = 10
PLATFORM_WIDTH_MIN_PX: int = 60
PLATFORM_WIDTH_MAX_PX: int = 100
PLATFORM_MOVE_SPEED_MIN: float = 1.0
PLATFORM_MOVE_SPEED_MAX: float = 3.0
FRAGILE_LIFETIME_AFTER_TOUCH_S: float = 0.5

# Generation
STARTING_PLATFORM_COUNT: int = 10
VERTICAL_GAP_MIN_PX: int = 70
VERTICAL_GAP_MAX_PX: int = 110

PLATFORM_WEIGHT_NORMAL: int = 60
PLATFORM_WEIGHT_MOVING: int = 25
PLATFORM_WEIGHT_FRAGILE: int = 15

BOOSTER_SPAWN_CHANCE: float = 0.10
CRYSTAL_SPAWN_CHANCE: float = 0.35
MULTIPLIER_SPAWN_CHANCE: float = 0.12
SHIELD_SPAWN_CHANCE: float = 0.07

BOOSTER_MULTIPLIER: float = 1.5
MULTIPLIER_DURATION_S: float = 10.0
MULTIPLIER_VALUE: int = 2

# Scoring/progress
PIXELS_PER_METER: float = 12.0
CRYSTAL_SCORE: int = 10

# UI
TOP_BAR_HEIGHT_PX: int = 36

# Colors (R, G, B)
COLOR_BG_DARK: tuple[int, int, int] = (10, 12, 18)
COLOR_BG_MID: tuple[int, int, int] = (16, 20, 28)
COLOR_BG_LIGHT: tuple[int, int, int] = (22, 26, 36)

COLOR_PLAYER: tuple[int, int, int] = (120, 200, 255)
COLOR_PLATFORM_NORMAL: tuple[int, int, int] = (60, 200, 120)
COLOR_PLATFORM_MOVING: tuple[int, int, int] = (80, 160, 255)
COLOR_PLATFORM_FRAGILE: tuple[int, int, int] = (255, 150, 60)
COLOR_BOOSTER: tuple[int, int, int] = (255, 220, 80)

COLOR_CRYSTAL: tuple[int, int, int] = (120, 255, 240)
COLOR_MULTIPLIER: tuple[int, int, int] = (220, 140, 255)
COLOR_SHIELD: tuple[int, int, int] = (120, 220, 255)

COLOR_UI_TEXT: tuple[int, int, int] = (230, 240, 255)
COLOR_UI_SHADOW: tuple[int, int, int] = (0, 0, 0)
COLOR_TOP_BAR: tuple[int, int, int] = (0, 0, 0)
COLOR_TOP_BAR_ALPHA: int = 120
