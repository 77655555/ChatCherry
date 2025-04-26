import os
import sys
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, Document, Voice, KeyboardButton, ReplyKeyboardMarkup
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.utils.markdown import bold, italic
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any

# Загрузка .env переменных
load_dotenv()

# Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEYS = [key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()]
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OWNER_ID = 9995599
OWNER_USERNAME = "qqq5599"
WEBHOOK_HOST = 'https://chatcherry-4.onrender.com'
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher()

# Память для истории сообщений
user_histories = defaultdict(list)

# Память лимитов
user_limits = defaultdict(lambda: {"count": 0, "last_reset": datetime.utcnow()})

# Кнопки быстрого ответа
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Расскажи анекдот"), KeyboardButton(text="Сделай мотивацию")],
        [KeyboardButton(text="Помоги с идеями"), KeyboardButton(text="Напиши статью")]
    ],
    resize_keyboard=True
)

# Функция для запроса в OpenRouter с автосменой ключей
async def ask_openrouter(messages: List[Dict[str, Any]], api_keys: List[str]):
    for idx, key in enumerate(api_keys):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": messages
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ENDPOINT, headers=headers, json=payload, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    elif response.status in (401, 403, 429):
                        continue
                    else:
                        return "❗ *Ошибка на стороне OpenRouter.*"
        except Exception:
            continue
    return "❗ *Все API-ключи недоступны. Попробуйте позже.*"

# Очистка истории пользователей раз в сутки
async def clear_user_histories():
    while True:
        await asyncio.sleep(86400)  # 24 часа
        user_histories.clear()
        user_limits.clear()

# Проверка лимита
async def check_limit(user_id: int, username: str):
    now = datetime.utcnow()
    user = user_limits[user_id]
    if now - user["last_reset"] > timedelta(days=1):
        user["count"] = 0
        user["last_reset"] = now
    if user_id == OWNER_ID or username == OWNER_USERNAME:
        return True
    return user["count"] < 10

# Увеличение лимита
async def increment_limit(user_id: int):
    user_limits[user_id]["count"] += 1

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, *{message.from_user.first_name}*!\n\n"
        "Я — умный помощник на базе *GPT-3.5 Turbo*.\n"
        "Пиши текст или отправляй документ, и я постараюсь ответить!\n\n"
        "_У вас 10 сообщений в сутки._",
        reply_markup=menu_keyboard
    )

# Команда /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🛠 *Помощь*\n\n"
        "/start — Начать общение\n"
        "/help — Помощь\n"
        "/reset — Очистить историю сообщений\n"
        "/menu — Показать меню кнопок\n\n"
        "_Пишите сообщения, отправляйте документы!_"
    )

# Команда /reset
@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    user_histories.pop(message.from_user.id, None)
    await message.answer("✅ *История очищена!*")

# Команда /menu
@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("📋 Выберите действие:", reply_markup=menu_keyboard)

# Обработка текстовых сообщений
@dp.message(F.text)
async def handle_text(message: Message):
    await bot.send_chat_action(message.chat.id, action="typing")
    user_id = message.from_user.id
    username = message.from_user.username or ""

    if not await check_limit(user_id, username):
        await message.answer("⛔ *Достигнут лимит 10 сообщений в сутки.*\nПопробуйте завтра.")
        return

    user_histories[user_id].append({"role": "user", "content": message.text})

    response = await ask_openrouter(user_histories[user_id], API_KEYS)

    user_histories[user_id].append({"role": "assistant", "content": response})
    await increment_limit(user_id)

    await message.answer(response)

# Обработка документов
@dp.message(F.document)
async def handle_document(message: Message):
    await bot.send_chat_action(message.chat.id, action="typing")
    user_id = message.from_user.id
    username = message.from_user.username or ""

    if not await check_limit(user_id, username):
        await message.answer("⛔ *Достигнут лимит 10 сообщений в сутки.*\nПопробуйте завтра.")
        return

    file = await bot.download(message.document.file_id)
    content = (await file.read()).decode("utf-8")

    user_histories[user_id].append({"role": "user", "content": content})

    response = await ask_openrouter(user_histories[user_id], API_KEYS)

    user_histories[user_id].append({"role": "assistant", "content": response})
    await increment_limit(user_id)

    await message.answer(response)

# Обработка голосовых сообщений
@dp.message(F.voice)
async def handle_voice(message: Message):
    await bot.send_chat_action(message.chat.id, action="typing")
    await message.answer("🎙 *Обработка голосовых пока в разработке!*\nПожалуйста, используйте текст или документы.")

# При запуске
async def on_startup(app):
    asyncio.create_task(clear_user_histories())
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")

# Aiohttp-приложение
app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
app.on_startup.append(on_startup)

# Запуск через веб-сервер
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 3000)))
