from __future__ import annotations
from utils import lerp
import settings as S


class Camera:
    def __init__(self) -> None:
        self.y: float = 0.0  # World y of screen top
        self.desired_player_screen_y: float = S.SCREEN_HEIGHT * 0.66
        self.smooth_factor: float = 0.08

    def update(self, player_world_y: float) -> None:
        target = player_world_y - self.desired_player_screen_y
        # Camera only moves upward (y decreases). Smoothly approach the lower target value.
        raw = lerp(self.y, target, self.smooth_factor)
        if raw < self.y:
            self.y = raw
        # Never move camera down

    def world_to_screen_y(self, world_y: float) -> float:
        return world_y - self.y

