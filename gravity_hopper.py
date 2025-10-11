"""
Gravity Hopper - Mobile 2D Game
Аркадный платформер с физикой для мобильных устройств
"""

import pygame
import random
import math
from typing import List, Tuple
from enum import Enum

# Инициализация Pygame
pygame.init()

# Константы игры
SCREEN_WIDTH = 360
SCREEN_HEIGHT = 640
FPS = 60

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (50, 205, 50)
BLUE = (30, 144, 255)
ORANGE = (255, 140, 0)
YELLOW = (255, 215, 0)
CYAN = (0, 255, 255)
PURPLE = (138, 43, 226)
DARK_BLUE = (10, 10, 40)
STAR_COLOR = (200, 200, 255)

# Физические константы
GRAVITY = 0.5
MAX_FALL_SPEED = 15
JUMP_FORCE_SHORT = -12
JUMP_FORCE_LONG = -18
AIR_CONTROL = 0.3
FRICTION = 0.95
BOOSTER_MULTIPLIER = 1.5


class GameState(Enum):
    """Состояния игры"""
    MENU = 1
    PLAYING = 2
    GAME_OVER = 3


class PlatformType(Enum):
    """Типы платформ"""
    NORMAL = 1
    MOVING = 2
    FRAGILE = 3
    BOOSTER = 4


class Particle:
    """Частица для визуальных эффектов"""
    def __init__(self, x: float, y: float, vx: float, vy: float, color: Tuple[int, int, int], lifetime: int):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.size = random.randint(2, 4)
    
    def update(self):
        """Обновление частицы"""
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.2  # Гравитация для частиц
        self.lifetime -= 1
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        """Отрисовка частицы"""
        if self.lifetime > 0:
            alpha = int(255 * (self.lifetime / self.max_lifetime))
            color = (*self.color, alpha)
            size = int(self.size * (self.lifetime / self.max_lifetime))
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y - camera_y)), max(1, size))
    
    def is_alive(self) -> bool:
        """Проверка, жива ли частица"""
        return self.lifetime > 0


class Collectible:
    """Собираемый предмет"""
    def __init__(self, x: float, y: float, collectible_type: str):
        self.x = x
        self.y = y
        self.type = collectible_type  # 'crystal', 'bonus', 'shield'
        self.collected = False
        self.animation_offset = 0
        self.rotation = 0
        
        if collectible_type == 'crystal':
            self.color = CYAN
            self.size = 8
            self.value = 10
        elif collectible_type == 'bonus':
            self.color = YELLOW
            self.size = 10
            self.value = 0  # Множитель, не очки
        else:  # shield
            self.color = PURPLE
            self.size = 12
            self.value = 0
    
    def update(self):
        """Обновление анимации"""
        self.animation_offset = math.sin(pygame.time.get_ticks() / 200) * 5
        self.rotation += 2
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        """Отрисовка предмета"""
        if not self.collected:
            draw_y = int(self.y - camera_y + self.animation_offset)
            
            if self.type == 'crystal':
                # Рисуем кристалл как ромб
                points = [
                    (self.x, draw_y - self.size),
                    (self.x + self.size, draw_y),
                    (self.x, draw_y + self.size),
                    (self.x - self.size, draw_y)
                ]
                pygame.draw.polygon(screen, self.color, points)
                pygame.draw.polygon(screen, WHITE, points, 2)
            elif self.type == 'bonus':
                # Рисуем бонус как звезду
                pygame.draw.circle(screen, self.color, (int(self.x), draw_y), self.size)
                pygame.draw.circle(screen, WHITE, (int(self.x), draw_y), self.size, 2)
                # Рисуем "×2"
                font = pygame.font.Font(None, 16)
                text = font.render("x2", True, BLACK)
                screen.blit(text, (int(self.x - 8), draw_y - 4))
            else:  # shield
                # Рисуем щит
                pygame.draw.circle(screen, self.color, (int(self.x), draw_y), self.size)
                pygame.draw.circle(screen, WHITE, (int(self.x), draw_y), self.size, 2)
    
    def get_rect(self) -> pygame.Rect:
        """Получение прямоугольника для коллизий"""
        return pygame.Rect(self.x - self.size, self.y - self.size, self.size * 2, self.size * 2)


