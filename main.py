#!/usr/bin/env python3
"""
Gravity Hopper - Mobile 2D Game
Увлекательная мобильная 2D игра с простым управлением, оптимизированная для сенсорного экрана.
"""

import pygame
import random
import math
import json
import os
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

# Инициализация Pygame
pygame.init()

# Константы игры
SCREEN_WIDTH = 360
SCREEN_HEIGHT = 640
FPS = 60

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 100, 255)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
GRAY = (128, 128, 128)
DARK_BLUE = (0, 0, 139)

# Физические константы
GRAVITY = 0.8
MAX_FALL_SPEED = 15
JUMP_STRENGTH = -12
LONG_JUMP_STRENGTH = -18
AIR_RESISTANCE = 0.98
PLATFORM_BOUNCE = 0.3

# Игровые константы
PLAYER_SIZE = 20
PLATFORM_HEIGHT = 10
MIN_PLATFORM_WIDTH = 60
MAX_PLATFORM_WIDTH = 100
PLATFORM_SPACING_Y = 80
CRYSTAL_SIZE = 12
BONUS_SIZE = 16

class GameState(Enum):
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"

class PlatformType(Enum):
    NORMAL = "normal"
    MOVING = "moving"
    FRAGILE = "fragile"
    SPRING = "spring"

@dataclass
class Vector2:
    x: float
    y: float
    
    def __add__(self, other):
        return Vector2(self.x + other.x, self.y + other.y)
    
    def __mul__(self, scalar):
        return Vector2(self.x * scalar, self.y * scalar)

class Particle:
    """Класс для эффектов частиц"""
    def __init__(self, x: float, y: float, vel_x: float, vel_y: float, color: Tuple[int, int, int], life: int):
        self.x = x
        self.y = y
        self.vel_x = vel_x
        self.vel_y = vel_y
        self.color = color
        self.life = life
        self.max_life = life
        self.size = random.randint(2, 4)
    
    def update(self):
        self.x += self.vel_x
        self.y += self.vel_y
        self.vel_y += 0.2  # Гравитация для частиц
        self.life -= 1
        
        # Уменьшаем размер со временем
        self.size = max(1, int(self.size * (self.life / self.max_life)))
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        if self.life > 0:
            alpha = int(255 * (self.life / self.max_life))
            color = (*self.color, alpha)
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y - camera_y)), self.size)

