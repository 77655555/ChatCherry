from __future__ import annotations
import pygame
import settings as S


class ParallaxBackground:
    def __init__(self) -> None:
        self.layer_speeds = [0.15, 0.35, 0.6]
        self.layer_colors = [S.COLOR_BG_LIGHT, S.COLOR_BG_MID, S.COLOR_BG_DARK]
        self.stripe_height = 80

    def draw(self, surface: pygame.Surface, camera_y: float) -> None:
        surface.fill(S.COLOR_BG_DARK)
        w, h = S.SCREEN_WIDTH, S.SCREEN_HEIGHT

        # Three horizontal neon layers sliding at different speeds
        for idx, speed in enumerate(self.layer_speeds):
            color = self.layer_colors[idx]
            offset = int((camera_y * speed) % self.stripe_height)
            for y in range(-self.stripe_height, h + self.stripe_height, self.stripe_height):
                rect = pygame.Rect(0, y - offset, w, self.stripe_height // 2)
                srf = pygame.Surface(rect.size, pygame.SRCALPHA)
                srf.fill((*color, 60 + idx * 30))
                surface.blit(srf, rect.topleft)

        # Subtle vignette
        vignette = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 90), vignette.get_rect(), border_radius=24)
        surface.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