class Platform:
    """Платформа"""
    def __init__(self, x: float, y: float, width: int, platform_type: PlatformType):
        self.x = x
        self.y = y
        self.width = width
        self.height = 10
        self.type = platform_type
        self.broken = False
        self.break_timer = 0
        self.alpha = 255
        
        # Параметры для движущихся платформ
        self.move_speed = random.uniform(1, 3) if platform_type == PlatformType.MOVING else 0
        self.move_direction = random.choice([-1, 1])
        self.move_range = 100
        self.start_x = x
        
        # Анимация для ускорителя
        self.bounce_offset = 0
        
        # Цвета по типу
        if platform_type == PlatformType.NORMAL:
            self.color = GREEN
        elif platform_type == PlatformType.MOVING:
            self.color = BLUE
        elif platform_type == PlatformType.FRAGILE:
            self.color = ORANGE
        else:  # BOOSTER
            self.color = YELLOW
    
    def update(self):
        """Обновление платформы"""
        # Движение для движущихся платформ
        if self.type == PlatformType.MOVING:
            self.x += self.move_speed * self.move_direction
            if abs(self.x - self.start_x) > self.move_range:
                self.move_direction *= -1
        
        # Разрушение хрупких платформ
        if self.type == PlatformType.FRAGILE and self.broken:
            self.break_timer += 1
            self.alpha = max(0, 255 - (self.break_timer * 8))
        
        # Анимация ускорителя
        if self.type == PlatformType.BOOSTER:
            self.bounce_offset = math.sin(pygame.time.get_ticks() / 100) * 3
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        """Отрисовка платформы"""
        if self.type == PlatformType.FRAGILE and self.alpha < 50:
            return
        
        draw_y = int(self.y - camera_y)
        
        if self.type == PlatformType.BOOSTER:
            draw_y += int(self.bounce_offset)
        
        # Основная платформа
        rect = pygame.Rect(int(self.x), draw_y, self.width, self.height)
        pygame.draw.rect(screen, self.color, rect)
        pygame.draw.rect(screen, WHITE, rect, 2)
        
        # Индикатор для движущихся платформ
        if self.type == PlatformType.MOVING:
            indicator_x = int(self.x + self.width / 2 + math.sin(pygame.time.get_ticks() / 200) * 10)
            pygame.draw.circle(screen, WHITE, (indicator_x, draw_y + 5), 3)
        
        # Пружина для ускорителя
        if self.type == PlatformType.BOOSTER:
            spring_x = int(self.x + self.width / 2)
            spring_top = draw_y - 10
            pygame.draw.line(screen, self.color, (spring_x, draw_y), (spring_x, spring_top), 3)
            pygame.draw.circle(screen, self.color, (spring_x, spring_top), 5)
    
    def get_rect(self) -> pygame.Rect:
        """Получение прямоугольника для коллизий"""
        if self.type == PlatformType.BOOSTER:
            return pygame.Rect(self.x, self.y + self.bounce_offset, self.width, self.height)
        return pygame.Rect(self.x, self.y, self.width, self.height)
    
    def activate_break(self):
        """Активация разрушения для хрупких платформ"""
        if self.type == PlatformType.FRAGILE:
            self.broken = True
    
    def is_destroyed(self) -> bool:
        """Проверка, разрушена ли платформа"""
        return self.broken and self.break_timer > 30