class Player:
    """Класс игрока - антигравитационный робот-шарик"""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.size = PLAYER_SIZE
        self.on_ground = False
        self.jump_charge = 0.0
        self.max_jump_charge = 30
        self.glow_intensity = 0
        self.glow_direction = 1
        self.shield_active = False
        self.shield_time = 0
        
    def update(self, platforms: List['Platform']):
        # Применяем гравитацию
        if not self.on_ground:
            self.vel_y += GRAVITY
            if self.vel_y > MAX_FALL_SPEED:
                self.vel_y = MAX_FALL_SPEED
        
        # Применяем сопротивление воздуха к горизонтальному движению
        self.vel_x *= AIR_RESISTANCE
        
        # Обновляем позицию
        self.x += self.vel_x
        self.y += self.vel_y
        
        # Ограничиваем движение по горизонтали
        if self.x < self.size:
            self.x = self.size
            self.vel_x = 0
        elif self.x > SCREEN_WIDTH - self.size:
            self.x = SCREEN_WIDTH - self.size
            self.vel_x = 0
        
        # Проверяем коллизии с платформами
        self.check_platform_collisions(platforms)
        
        # Обновляем эффект свечения
        self.glow_intensity += self.glow_direction * 3
        if self.glow_intensity >= 50:
            self.glow_intensity = 50
            self.glow_direction = -1
        elif self.glow_intensity <= 0:
            self.glow_intensity = 0
            self.glow_direction = 1
        
        # Обновляем щит
        if self.shield_active:
            self.shield_time -= 1
            if self.shield_time <= 0:
                self.shield_active = False
    
    def check_platform_collisions(self, platforms: List['Platform']):
        self.on_ground = False
        
        for platform in platforms:
            if not platform.active:
                continue
                
            # Проверяем коллизию сверху (приземление на платформу)
            if (self.vel_y > 0 and 
                self.y + self.size > platform.y and 
                self.y + self.size < platform.y + PLATFORM_HEIGHT + 10 and
                self.x + self.size > platform.x and 
                self.x - self.size < platform.x + platform.width):
                
                self.y = platform.y - self.size
                self.vel_y = 0
                self.on_ground = True
                
                # Обрабатываем разные типы платформ
                if platform.platform_type == PlatformType.SPRING:
                    self.vel_y = LONG_JUMP_STRENGTH * 1.5
                    self.on_ground = False
                    return [Particle(self.x + random.randint(-10, 10), self.y + self.size, 
                                   random.uniform(-3, 3), random.uniform(-5, -2), 
                                   YELLOW, random.randint(20, 40)) for _ in range(8)]
                
                elif platform.platform_type == PlatformType.FRAGILE:
                    platform.trigger_destruction()
                
                # Если платформа движется, передаем импульс игроку
                if platform.platform_type == PlatformType.MOVING:
                    self.vel_x += platform.vel_x * 0.3
                
                break
        
        return []
    
    def jump(self, charge_time: float = 0.0):
        """Прыжок с учетом времени зарядки"""
        if self.on_ground:
            # Базовая сила прыжка + бонус от зарядки
            jump_power = JUMP_STRENGTH + (charge_time / self.max_jump_charge) * (LONG_JUMP_STRENGTH - JUMP_STRENGTH)
            self.vel_y = jump_power
            self.on_ground = False
            
            # Создаем частицы при прыжке
            return [Particle(self.x + random.randint(-self.size, self.size), self.y + self.size, 
                           random.uniform(-2, 2), random.uniform(-3, -1), 
                           CYAN, random.randint(15, 30)) for _ in range(5)]
        return []
    
    def move_horizontal(self, direction: float):
        """Горизонтальное движение в воздухе"""
        if not self.on_ground:
            self.vel_x += direction * 0.5
            # Ограничиваем максимальную горизонтальную скорость
            max_vel = 8
            if self.vel_x > max_vel:
                self.vel_x = max_vel
            elif self.vel_x < -max_vel:
                self.vel_x = -max_vel
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        screen_y = self.y - camera_y
        
        # Рисуем свечение
        glow_radius = self.size + self.glow_intensity // 3
        glow_color = (0, 150 + self.glow_intensity, 255 - self.glow_intensity // 2)
        pygame.draw.circle(screen, glow_color, (int(self.x), int(screen_y)), glow_radius, 3)
        
        # Рисуем основной шарик
        pygame.draw.circle(screen, CYAN, (int(self.x), int(screen_y)), self.size)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(screen_y)), self.size, 2)
        
        # Рисуем "глаза" робота
        eye_offset = self.size // 3
        pygame.draw.circle(screen, WHITE, (int(self.x - eye_offset), int(screen_y - eye_offset)), 4)
        pygame.draw.circle(screen, WHITE, (int(self.x + eye_offset), int(screen_y - eye_offset)), 4)
        pygame.draw.circle(screen, BLACK, (int(self.x - eye_offset), int(screen_y - eye_offset)), 2)
        pygame.draw.circle(screen, BLACK, (int(self.x + eye_offset), int(screen_y - eye_offset)), 2)
        
        # Рисуем щит
        if self.shield_active:
            shield_alpha = min(255, self.shield_time * 3)
            shield_color = (255, 215, 0, shield_alpha)
            pygame.draw.circle(screen, (255, 215, 0), (int(self.x), int(screen_y)), self.size + 8, 3)

