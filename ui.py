from __future__ import annotations
import pygame
import settings as S


class HUD:
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("Arial", 18)
        self.small = pygame.font.SysFont("Arial", 14)

    def draw_top(self, surface: pygame.Surface, score: int, best: int, multiplier_active: bool, multiplier_time_left: float) -> None:
        bar_rect = pygame.Rect(0, 0, S.SCREEN_WIDTH, S.TOP_PANEL_HEIGHT)
        # Use separate alpha surface for translucent bar
        bar = pygame.Surface(bar_rect.size, pygame.SRCALPHA)
        bar.fill((0, 0, 0, 100))
        surface.blit(bar, bar_rect.topleft)
        text = self.font.render(f"Score: {score}", True, S.HUD_TEXT)
        surface.blit(text, (8, 8))

        best_text = self.font.render(f"Best: {best}", True, S.HUD_TEXT)
        surface.blit(best_text, (S.SCREEN_WIDTH - best_text.get_width() - 8, 8))

        if multiplier_active:
            w = 80
            h = 8
            x = 8 + text.get_width() + 12
            y = 10
            pygame.draw.rect(surface, S.HUD_ACCENT, (x, y, w, h), 2, 3)
            fill = int(w * max(0.0, min(1.0, multiplier_time_left / S.MULTIPLIER_DURATION)))
            pygame.draw.rect(surface, S.HUD_ACCENT, (x, y, fill, h), 0, 3)
            mult_text = self.small.render("x2", True, S.HUD_TEXT)
            surface.blit(mult_text, (x + w + 6, y - 2))

    def draw_game_over(self, surface: pygame.Surface, score: int, best: int) -> None:
        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        title_font = pygame.font.SysFont("Arial", 28, bold=True)
        title = title_font.render("Game Over", True, S.HUD_TEXT)
        score_text = self.font.render(f"Score: {score}", True, S.HUD_TEXT)
        best_text = self.font.render(f"Best: {best}", True, S.HUD_TEXT)

        cx = S.SCREEN_WIDTH // 2
        surface.blit(title, (cx - title.get_width() // 2, 220))
        surface.blit(score_text, (cx - score_text.get_width() // 2, 260))
        surface.blit(best_text, (cx - best_text.get_width() // 2, 286))

        tip = self.small.render("Tap to restart", True, S.HUD_TEXT)
        surface.blit(tip, (cx - tip.get_width() // 2, 330))