class Player:
    """Игрок - антигравитационный шарик"""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.radius = 10
        self.grounded = False
        self.jump_hold_time = 0
        self.max_jump_hold = 15
        self.has_shield = False
        self.glow_offset = 0
        
    def update(self, platforms: List[Platform]):
        """Обновление игрока"""
        # Применяем гравитацию
        self.vy += GRAVITY
        
        # Ограничиваем скорость падения
        if self.vy > MAX_FALL_SPEED:
            self.vy = MAX_FALL_SPEED
        
        # Применяем скорость
        self.x += self.vx
        self.y += self.vy
        
        # Применяем трение
        self.vx *= FRICTION
        
        # Ограничиваем по горизонтали
        if self.x < self.radius:
            self.x = self.radius
            self.vx = 0
        elif self.x > SCREEN_WIDTH - self.radius:
            self.x = SCREEN_WIDTH - self.radius
            self.vx = 0
        
        # Проверяем коллизии с платформами
        self.grounded = False
        for platform in platforms:
            if self.check_platform_collision(platform):
                self.grounded = True
        
        # Анимация свечения
        self.glow_offset = math.sin(pygame.time.get_ticks() / 200) * 2
    
    def check_platform_collision(self, platform: Platform) -> bool:
        """Проверка коллизии с платформой"""
        if platform.is_destroyed():
            return False
        
        platform_rect = platform.get_rect()
        
        # Проверяем, падает ли игрок на платформу сверху
        if (self.vy >= 0 and 
            self.x > platform_rect.left and 
            self.x < platform_rect.right and
            self.y + self.radius > platform_rect.top and
            self.y + self.radius < platform_rect.bottom + 10):
            
            # Приземляемся на платформу
            self.y = platform_rect.top - self.radius
            self.vy = 0
            
            # Наследуем горизонтальную скорость от движущейся платформы
            if platform.type == PlatformType.MOVING:
                self.vx += platform.move_speed * platform.move_direction * 0.5
            
            # Ускоритель
            if platform.type == PlatformType.BOOSTER:
                self.vy = JUMP_FORCE_LONG * BOOSTER_MULTIPLIER
            
            # Разрушаем хрупкую платформу
            if platform.type == PlatformType.FRAGILE:
                platform.activate_break()
            
            return True
        
        return False
    
    def jump(self, is_short: bool = True):
        """Прыжок"""
        if self.grounded:
            self.vy = JUMP_FORCE_SHORT if is_short else JUMP_FORCE_LONG
            self.jump_hold_time = 0
    
    def move_horizontal(self, direction: float):
        """Горизонтальное движение в воздухе"""
        self.vx += direction * AIR_CONTROL
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        """Отрисовка игрока"""
        draw_y = int(self.y - camera_y)
        
        # Свечение
        glow_radius = int(self.radius + 5 + self.glow_offset)
        glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (0, 255, 255, 50), (glow_radius, glow_radius), glow_radius)
        screen.blit(glow_surface, (int(self.x - glow_radius), draw_y - glow_radius))
        
        # Основной шарик
        pygame.draw.circle(screen, CYAN, (int(self.x), draw_y), self.radius)
        pygame.draw.circle(screen, WHITE, (int(self.x), draw_y), self.radius, 2)
        
        # Внутреннее ядро
        pygame.draw.circle(screen, WHITE, (int(self.x), draw_y), self.radius // 2)
        
        # Щит
        if self.has_shield:
            shield_radius = self.radius + 8
            pygame.draw.circle(screen, PURPLE, (int(self.x), draw_y), shield_radius, 3)
    
    def get_rect(self) -> pygame.Rect:
        """Получение прямоугольника для коллизий"""
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)


class Camera:
    """Камера, следующая за игроком"""
    def __init__(self):
        self.y = 0
        self.target_y = 0
        self.smoothness = 0.1
    
    def update(self, player_y: float):
        """Обновление камеры"""
        # Камера следует за игроком, когда он поднимается выше середины экрана
        if player_y < self.y + SCREEN_HEIGHT / 3:
            self.target_y = player_y - SCREEN_HEIGHT / 3
        
        # Плавное движение камеры
        self.y += (self.target_y - self.y) * self.smoothness


