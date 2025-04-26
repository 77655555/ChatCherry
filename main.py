import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, Document, Voice, KeyboardButton, ReplyKeyboardMarkup
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict

# Загрузка .env переменных
load_dotenv()

# Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEYS = os.getenv("API_KEYS").split(",")
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OWNER_ID = 9995599
OWNER_USERNAME = "qqq5599"

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

# Функция для запроса в OpenRouter
async def ask_openrouter(messages: list, api_keys: list):
    headers = {
        "Authorization": f"Bearer {api_keys[0]}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages
    }
    for key in api_keys:
        headers["Authorization"] = f"Bearer {key}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ENDPOINT, headers=headers, json=payload, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        continue
        except Exception:
            continue
    return "Все ключи недоступны. Попробуйте позже."

# Функция для очистки истории сообщений
async def clear_user_histories():
    while True:
        await asyncio.sleep(86400)  # 24 часа
        user_histories.clear()
        user_limits.clear()

# Middleware: проверка лимитов
async def check_limit(user_id: int, username: str):
    now = datetime.utcnow()
    user = user_limits[user_id]
    if now - user["last_reset"] > timedelta(days=1):
        user["count"] = 0
        user["last_reset"] = now
    if user_id == OWNER_ID or username == OWNER_USERNAME:
        return True
    return user["count"] < 10

async def increment_limit(user_id: int):
    user_limits[user_id]["count"] += 1

# Обработка команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, *{message.from_user.first_name}*!\n\n"
        "Я — умный помощник на базе *GPT-3.5 Turbo*.\n"
        "Пиши любой запрос, и я постараюсь ответить!\n\n"
        "_Доступно 10 сообщений в сутки._",
        reply_markup=menu_keyboard
    )

# Обработка команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🛠 *Помощь*\n\n"
        "/start — Начать общение\n"
        "/help — Помощь\n"
        "/reset — Очистить историю\n"
        "/menu — Показать меню кнопок\n\n"
        "_Пиши текст, отправляй голосовые или документы!_"
    )

# Обработка команды /reset
@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    user_histories.pop(message.from_user.id, None)
    await message.answer("История очищена! Начинаем с чистого листа.")

# Обработка команды /menu
@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("Выберите быстрый запрос:", reply_markup=menu_keyboard)

# Обработка текстовых сообщений
@dp.message(F.text)
async def handle_text(message: Message):
    await bot.send_chat_action(message.chat.id, action="typing")

    user_id = message.from_user.id
    username = message.from_user.username or ""

    if not await check_limit(user_id, username):
        await message.answer("⛔ *Достигнут лимит 10 сообщений в день.*\nПопробуйте завтра!")
        return

    user_histories[user_id].append({"role": "user", "content": message.text})

    response = await ask_openrouter(user_histories[user_id], API_KEYS)

    user_histories[user_id].append({"role": "assistant", "content": response})
    await increment_limit(user_id)

    await message.answer(response)

# Обработка документов
@dp.message(F.document)
async def handle_document(message: Message, document: Document):
    await bot.send_chat_action(message.chat.id, action="typing")

    user_id = message.from_user.id
    username = message.from_user.username or ""

    if not await check_limit(user_id, username):
        await message.answer("⛔ *Достигнут лимит 10 сообщений в день.*\nПопробуйте завтра!")
        return

    file = await bot.download(document)
    content = file.read().decode("utf-8")

    user_histories[user_id].append({"role": "user", "content": content})

    response = await ask_openrouter(user_histories[user_id], API_KEYS)

    user_histories[user_id].append({"role": "assistant", "content": response})
    await increment_limit(user_id)

    await message.answer(response)

# Обработка голосовых сообщений
@dp.message(F.voice)
async def handle_voice(message: Message, voice: Voice):
    await bot.send_chat_action(message.chat.id, action="typing")
    await message.answer("⛔ *Обработка голосовых пока не поддерживается.*\nПопробуйте текстом или документом.")

# Запуск бота
async def main():
    asyncio.create_task(clear_user_histories())
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