class Platform:
    """Класс платформы"""
    def __init__(self, x: float, y: float, width: float, platform_type: PlatformType):
        self.x = x
        self.y = y
        self.width = width
        self.platform_type = platform_type
        self.active = True
        self.destruction_timer = 0
        self.max_destruction_time = 30  # 0.5 секунды при 60 FPS
        self.vel_x = 0
        self.spring_animation = 0
        
        # Настройки для движущихся платформ
        if platform_type == PlatformType.MOVING:
            self.vel_x = random.choice([-2, -1, 1, 2])
            self.move_range = random.randint(80, 120)
            self.start_x = x
    
    def update(self):
        # Обновляем движущиеся платформы
        if self.platform_type == PlatformType.MOVING and self.active:
            self.x += self.vel_x
            
            # Отскакиваем от границ движения
            if abs(self.x - self.start_x) > self.move_range:
                self.vel_x *= -1
            
            # Отскакиваем от границ экрана
            if self.x <= 0 or self.x + self.width >= SCREEN_WIDTH:
                self.vel_x *= -1
                self.x = max(0, min(SCREEN_WIDTH - self.width, self.x))
        
        # Обновляем хрупкие платформы
        if self.platform_type == PlatformType.FRAGILE and self.destruction_timer > 0:
            self.destruction_timer += 1
            if self.destruction_timer >= self.max_destruction_time:
                self.active = False
        
        # Анимация пружин
        if self.platform_type == PlatformType.SPRING:
            self.spring_animation = max(0, self.spring_animation - 1)
    
    def trigger_destruction(self):
        """Запускает разрушение хрупкой платформы"""
        if self.platform_type == PlatformType.FRAGILE:
            self.destruction_timer = 1
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        if not self.active:
            return
        
        screen_y = self.y - camera_y
        
        # Определяем цвет платформы
        if self.platform_type == PlatformType.NORMAL:
            color = GREEN
        elif self.platform_type == PlatformType.MOVING:
            # Мигающий индикатор движения
            flash = int(pygame.time.get_ticks() / 200) % 2
            color = BLUE if flash else (0, 50, 200)
        elif self.platform_type == PlatformType.FRAGILE:
            # Постепенное исчезновение
            if self.destruction_timer > 0:
                alpha = 1.0 - (self.destruction_timer / self.max_destruction_time)
                color = (int(ORANGE[0] * alpha), int(ORANGE[1] * alpha), int(ORANGE[2] * alpha))
            else:
                color = ORANGE
        elif self.platform_type == PlatformType.SPRING:
            color = YELLOW
        
        # Рисуем платформу
        rect = pygame.Rect(self.x, screen_y, self.width, PLATFORM_HEIGHT)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, WHITE, rect, 2)
        
        # Дополнительные эффекты для пружин
        if self.platform_type == PlatformType.SPRING:
            # Рисуем спираль пружины
            center_x = self.x + self.width // 2
            center_y = screen_y + PLATFORM_HEIGHT // 2
            spring_height = 6 - self.spring_animation
            
            for i in range(3):
                offset_y = (i - 1) * spring_height
                pygame.draw.circle(screen, BLACK, (int(center_x), int(center_y + offset_y)), 2)

class Collectible:
    """Базовый класс для собираемых предметов"""
    def __init__(self, x: float, y: float, collectible_type: str):
        self.x = x
        self.y = y
        self.type = collectible_type
        self.active = True
        self.animation_offset = random.uniform(0, 2 * math.pi)
        self.bob_speed = 0.1
        self.collected = False
    
    def update(self):
        # Анимация покачивания
        self.animation_offset += self.bob_speed
    
    def check_collision(self, player: Player) -> bool:
        if not self.active:
            return False
        
        distance = math.sqrt((self.x - player.x)**2 + (self.y - player.y)**2)
        collision_distance = CRYSTAL_SIZE + player.size
        
        if distance < collision_distance:
            self.active = False
            self.collected = True
            return True
        return False
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        if not self.active:
            return
        
        screen_y = self.y - camera_y + math.sin(self.animation_offset) * 3
        
        if self.type == "crystal":
            # Рисуем кристалл
            points = []
            for i in range(6):
                angle = i * math.pi / 3 + self.animation_offset * 0.5
                x = self.x + math.cos(angle) * CRYSTAL_SIZE
                y = screen_y + math.sin(angle) * CRYSTAL_SIZE
                points.append((x, y))
            
            pygame.draw.polygon(screen, PURPLE, points)
            pygame.draw.polygon(screen, WHITE, points, 2)
        
        elif self.type == "bonus":
            # Рисуем бонус множителя
            pygame.draw.circle(screen, YELLOW, (int(self.x), int(screen_y)), BONUS_SIZE)
            pygame.draw.circle(screen, RED, (int(self.x), int(screen_y)), BONUS_SIZE, 3)
            
            # Рисуем "x2"
            font = pygame.font.Font(None, 20)
            text = font.render("x2", True, BLACK)
            text_rect = text.get_rect(center=(self.x, screen_y))
            screen.blit(text, text_rect)
        
        elif self.type == "shield":
            # Рисуем щит
            pygame.draw.circle(screen, (255, 215, 0), (int(self.x), int(screen_y)), BONUS_SIZE)
            pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(screen_y)), BONUS_SIZE, 3)
            
            # Рисуем символ щита
            shield_points = [
                (self.x, screen_y - BONUS_SIZE + 4),
                (self.x - BONUS_SIZE + 6, screen_y - 2),
                (self.x - BONUS_SIZE + 6, screen_y + 6),
                (self.x, screen_y + BONUS_SIZE - 4),
                (self.x + BONUS_SIZE - 6, screen_y + 6),
                (self.x + BONUS_SIZE - 6, screen_y - 2)
            ]
            pygame.draw.polygon(screen, (0, 100, 200), shield_points)