class ParallaxBackground:
    """Параллакс-фон с тремя слоями"""
    def __init__(self):
        self.layers = []
        # Создаем звезды для трех слоев
        for layer_index in range(3):
            stars = []
            speed = 0.1 + layer_index * 0.05  # Разная скорость для слоев
            num_stars = 30 + layer_index * 20
            
            for _ in range(num_stars):
                x = random.randint(0, SCREEN_WIDTH)
                y = random.randint(0, SCREEN_HEIGHT * 3)
                size = random.randint(1, 3)
                stars.append({'x': x, 'y': y, 'size': size})
            
            self.layers.append({'stars': stars, 'speed': speed})
    
    def draw(self, screen: pygame.Surface, camera_y: float):
        """Отрисовка параллакс-фона"""
        screen.fill(DARK_BLUE)
        
        for layer in self.layers:
            for star in layer['stars']:
                # Параллакс эффект
                offset_y = (camera_y * layer['speed']) % (SCREEN_HEIGHT * 3)
                draw_y = star['y'] - offset_y
                
                # Зацикливаем звезды
                if draw_y < -50:
                    draw_y += SCREEN_HEIGHT * 3
                elif draw_y > SCREEN_HEIGHT + 50:
                    draw_y -= SCREEN_HEIGHT * 3
                
                if -50 < draw_y < SCREEN_HEIGHT + 50:
                    pygame.draw.circle(screen, STAR_COLOR, (int(star['x']), int(draw_y)), star['size'])


