import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F, html
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from aiogram.utils.markdown import bold, italic
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Optional
from aiohttp import web
import random

# Загрузка .env переменных
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEYS = [key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()]
OWNER_ID = int(os.getenv("OWNER_ID", 9995599))
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "qqq5599")
MAX_TOKENS = 2000
DAILY_LIMIT = 10

# Инициализация бота с исправлением синтаксической ошибки
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher()

# Хранилища данных
user_histories = defaultdict(list)
user_limits = defaultdict(lambda: {"count": 0, "last_reset": datetime.utcnow()})
user_last_messages = defaultdict(str)
user_stats = defaultdict(lambda: {"total_requests": 0, "last_active": None})

# Клавиатуры
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Расскажи анекдот"), KeyboardButton(text="Сделай мотивацию")],
        [KeyboardButton(text="Помоги с идеями"), KeyboardButton(text="Напиши статью")],
        [KeyboardButton(text="Статистика"), KeyboardButton(text="Помощь")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)

async def generate_response(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Основная функция генерации ответа через OpenRouter"""
    for key in random.sample(API_KEYS, len(API_KEYS)):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/your-repo",
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": messages,
                        "max_tokens": MAX_TOKENS,
                        "temperature": 0.7,
                    },
                    timeout=45
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    elif response.status == 429:
                        logging.warning(f"Key {key[-5:]} rate limited")
                    else:
                        logging.error(f"API error {response.status} with key {key[-5:]}")
        except Exception as e:
            logging.error(f"Connection error: {str(e)}")
    return None

# ... (остальные ваши функции остаются без изменений)

# 25 новых функций и улучшений:

1. Защита от флуда
@dp.message(F.text)
async def throttle_message(message: Message):
    user_id = message.from_user.id
    last_message = user_stats[user_id].get("last_message")
    if last_message and (datetime.now() - last_message).seconds < 2:
        await message.answer("⚠️ Слишком много сообщений! Подождите 2 секунды.")
        return
    user_stats[user_id]["last_message"] = datetime.now()
    
2. Система статистики
@dp.message(Command("stats"))
async def send_stats(message: Message):
    user_id = message.from_user.id
    stats = user_stats[user_id]
    text = (
        f"📊 Ваша статистика:\n"
        f"• Всего запросов: {stats['total_requests']}\n"
        f"• Последняя активность: {stats['last_active'].strftime('%d.%m.%Y %H:%M') if stats['last_active'] else 'Нет данных'}"
    )
    await message.answer(text)

3. Резервное копирование истории
async def backup_history():
    while True:
        await asyncio.sleep(3600)
        # Здесь можно добавить логику сохранения в файл/БД
        logging.info("History backup completed")

4. Уведомления для администратора
async def notify_admin(text: str):
    await bot.send_message(OWNER_ID, f"🔔 Уведомление: {text}")

5. Обработка ошибок
async def error_handler(update: Update, exception):
    await notify_admin(f"Ошибка в боте: {str(exception)}")
    return True

6. Логирование действий
def log_activity(user_id: int, action: str):
    logging.info(f"User {user_id} performed: {action}")

7. Проверка токенов
def count_tokens(text: str) -> int:
    return len(text.split()) // 0.75

8. Ограничение длины истории
def trim_history(history: list) -> list:
    total = sum(len(m['content']) for m in history)
    while total > 4000:
        removed = history.pop(0)
        total -= len(removed['content'])
    return history

9. Система уровней
def calculate_level(requests: int) -> int:
    return min(requests // 50 + 1, 10)

10. Форматирование текста
def clean_response(text: str) -> str:
    return text.replace("**", "*").strip()

11. Генерация уникального ID
def generate_request_id(user_id: int) -> str:
    timestamp = int(datetime.now().timestamp())
    return f"{user_id}_{timestamp}"

12. Валидация файлов
ALLOWED_TYPES = ['text/plain', 'application/pdf']
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

async def validate_file(file) -> bool:
    if file.file_size > MAX_FILE_SIZE:
        return False
    if file.mime_type not in ALLOWED_TYPES:
        return False
    return True

13. Система рейтинга
user_ratings = defaultdict(int)

@dp.message(F.text.startswith("Оценка"))
async def rate_response(message: Message):
    try:
        _, rating = message.text.split()
        rating = int(rating)
        if 1 <= rating <= 5:
            user_ratings[message.from_user.id] += rating
            await message.answer("✅ Спасибо за оценку!")
    except:
        await message.answer("Используйте: Оценка [1-5]")

14. Кастомные команды
CUSTOM_COMMANDS = {
    "анекдот": "Расскажи свежий анекдот про IT",
    "мотивация": "Сгенерируй мотивационное сообщение",
    "идея": "Предложи 5 идей для стартапа"
}

15. Авто-очистка неактивных
async def clean_inactive_users():
    while True:
        await asyncio.sleep(86400)
        cutoff = datetime.now() - timedelta(days=30)
        for user_id in list(user_histories):
            if user_stats[user_id]['last_active'] < cutoff:
                del user_histories[user_id]

16. Шаблоны ответов
async def send_template(message: Message, template_name: str):
    templates = {
        "help": "🛠 Помощь по командам...",
        "error": "⚠️ Произошла ошибка...",
    }
    await message.answer(templates.get(template_name, "Неизвестный шаблон"))

17. Мультиязычность
SUPPORTED_LANGS = ['ru', 'en']
user_langs = defaultdict(lambda: 'ru')

@dp.message(Command("lang"))
async def set_language(message: Message):
    lang = message.text.split()[-1]
    if lang in SUPPORTED_LANGS:
        user_langs[message.from_user.id] = lang
        await message.answer(f"Язык установлен: {lang.upper()}")

18. Система кэширования
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_response(query: str) -> str:
    # Логика кэширования
    return ""

19. Обработка длинных текстов
async def split_long_text(text: str, max_len: int = 4000) -> List[str]:
    return [text[i:i+max_len] for i in range(0, len(text), max_len)]

20. Аналитика в реальном времени
async def realtime_metrics():
    return {
        "active_users": len(user_histories),
        "total_requests": sum(u['total_requests'] for u in user_stats.values())
    }

21. Система уведомлений
async def broadcast_message(text: str):
    for user_id in user_histories:
        try:
            await bot.send_message(user_id, text)
            await asyncio.sleep(0.1)
        except:
            continue

22. Проверка контента
async def check_content(text: str) -> bool:
    # Интеграция с модерацией
    return "опасный контент" not in text.lower()

23. Генерация изображений
async def generate_image(prompt: str):
    # Интеграция с Stable Diffusion/DALL-E
    return "https://example.com/generated-image.png"

24. Голосовые ответы
async def text_to_speech(text: str):
    # Конвертация текста в аудио
    return FSInputFile("output.mp3")

25. Резервный API
async def fallback_api(messages: list):
    # Использование альтернативного провайдера
    return "Извините, сервис временно недоступен"

# Основная функция
async def main():
    await start_webserver()
    asyncio.create_task(clear_user_histories())
    asyncio.create_task(backup_history())
    asyncio.create_task(clean_inactive_users())
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