class Camera:
    """Система камеры с плавным следованием за игроком"""
    def __init__(self):
        self.y = 0
        self.target_y = 0
        self.smooth_factor = 0.1
        self.max_height = 0
    
    def update(self, player: Player):
        # Камера следует за игроком, но только вверх
        target = player.y - SCREEN_HEIGHT * 0.7
        
        if target < self.target_y:
            self.target_y = target
            self.max_height = max(self.max_height, -target)
        
        # Плавное движение камеры
        self.y += (self.target_y - self.y) * self.smooth_factor

class ParallaxBackground:
    """Параллакс-фон с тремя слоями"""
    def __init__(self):
        self.layers = [
            {'speed': 0.2, 'color': (20, 20, 60), 'stars': self.generate_stars(50)},
            {'speed': 0.5, 'color': (40, 40, 80), 'stars': self.generate_stars(30)},
            {'speed': 0.8, 'color': (60, 60, 100), 'stars': self.generate_stars(20)}
        ]
    
    def generate_stars(self, count: int) -> List[Tuple[int, int, int]]:
        """Генерирует звезды для слоя"""
        stars = []
        for _ in range(count):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(-2000, SCREEN_HEIGHT)
            size = random.randint(1, 3)
            stars.append((x, y, size))
        return stars
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        # Заливаем фон градиентом
        for y in range(SCREEN_HEIGHT):
            color_intensity = int(20 + (y / SCREEN_HEIGHT) * 40)
            color = (color_intensity, color_intensity, color_intensity + 20)
            pygame.draw.line(screen, color, (0, y), (SCREEN_WIDTH, y))
        
        # Рисуем слои звезд
        for layer in self.layers:
            for star_x, star_y, star_size in layer['stars']:
                screen_y = star_y - camera_y * layer['speed']
                
                # Зацикливаем звезды
                if screen_y > SCREEN_HEIGHT + 100:
                    screen_y -= SCREEN_HEIGHT + 2000
                elif screen_y < -100:
                    screen_y += SCREEN_HEIGHT + 2000
                
                if 0 <= screen_y <= SCREEN_HEIGHT:
                    pygame.draw.circle(screen, WHITE, (star_x, int(screen_y)), star_size)