class Game:
    """Основной класс игры"""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Gravity Hopper")
        self.clock = pygame.time.Clock()
        self.state = GameState.MENU
        
        # Игровые объекты
        self.player = None
        self.platforms = []
        self.collectibles = []
        self.particles = []
        self.camera = Camera()
        self.background = ParallaxBackground()
        
        # Игровые данные
        self.score = 0
        self.best_score = 0
        self.height = 0
        self.best_height = 0
        self.multiplier = 1
        self.multiplier_timer = 0
        self.crystals_collected = 0
        
        # Управление
        self.mouse_pressed = False
        self.mouse_press_time = 0
        self.swipe_start_x = 0
        
        # Шрифты
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 24)
    
    def reset_game(self):
        """Сброс игры для нового раунда"""
        self.player = Player(SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100)
        self.platforms = []
        self.collectibles = []
        self.particles = []
        self.camera = Camera()
        
        self.score = 0
        self.height = 0
        self.multiplier = 1
        self.multiplier_timer = 0
        self.crystals_collected = 0
        
        # Генерируем начальные платформы
        for i in range(10):
            self.generate_platform(i * 80)
    
    def generate_platform(self, y: float):
        """Генерация новой платформы"""
        # Определяем тип платформы
        rand = random.random()
        if rand < 0.6:
            platform_type = PlatformType.NORMAL
        elif rand < 0.85:
            platform_type = PlatformType.MOVING
        elif rand < 0.95:
            platform_type = PlatformType.FRAGILE
        else:
            platform_type = PlatformType.BOOSTER
        
        # Размер платформы
        width = random.randint(60, 100)
        x = random.randint(width // 2, SCREEN_WIDTH - width // 2)
        
        platform = Platform(x - width // 2, y, width, platform_type)
        self.platforms.append(platform)
        
        # Иногда добавляем собираемый предмет
        if random.random() < 0.3:
            collectible_type = random.choice(['crystal', 'crystal', 'crystal', 'bonus', 'shield'])
            collectible = Collectible(x, y - 40, collectible_type)
            self.collectibles.append(collectible)
    
    def update(self):
        """Обновление игры"""
        if self.state == GameState.PLAYING:
            # Обновляем игрока
            self.player.update(self.platforms)
            
            # Обновляем платформы
            for platform in self.platforms:
                platform.update()
            
            # Удаляем разрушенные платформы
            self.platforms = [p for p in self.platforms if not p.is_destroyed()]
            
            # Обновляем собираемые предметы
            for collectible in self.collectibles:
                collectible.update()
                
                # Проверяем сбор предметов
                if not collectible.collected:
                    player_rect = self.player.get_rect()
                    collectible_rect = collectible.get_rect()
                    
                    if player_rect.colliderect(collectible_rect):
                        collectible.collected = True
                        self.collect_item(collectible)
            
            # Удаляем собранные предметы
            self.collectibles = [c for c in self.collectibles if not c.collected]
            
            # Обновляем камеру
            self.camera.update(self.player.y)
            
            # Обновляем частицы
            for particle in self.particles:
                particle.update()
            self.particles = [p for p in self.particles if p.is_alive()]
            
            # Генерируем новые платформы
            highest_platform = min([p.y for p in self.platforms]) if self.platforms else 0
            while highest_platform > self.camera.y - SCREEN_HEIGHT:
                highest_platform -= 80
                self.generate_platform(highest_platform)
            
            # Удаляем платформы, которые ушли за экран
            self.platforms = [p for p in self.platforms if p.y < self.camera.y + SCREEN_HEIGHT + 100]
            self.collectibles = [c for c in self.collectibles if c.y < self.camera.y + SCREEN_HEIGHT + 100]
            
            # Обновляем высоту и счет
            current_height = max(0, -int(self.player.y) // 10)
            if current_height > self.height:
                self.height = current_height
                if self.height > self.best_height:
                    self.best_height = self.height
            
            # Обновляем таймер множителя
            if self.multiplier > 1:
                self.multiplier_timer -= 1
                if self.multiplier_timer <= 0:
                    self.multiplier = 1
            
            # Проверяем падение за экран
            if self.player.y > self.camera.y + SCREEN_HEIGHT + 50:
                if self.player.has_shield:
                    # Используем щит
                    self.player.has_shield = False
                    self.player.y = self.camera.y + SCREEN_HEIGHT / 2
                    self.player.vy = JUMP_FORCE_LONG
                    self.create_particles(self.player.x, self.player.y, PURPLE, 20)
                else:
                    # Игра окончена
                    self.state = GameState.GAME_OVER
                    if self.score > self.best_score:
                        self.best_score = self.score
    
    def collect_item(self, collectible: Collectible):
        """Сбор предмета"""
        if collectible.type == 'crystal':
            self.score += collectible.value * self.multiplier
            self.crystals_collected += 1
            self.create_particles(collectible.x, collectible.y, CYAN, 10)
        elif collectible.type == 'bonus':
            self.multiplier = 2
            self.multiplier_timer = 600  # 10 секунд при 60 FPS
            self.create_particles(collectible.x, collectible.y, YELLOW, 15)
        else:  # shield
            self.player.has_shield = True
            self.create_particles(collectible.x, collectible.y, PURPLE, 15)
    
    def create_particles(self, x: float, y: float, color: Tuple[int, int, int], count: int):
        """Создание частиц для эффектов"""
        for _ in range(count):
            vx = random.uniform(-3, 3)
            vy = random.uniform(-3, 3)
            lifetime = random.randint(20, 40)
            self.particles.append(Particle(x, y, vx, vy, color, lifetime))
    
    def draw(self):
        """Отрисовка игры"""
        if self.state == GameState.MENU:
            self.draw_menu()
        elif self.state == GameState.PLAYING:
            self.draw_game()
        elif self.state == GameState.GAME_OVER:
            self.draw_game_over()
        
        pygame.display.flip()
    
    def draw_menu(self):
        """Отрисовка меню"""
        self.screen.fill(DARK_BLUE)
        
        # Заголовок
        title = self.font_large.render("GRAVITY HOPPER", True, CYAN)
        title_rect = title.get_rect(center=(SCREEN_WIDTH / 2, 150))
        self.screen.blit(title, title_rect)
        
        # Инструкции
        instructions = [
            "Управление:",
            "Короткое нажатие - короткий прыжок",
            "Долгое нажатие - высокий прыжок",
            "Свайп влево/вправо - движение",
            "",
            "Нажмите в любом месте для старта"
        ]
        
        y = 250
        for line in instructions:
            text = self.font_small.render(line, True, WHITE)
            text_rect = text.get_rect(center=(SCREEN_WIDTH / 2, y))
            self.screen.blit(text, text_rect)
            y += 30
        
        # Лучший результат
        if self.best_score > 0:
            best = self.font_medium.render(f"Лучший счет: {self.best_score}", True, YELLOW)
            best_rect = best.get_rect(center=(SCREEN_WIDTH / 2, 500))
            self.screen.blit(best, best_rect)
    
    def draw_game(self):
        """Отрисовка игрового процесса"""
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
        
        # UI
        self.draw_ui()
    
    def draw_ui(self):
        """Отрисовка пользовательского интерфейса"""
        # Полупрозрачная панель сверху
        panel = pygame.Surface((SCREEN_WIDTH, 80))
        panel.set_alpha(200)
        panel.fill(BLACK)
        self.screen.blit(panel, (0, 0))
        
        # Текущий счет
        score_text = self.font_medium.render(f"Счет: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 10))
        
        # Лучший результат
        best_text = self.font_small.render(f"Лучший: {self.best_score}", True, YELLOW)
        self.screen.blit(best_text, (SCREEN_WIDTH - 150, 10))
        
        # Высота
        height_text = self.font_small.render(f"Высота: {self.height}м", True, CYAN)
        self.screen.blit(height_text, (10, 45))
        
        # Кристаллы
        crystal_text = self.font_small.render(f"Кристаллы: {self.crystals_collected}", True, CYAN)
        self.screen.blit(crystal_text, (SCREEN_WIDTH - 150, 45))
        
        # Множитель
        if self.multiplier > 1:
            mult_text = self.font_medium.render(f"x{self.multiplier}", True, YELLOW)
            mult_rect = mult_text.get_rect(center=(SCREEN_WIDTH / 2, 35))
            self.screen.blit(mult_text, mult_rect)
            
            # Таймер множителя
            timer_width = 100
            timer_height = 5
            timer_fill = (self.multiplier_timer / 600) * timer_width
            pygame.draw.rect(self.screen, WHITE, 
                           (SCREEN_WIDTH / 2 - timer_width / 2, 60, timer_width, timer_height), 1)
            pygame.draw.rect(self.screen, YELLOW,
                           (SCREEN_WIDTH / 2 - timer_width / 2, 60, timer_fill, timer_height))
    
    def draw_game_over(self):
        """Отрисовка экрана окончания игры"""
        # Рисуем игровое поле с затемнением
        self.draw_game()
        
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        # Текст "Game Over"
        game_over_text = self.font_large.render("ИГРА ОКОНЧЕНА", True, WHITE)
        game_over_rect = game_over_text.get_rect(center=(SCREEN_WIDTH / 2, 200))
        self.screen.blit(game_over_text, game_over_rect)
        
        # Статистика
        stats = [
            f"Финальный счет: {self.score}",
            f"Лучший счет: {self.best_score}",
            f"Высота: {self.height}м",
            f"Кристаллы: {self.crystals_collected}",
            "",
            "Нажмите для перезапуска"
        ]
        
        y = 300
        for line in stats:
            color = YELLOW if "Лучший" in line or "Финальный" in line else WHITE
            text = self.font_medium.render(line, True, color)
            text_rect = text.get_rect(center=(SCREEN_WIDTH / 2, y))
            self.screen.blit(text, text_rect)
            y += 40
    
    def handle_input(self, event):
        """Обработка ввода"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.state == GameState.MENU:
                self.reset_game()
                self.state = GameState.PLAYING
            elif self.state == GameState.GAME_OVER:
                self.state = GameState.MENU
            elif self.state == GameState.PLAYING:
                self.mouse_pressed = True
                self.mouse_press_time = pygame.time.get_ticks()
                self.swipe_start_x = event.pos[0]
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.state == GameState.PLAYING and self.mouse_pressed:
                self.mouse_pressed = False
                press_duration = pygame.time.get_ticks() - self.mouse_press_time
                
                # Проверяем свайп
                swipe_distance = event.pos[0] - self.swipe_start_x
                if abs(swipe_distance) > 30:
                    # Свайп для горизонтального движения
                    self.player.move_horizontal(swipe_distance / 10)
                else:
                    # Прыжок
                    is_short = press_duration < 300
                    self.player.jump(is_short)
                    self.create_particles(self.player.x, self.player.y + self.player.radius, 
                                        CYAN, 8)
    
    def run(self):
        """Основной игровой цикл"""
        running = True
        
        while running:
            # Обработка событий
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_input(event)
            
            # Обновление
            self.update()
            
            # Отрисовка
            self.draw()
            
            # Ограничение FPS
            self.clock.tick(FPS)
        
        pygame.quit()


def main():
    """Точка входа в игру"""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
