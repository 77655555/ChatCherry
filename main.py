import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
from aiohttp import web
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEYS = [key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()]
ADMIN_USERNAME = "@qqq5599"  # Ваш юзернейм с безлимитом
DAILY_LIMIT = 10  # Лимит для обычных пользователей

# Инициализация бота с исправленным синтаксисом
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
dp = Dispatcher()

# Хранилища данных
user_histories = defaultdict(list)
user_limits = defaultdict(lambda: {"count": 0, "last_reset": datetime.utcnow()})
user_last_messages = defaultdict(str)

# Клавиатура
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Расскажи анекдот"), KeyboardButton(text="Сделай мотивацию")],
        [KeyboardButton(text="Помоги с идеями"), KeyboardButton(text="Напиши статью")],
        [KeyboardButton(text="Помощь")]
    ],
    resize_keyboard=True
)

async def check_limit(user: types.User) -> bool:
    """Проверка лимита запросов"""
    if user.username and user.username.lower() == ADMIN_USERNAME.lower():
        return True
    
    now = datetime.utcnow()
    user_data = user_limits[user.id]
    
    # Сброс счетчика раз в сутки
    if (now - user_data["last_reset"]).days >= 1:
        user_data["count"] = 0
        user_data["last_reset"] = now
    
    return user_data["count"] < DAILY_LIMIT

async def ask_gpt(messages: List[Dict[str, Any]]) -> str:
    """Запрос к OpenAI через OpenRouter"""
    for key in API_KEYS:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": "gpt-3.5-turbo", "messages": messages},
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
        except Exception as e:
            logging.error(f"Ошибка API: {str(e)}")
    return "❗ Сервис временно недоступен"

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        f"✨ Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Я ваш персональный AI помощник\n"
        f"Лимит запросов: {DAILY_LIMIT}/день\n"
        "Используйте /help для списка команд",
        reply_markup=menu_keyboard
    )

@dp.message(F.text | F.document)
async def handle_message(message: Message):
    user = message.from_user
    if not await check_limit(user):
        await message.answer(f"⛔ Лимит {DAILY_LIMIT} запросов исчерпан!")
        return

    # Обработка контента
    content = message.text or await process_file(message)
    if not content:
        return

    # Генерация ответа
    user_histories[user.id].append({"role": "user", "content": content})
    response = await ask_gpt(user_histories[user.id])
    
    # Обновление хранилища
    user_histories[user.id].append({"role": "assistant", "content": response})
    user_limits[user.id]["count"] += 1
    await message.answer(response[:4000])  # Ограничение длины сообщения

async def process_file(message: Message) -> Optional[str]:
    """Обработка вложенных файлов"""
    if message.document:
        if message.document.file_size > 5 * 1024 * 1024:  # 5MB
            await message.answer("❌ Файл слишком большой!")
            return None
        try:
            file = await bot.get_file(message.document.file_id)
            content = (await bot.download_file(file.file_path)).read().decode()
            return content
        except Exception as e:
            logging.error(f"Ошибка обработки файла: {str(e)}")
            await message.answer("❌ Ошибка чтения файла!")
    return None

# Веб-сервер для проверки работоспособности
async def health_check(request):
    return web.Response(text="OK")

async def run_webserver():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8080).start()

async def main():
    await run_webserver()
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logging.critical(f"Ошибка: {str(e)}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