class GameUI:
    """Пользовательский интерфейс игры"""
    def __init__(self):
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        
        self.score = 0
        self.best_score = self.load_best_score()
        self.height_meters = 0
        self.crystals_collected = 0
        self.multiplier = 1.0
        self.multiplier_time = 0
        
    def load_best_score(self) -> int:
        """Загружает лучший результат из файла"""
        try:
            if os.path.exists("best_score.json"):
                with open("best_score.json", "r") as f:
                    data = json.load(f)
                    return data.get("best_score", 0)
        except:
            pass
        return 0
    
    def save_best_score(self):
        """Сохраняет лучший результат в файл"""
        try:
            with open("best_score.json", "w") as f:
                json.dump({"best_score": self.best_score}, f)
        except:
            pass
    
    def add_score(self, points: int):
        """Добавляет очки с учетом множителя"""
        self.score += int(points * self.multiplier)
        if self.score > self.best_score:
            self.best_score = self.score
    
    def activate_multiplier(self):
        """Активирует множитель очков"""
        self.multiplier = 2.0
        self.multiplier_time = 600  # 10 секунд при 60 FPS
    
    def update(self, player_y: float):
        # Обновляем высоту в метрах
        self.height_meters = max(0, int(-player_y / 50))
        
        # Обновляем множитель
        if self.multiplier_time > 0:
            self.multiplier_time -= 1
            if self.multiplier_time <= 0:
                self.multiplier = 1.0
    
    def draw(self, screen: pygame.Surface):
        # Верхняя панель с полупрозрачным фоном
        panel_rect = pygame.Rect(0, 0, SCREEN_WIDTH, 80)
        panel_surface = pygame.Surface((SCREEN_WIDTH, 80))
        panel_surface.set_alpha(180)
        panel_surface.fill(BLACK)
        screen.blit(panel_surface, (0, 0))
        
        # Текущие очки
        score_text = self.font_medium.render(f"Очки: {self.score}", True, WHITE)
        screen.blit(score_text, (10, 10))
        
        # Лучший результат
        best_text = self.font_small.render(f"Лучший: {self.best_score}", True, GRAY)
        screen.blit(best_text, (SCREEN_WIDTH - 120, 10))
        
        # Высота
        height_text = self.font_small.render(f"Высота: {self.height_meters}м", True, WHITE)
        screen.blit(height_text, (10, 35))
        
        # Кристаллы
        crystals_text = self.font_small.render(f"Кристаллы: {self.crystals_collected}", True, PURPLE)
        screen.blit(crystals_text, (10, 55))
        
        # Множитель
        if self.multiplier > 1.0:
            mult_text = self.font_medium.render(f"x{self.multiplier:.1f}", True, YELLOW)
            mult_rect = mult_text.get_rect(center=(SCREEN_WIDTH - 60, 45))
            
            # Мигающий эффект
            if self.multiplier_time < 120 and (self.multiplier_time // 10) % 2:
                pass  # Не рисуем для мигания
            else:
                screen.blit(mult_text, mult_rect)

class TouchControls:
    """Система управления, адаптированная под мобильные устройства"""
    def __init__(self):
        self.touch_start_time = 0
        self.is_touching = False
        self.touch_start_pos = (0, 0)
        self.swipe_threshold = 30
        self.long_press_threshold = 300  # миллисекунды
    
    def handle_touch_start(self, pos: Tuple[int, int]):
        """Обрабатывает начало касания"""
        self.is_touching = True
        self.touch_start_time = pygame.time.get_ticks()
        self.touch_start_pos = pos
    
    def handle_touch_end(self, pos: Tuple[int, int], player: Player) -> List[Particle]:
        """Обрабатывает окончание касания"""
        if not self.is_touching:
            return []
        
        particles = []
        touch_duration = pygame.time.get_ticks() - self.touch_start_time
        
        # Проверяем на свайп
        dx = pos[0] - self.touch_start_pos[0]
        dy = pos[1] - self.touch_start_pos[1]
        
        if abs(dx) > self.swipe_threshold and abs(dx) > abs(dy):
            # Горизонтальный свайп - движение в воздухе
            direction = 1 if dx > 0 else -1
            player.move_horizontal(direction * 3)
        else:
            # Тап или долгое нажатие - прыжок
            charge_time = min(touch_duration, player.max_jump_charge * 10)  # Конвертируем в условные единицы
            particles = player.jump(charge_time)
        
        self.is_touching = False
        return particles
    
    def get_jump_charge_visual(self) -> float:
        """Возвращает визуальный индикатор зарядки прыжка"""
        if not self.is_touching:
            return 0.0
        
        charge_time = pygame.time.get_ticks() - self.touch_start_time
        return min(1.0, charge_time / (30 * 10))  # Нормализуем к 0-1

class PlatformGenerator:
    """Генератор платформ"""
    def __init__(self):
        self.last_platform_y = SCREEN_HEIGHT - 100
        self.platform_count = 0
    
    def generate_platforms(self, target_y: float, existing_platforms: List[Platform]) -> List[Platform]:
        """Генерирует платформы до указанной высоты"""
        new_platforms = []
        
        while self.last_platform_y > target_y:
            self.last_platform_y -= PLATFORM_SPACING_Y + random.randint(-20, 20)
            
            # Определяем тип платформы
            rand = random.random()
            if rand < 0.6:  # 60% обычные
                platform_type = PlatformType.NORMAL
            elif rand < 0.85:  # 25% движущиеся
                platform_type = PlatformType.MOVING
            elif rand < 0.98:  # 13% хрупкие
                platform_type = PlatformType.FRAGILE
            else:  # 2% пружины
                platform_type = PlatformType.SPRING
            
            # Размеры и позиция платформы
            width = random.randint(MIN_PLATFORM_WIDTH, MAX_PLATFORM_WIDTH)
            x = random.randint(0, SCREEN_WIDTH - width)
            
            platform = Platform(x, self.last_platform_y, width, platform_type)
            new_platforms.append(platform)
            self.platform_count += 1
        
        return new_platforms

class CollectibleGenerator:
    """Генератор собираемых предметов"""
    def __init__(self):
        pass
    
    def generate_for_platform(self, platform: Platform) -> List[Collectible]:
        """Генерирует предметы для платформы"""
        collectibles = []
        
        # Кристаллы появляются часто
        if random.random() < 0.4:
            x = platform.x + platform.width // 2
            y = platform.y - 30
            collectibles.append(Collectible(x, y, "crystal"))
        
        # Бонусы появляются редко
        if random.random() < 0.05:
            x = platform.x + platform.width // 2
            y = platform.y - 30
            collectibles.append(Collectible(x, y, "bonus"))
        
        # Щиты появляются очень редко
        if random.random() < 0.02:
            x = platform.x + platform.width // 2
            y = platform.y - 30
            collectibles.append(Collectible(x, y, "shield"))
        
        return collectibles

class GravityHopper:
    """Основной класс игры"""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Gravity Hopper")
        self.clock = pygame.time.Clock()
        
        # Игровые объекты
        self.player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 150)
        self.camera = Camera()
        self.background = ParallaxBackground()
        self.ui = GameUI()
        self.controls = TouchControls()
        self.platform_generator = PlatformGenerator()
        self.collectible_generator = CollectibleGenerator()
        
        # Списки объектов
        self.platforms: List[Platform] = []
        self.collectibles: List[Collectible] = []
        self.particles: List[Particle] = []
        
        # Состояние игры
        self.game_state = GameState.MENU
        self.running = True
        
        # Генерируем начальные платформы
        self.generate_initial_platforms()
    
    def generate_initial_platforms(self):
        """Генерирует начальные платформы"""
        # Стартовая платформа
        start_platform = Platform(SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT - 50, 100, PlatformType.NORMAL)
        self.platforms.append(start_platform)
        
        # Генерируем платформы вверх
        new_platforms = self.platform_generator.generate_platforms(-1000, self.platforms)
        self.platforms.extend(new_platforms)
        
        # Генерируем предметы для платформ
        for platform in new_platforms:
            collectibles = self.collectible_generator.generate_for_platform(platform)
            self.collectibles.extend(collectibles)
    
    def handle_events(self):
        """Обрабатывает события"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                if self.game_state == GameState.MENU:
                    if event.key == pygame.K_SPACE:
                        self.start_game()
                elif self.game_state == GameState.PLAYING:
                    if event.key == pygame.K_SPACE:
                        particles = self.player.jump()
                        self.particles.extend(particles)
                    elif event.key == pygame.K_p:
                        self.game_state = GameState.PAUSED
                    elif event.key == pygame.K_LEFT:
                        self.player.move_horizontal(-1)
                    elif event.key == pygame.K_RIGHT:
                        self.player.move_horizontal(1)
                elif self.game_state == GameState.PAUSED:
                    if event.key == pygame.K_p:
                        self.game_state = GameState.PLAYING
                elif self.game_state == GameState.GAME_OVER:
                    if event.key == pygame.K_SPACE:
                        self.restart_game()
            
            # Обработка касаний (симуляция мышью)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.game_state == GameState.MENU:
                    self.start_game()
                elif self.game_state == GameState.PLAYING:
                    self.controls.handle_touch_start(event.pos)
                elif self.game_state == GameState.GAME_OVER:
                    self.restart_game()
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if self.game_state == GameState.PLAYING:
                    particles = self.controls.handle_touch_end(event.pos, self.player)
                    self.particles.extend(particles)
    
    def start_game(self):
        """Начинает новую игру"""
        self.game_state = GameState.PLAYING
        self.player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 150)
        self.camera = Camera()
        self.ui = GameUI()
        self.platforms.clear()
        self.collectibles.clear()
        self.particles.clear()
        self.generate_initial_platforms()
    
    def restart_game(self):
        """Перезапускает игру"""
        self.ui.save_best_score()
        self.start_game()
    
    def update(self):
        """Обновляет игровую логику"""
        if self.game_state != GameState.PLAYING:
            return
        
        # Обновляем игрока
        platform_particles = self.player.update(self.platforms)
        self.particles.extend(platform_particles)
        
        # Обновляем камеру
        self.camera.update(self.player)
        
        # Обновляем платформы
        for platform in self.platforms:
            platform.update()
        
        # Удаляем неактивные платформы
        self.platforms = [p for p in self.platforms if p.active or p.y > self.camera.y - 100]
        
        # Генерируем новые платформы при необходимости
        if self.player.y < self.camera.y - 500:
            new_platforms = self.platform_generator.generate_platforms(self.player.y - 1000, self.platforms)
            self.platforms.extend(new_platforms)
            
            # Генерируем предметы для новых платформ
            for platform in new_platforms:
                collectibles = self.collectible_generator.generate_for_platform(platform)
                self.collectibles.extend(collectibles)
        
        # Обновляем собираемые предметы
        for collectible in self.collectibles:
            collectible.update()
            
            if collectible.check_collision(self.player):
                if collectible.type == "crystal":
                    self.ui.crystals_collected += 1
                    self.ui.add_score(10)
                elif collectible.type == "bonus":
                    self.ui.activate_multiplier()
                elif collectible.type == "shield":
                    self.player.shield_active = True
                    self.player.shield_time = 300  # 5 секунд
                
                # Создаем частицы при сборе
                for _ in range(10):
                    self.particles.append(Particle(
                        collectible.x + random.randint(-10, 10),
                        collectible.y + random.randint(-10, 10),
                        random.uniform(-3, 3),
                        random.uniform(-5, -2),
                        YELLOW,
                        random.randint(20, 40)
                    ))
        
        # Удаляем собранные предметы
        self.collectibles = [c for c in self.collectibles if c.active]
        
        # Обновляем частицы
        for particle in self.particles:
            particle.update()
        
        # Удаляем мертвые частицы
        self.particles = [p for p in self.particles if p.life > 0]
        
        # Обновляем UI
        self.ui.update(self.player.y)
        
        # Проверяем условие окончания игры
        if self.player.y > self.camera.y + SCREEN_HEIGHT + 100:
            if not self.player.shield_active:
                self.game_state = GameState.GAME_OVER
            else:
                # Щит спасает от падения
                self.player.y = self.camera.y + SCREEN_HEIGHT - 100
                self.player.vel_y = JUMP_STRENGTH
                self.player.shield_active = False
    
    def draw(self):
        """Отрисовывает игру"""
        # Очищаем экран
        self.screen.fill(BLACK)
        
        if self.game_state == GameState.MENU:
            self.draw_menu()
        elif self.game_state == GameState.PLAYING:
            self.draw_game()
        elif self.game_state == GameState.PAUSED:
            self.draw_game()
            self.draw_pause_overlay()
        elif self.game_state == GameState.GAME_OVER:
            self.draw_game()
            self.draw_game_over_overlay()
        
        pygame.display.flip()
    
    def draw_menu(self):
        """Отрисовывает главное меню"""
        # Фон
        self.background.draw(self.screen, 0)
        
        # Заголовок
        title_font = pygame.font.Font(None, 48)
        title_text = title_font.render("Gravity Hopper", True, CYAN)
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, 150))
        self.screen.blit(title_text, title_rect)
        
        # Подзаголовок
        subtitle_font = pygame.font.Font(None, 24)
        subtitle_text = subtitle_font.render("Антигравитационный робот", True, WHITE)
        subtitle_rect = subtitle_text.get_rect(center=(SCREEN_WIDTH // 2, 190))
        self.screen.blit(subtitle_text, subtitle_rect)
        
        # Инструкции
        instructions = [
            "Нажмите для прыжка",
            "Удерживайте для высокого прыжка",
            "Свайп влево/вправо для движения",
            "",
            f"Лучший результат: {self.ui.best_score}",
            "",
            "Нажмите любую клавишу для начала"
        ]
        
        y_offset = 280
        for instruction in instructions:
            if instruction:
                text = self.ui.font_small.render(instruction, True, WHITE)
                text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, y_offset))
                self.screen.blit(text, text_rect)
            y_offset += 25
        
        # Анимированный робот-демонстрация
        demo_y = 450 + math.sin(pygame.time.get_ticks() * 0.003) * 20
        pygame.draw.circle(self.screen, CYAN, (SCREEN_WIDTH // 2, int(demo_y)), 15)
        pygame.draw.circle(self.screen, WHITE, (SCREEN_WIDTH // 2, int(demo_y)), 15, 2)
    
    def draw_game(self):
        """Отрисовывает игровой процесс"""
        # Фон
        self.background.draw(self.screen, self.camera.y)
        
        # Платформы
        for platform in self.platforms:
            platform.draw(self.screen, self.camera.y)
        
        # Собираемые предметы
        for collectible in self.collectibles:
            collectible.draw(self.screen, self.camera.y)
        
        # Частицы
        for particle in self.particles:
            particle.draw(self.screen, self.camera.y)
        
        # Игрок
        self.player.draw(self.screen, self.camera.y)
        
        # Индикатор зарядки прыжка
        charge = self.controls.get_jump_charge_visual()
        if charge > 0:
            bar_width = int(100 * charge)
            bar_rect = pygame.Rect(SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT - 30, bar_width, 10)
            pygame.draw.rect(self.screen, YELLOW, bar_rect)
            pygame.draw.rect(self.screen, WHITE, pygame.Rect(SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT - 30, 100, 10), 2)
        
        # UI
        self.ui.draw(self.screen)
    
    def draw_pause_overlay(self):
        """Отрисовывает оверлей паузы"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        pause_text = self.ui.font_large.render("ПАУЗА", True, WHITE)
        pause_rect = pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(pause_text, pause_rect)
        
        continue_text = self.ui.font_small.render("Нажмите P для продолжения", True, WHITE)
        continue_rect = continue_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40))
        self.screen.blit(continue_text, continue_rect)
    
    def draw_game_over_overlay(self):
        """Отрисовывает оверлей окончания игры"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        game_over_text = self.ui.font_large.render("ИГРА ОКОНЧЕНА", True, RED)
        game_over_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 60))
        self.screen.blit(game_over_text, game_over_rect)
        
        score_text = self.ui.font_medium.render(f"Очки: {self.ui.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
        self.screen.blit(score_text, score_rect)
        
        height_text = self.ui.font_medium.render(f"Высота: {self.ui.height_meters}м", True, WHITE)
        height_rect = height_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10))
        self.screen.blit(height_text, height_rect)
        
        crystals_text = self.ui.font_medium.render(f"Кристаллы: {self.ui.crystals_collected}", True, PURPLE)
        crystals_rect = crystals_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40))
        self.screen.blit(crystals_text, crystals_rect)
        
        if self.ui.score == self.ui.best_score and self.ui.score > 0:
            new_record_text = self.ui.font_medium.render("НОВЫЙ РЕКОРД!", True, YELLOW)
            new_record_rect = new_record_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70))
            self.screen.blit(new_record_text, new_record_rect)
        
        restart_text = self.ui.font_small.render("Нажмите любую клавишу для перезапуска", True, WHITE)
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 120))
        self.screen.blit(restart_text, restart_rect)
    
    def run(self):
        """Основной игровой цикл"""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        
        # Сохраняем лучший результат при выходе
        self.ui.save_best_score()
        pygame.quit()

def main():
    """Точка входа в программу"""
    game = GravityHopper()
    game.run()

if __name__ == "__main__":
    main()