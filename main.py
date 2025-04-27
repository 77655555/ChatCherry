import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from aiogram.utils.markdown import bold, italic, code
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Optional
from aiohttp import web
import json
import hashlib
from functools import lru_cache

# Configuration
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEYS = [key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()]
ADMIN_USERNAME = "@qqq5599"
DAILY_LIMIT = 10
MAX_HISTORY_LENGTH = 10
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_MIME_TYPES = ['text/plain', 'application/pdf']

# Initialize bot with markdown parsing
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
dp = Dispatcher()

# Memory storage with periodic cleanup
class UserStorage:
    def __init__(self):
        self.histories = defaultdict(list)
        self.limits = defaultdict(lambda: {"count": 0, "last_reset": datetime.utcnow()})
        self.last_messages = defaultdict(str)
        self.user_settings = defaultdict(dict)

    def cleanup(self):
        now = datetime.utcnow()
        for user_id in list(self.limits):
            if (now - self.limits[user_id]["last_reset"]).days > 30:
                del self.limits[user_id]
                del self.histories[user_id]
                del self.last_messages[user_id]

storage = UserStorage()

# Rate limiter decorator
def rate_limit(limit: int = 3, interval: int = 60):
    def decorator(func):
        last_calls = defaultdict(float)
        
        async def wrapper(message: Message, *args, **kwargs):
            user_id = message.from_user.id
            now = datetime.now().timestamp()
            if now - last_calls[user_id] < interval:
                await message.answer("⚠️ Слишком много запросов! Подождите немного.")
                return
            last_calls[user_id] = now
            return await func(message, *args, **kwargs)
        return wrapper
    return decorator

# Enhanced GPT client with caching
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
                        return data['choices'][0]['message']['content']
                    elif response.status == 429:
                        logging.warning(f"Rate limited on key: {key[-5:]}")
            except Exception as e:
                logging.error(f"API Error: {str(e)}")
            
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        return None

    async def close(self):
        await self.session.close()

gpt_client = OpenRouterClient(API_KEYS)

# Security validators
def is_admin(user: types.User) -> bool:
    return user.username.lower() == ADMIN_USERNAME.lower()

async def validate_file(file: types.Document) -> bool:
    if file.file_size > MAX_FILE_SIZE:
        return False
    if file.mime_type not in ALLOWED_MIME_TYPES:
        return False
    return True

# Core handlers
@dp.message(Command("start"))
async def start_handler(message: Message):
    user = message.from_user
    await message.answer(
        f"✨ Добро пожаловать, {bold(user.first_name)}!\n\n"
        "Я ваш персональный AI помощник с следующими возможностями:\n"
        "• Генерация текстов и идей\n"
        "• Анализ документов\n"
        "• Персональные рекомендации\n\n"
        f"{italic('Лимит запросов:')} {DAILY_LIMIT}/день\n"
        f"Используйте {code('/help')} для списка команд",
        reply_markup=main_menu()
    )

@dp.message(Command("help"))
async def help_handler(message: Message):
    help_text = (
        "🛠 Доступные команды:\n\n"
        "/start - Перезапустить бота\n"
        "/help - Справка по командам\n"
        "/status - Статус лимитов\n"
        "/reset - Сбросить историю\n"
        "/feedback - Отправить отзыв\n"
    )
    if is_admin(message.from_user):
        help_text += "\n👑 Админ-команды:\n/reset_all - Полный сброс\n/stats - Статистика"
    await message.answer(help_text)

@dp.message(Command("status"))
async def status_handler(message: Message):
    user = message.from_user
    limit_data = storage.limits[user.id]
    remaining = DAILY_LIMIT - limit_data["count"] if not is_admin(user) else "∞"
    await message.answer(
        f"📊 Ваш статус:\n"
        f"• Использовано запросов: {limit_data['count']}\n"
        f"• Осталось: {remaining}\n"
        f"• Следующий сброс: {(limit_data['last_reset'] + timedelta(days=1)).strftime('%d.%m.%Y %H:%M')}"
    )

@dp.message(Command("reset"))
async def reset_handler(message: Message):
    user_id = message.from_user.id
    storage.histories[user_id].clear()
    await message.answer("✅ История диалога очищена!")

# Admin commands
@dp.message(Command("reset_all"))
async def reset_all_handler(message: Message):
    if is_admin(message.from_user):
        storage.histories.clear()
        storage.limits.clear()
        await message.answer("🔥 Все данные сброшены!")
    else:
        await message.answer("⛔ Недостаточно прав!")

@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if is_admin(message.from_user):
        total_users = len(storage.limits)
        total_requests = sum(v["count"] for v in storage.limits.values())
        await message.answer(
            f"📈 Статистика:\n"
            f"• Пользователей: {total_users}\n"
            f"• Всего запросов: {total_requests}\n"
            f"• Активных диалогов: {len(storage.histories)}"
        )
    else:
        await message.answer("⛔ Недостаточно прав!")

# Main processing
@dp.message(F.text | F.document)
@rate_limit(limit=5, interval=60)
async def process_message(message: Message):
    user = message.from_user
    if not is_admin(user) and storage.limits[user.id]["count"] >= DAILY_LIMIT:
        await message.answer(
            f"⛔ Достигнут дневной лимит {DAILY_LIMIT} запросов!\n"
            f"Лимит сбросится {(storage.limits[user.id]['last_reset'] + timedelta(days=1)).strftime('%d.%m.%Y %H:%M')}"
        )
        return

    # File processing
    if message.document:
        if not await validate_file(message.document):
            await message.answer("❌ Недопустимый формат файла!")
            return
        try:
            file = await bot.get_file(message.document.file_id)
            content = (await bot.download_file(file.file_path)).read().decode()
        except Exception as e:
            logging.error(f"File error: {str(e)}")
            await message.answer("❌ Ошибка обработки файла!")
            return
    else:
        content = message.text

    # Generate response
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    storage.histories[user.id].append({"role": "user", "content": content})
    
    try:
        response = await gpt_client.get_response(storage.histories[user.id])
        if not response:
            raise ValueError("Empty response")
    except Exception as e:
        logging.error(f"Generation error: {str(e)}")
        await message.answer("⚠️ Ошибка генерации ответа. Попробуйте позже.")
        return

    # Update storage
    storage.histories[user.id].append({"role": "assistant", "content": response})
    if not is_admin(user):
        storage.limits[user.id]["count"] += 1
    storage.last_messages[user.id] = response

    # Send response
    await message.answer(response[:4000])  # Telegram message limit

# Web server for health checks
async def health_handler(request):
    return web.Response(text="OK")

async def run_webserver():
    app = web.Application()
    app.router.add_get("/", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8080).start()

# Utilities
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💡 Идеи"), KeyboardButton(text="📝 Контент")],
            [KeyboardButton(text="🎲 Анекдот"), KeyboardButton(text="📊 Статус")],
            [KeyboardButton(text="🛠 Помощь")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

async def shutdown():
    await gpt_client.close()
    await bot.session.close()

async def main():
    await run_webserver()
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await shutdown()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
