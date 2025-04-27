import os
import logging
import aiohttp
import asyncio
import time
from functools import wraps
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.markdown import bold, italic, code
from collections import defaultdict
from aiohttp import web
from dotenv import load_dotenv

# Инициализация окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEYS = [key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()]
ADMIN_USERNAME = "@qqq5599"
DAILY_LIMIT = 10
MAX_HISTORY_LENGTH = 10
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_MIME_TYPES = ['text/plain', 'application/pdf']

# Исправлено: Добавлены закрывающие скобки для Bot
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
)
dp = Dispatcher()

# Улучшенное хранилище с периодической очисткой
class UserStorage:
    def __init__(self):
        self.histories = defaultdict(list)
        self.limits = defaultdict(lambda: {
            "count": 0, 
            "last_reset": datetime.now(timezone.utc)
        })
        self.last_messages = defaultdict(str)
        self.user_settings = defaultdict(dict)
        self.cleanup_task = None

    async def start_periodic_cleanup(self):
        while True:
            await asyncio.sleep(3600)  # Каждый час
            self.cleanup()

    def cleanup(self):
        now = datetime.now(timezone.utc)
        for user_id in list(self.limits):
            if (now - self.limits[user_id]["last_reset"]).days > 30:
                del self.limits[user_id]
                del self.histories[user_id]
                del self.last_messages[user_id]

storage = UserStorage()

# Улучшенный rate limiter с использованием monotonic
def rate_limit(limit: int = 3, interval: int = 60):
    def decorator(func):
        last_calls = defaultdict(float)
        
        @wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            user_id = message.from_user.id
            now = time.monotonic()
            if now - last_calls[user_id] < interval:
                await message.answer("⚠️ Слишком много запросов! Подождите немного.")
                return
            last_calls[user_id] = now
            return await func(message, *args, **kwargs)
        return wrapper
    return decorator

# Улучшенный клиент OpenRouter с обработкой ошибок
class OpenRouterClient:
    def __init__(self, api_keys: list):
        self.api_keys = api_keys
        self.session = aiohttp.ClientSession()
        self.current_key_idx = 0

    async def get_response(self, messages: list) -> Optional[str]:
        for _ in range(len(self.api_keys)):
            key = self.api_keys[self.current_key_idx]
            try:
                async with self.session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": messages[-MAX_HISTORY_LENGTH:],
                        "temperature": 0.7,
                        "max_tokens": 1500
                    },
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'choices' in data and len(data['choices']) > 0:
                            return data['choices'][0]['message']['content']
                        return "Ошибка: пустой ответ от API"
                    elif response.status == 429:
                        logging.warning(f"Rate limited on key: {key[-5:]}")
            except Exception as e:
                logging.error(f"API Error: {str(e)}")
            
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        return None

    async def close(self):
        await self.session.close()

gpt_client = OpenRouterClient(API_KEYS)

# Обработчики команд и сообщений остаются аналогичными, но с улучшениями...

async def shutdown():
    await gpt_client.close()
    await bot.close()  # Исправленный метод закрытия бота

async def main():
    await run_webserver()
    storage.cleanup_task = asyncio.create_task(storage.start_periodic_cleanup())
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    finally:
        await shutdown()
        if storage.cleanup_task:
            storage.cleanup_task.cancel()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
