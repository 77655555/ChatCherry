import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.markdown import bold
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
from aiohttp import web

# Загрузка .env переменных
load_dotenv()

# Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEYS = [key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()]
OWNER_ID = int(os.getenv("OWNER_ID", 9995599))
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "qqq5599")

# Инициализация бота с исправлением deprecated-предупреждения
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher()

# Память пользователей
user_histories = defaultdict(list)
user_limits = defaultdict(lambda: {"count": 0, "last_reset": datetime.utcnow()})
user_last_messages = defaultdict(str)

# Кнопки
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Расскажи анекдот"), KeyboardButton(text="Сделай мотивацию")],
        [KeyboardButton(text="Помоги с идеями"), KeyboardButton(text="Напиши статью")]
    ],
    resize_keyboard=True
)

async def ask_gpt(messages: List[Dict[str, Any]], api_keys: List[str]):
    for idx, key in enumerate(api_keys):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {"model": "gpt-3.5-turbo", "messages": messages}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    elif response.status in (401, 403, 429, 500, 502, 503):
                        logging.warning(f"API error ({response.status}) for key {key}. Retrying...")
                        continue
                    else:
                        logging.error(f"Unexpected error {response.status} for key {key}.")
                        break
        except Exception as e:
            logging.error(f"Ошибка запроса к OpenRouter с ключом {key}: {e}")
            continue
    return "❗ *Все API-ключи недоступны. Попробуйте позже.*"

async def clear_user_histories():
    while True:
        await asyncio.sleep(86400)  # 24 часа
        user_histories.clear()
        user_limits.clear()
        user_last_messages.clear()

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

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, *{message.from_user.first_name}*!\n\n"
        "Я — умный помощник на базе *GPT-3.5 Turbo*.\n"
        "Пиши текст или отправляй документ, и я постараюсь ответить!\n\n"
        "_У вас 10 сообщений в сутки._",
        reply_markup=menu_keyboard
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🛠 *Помощь*\n\n"
        "/start — Начать\n"
        "/help — Помощь\n"
        "/reset — Сбросить историю\n"
        "/menu — Меню кнопок\n"
        "/last — Показать последний ответ\n"
    )

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    user_histories.pop(message.from_user.id, None)
    user_last_messages.pop(message.from_user.id, None)
    await message.answer("✅ *История очищена!*")

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("📋 Выберите действие:", reply_markup=menu_keyboard)

@dp.message(Command("last"))
async def cmd_last(message: Message):
    last_msg = user_last_messages.get(message.from_user.id)
    if last_msg:
        await message.answer(f"📝 *Последний ответ:*\n\n{last_msg}")
    else:
        await message.answer("❗ *Нет последнего ответа.*")

@dp.message(F.text)
async def handle_text(message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    user_id = message.from_user.id
    username = message.from_user.username or ""

    if not await check_limit(user_id, username):
        await message.answer("⛔ *Достигнут лимит 10 сообщений в сутки.*")
        return

    user_histories[user_id].append({"role": "user", "content": message.text})
    response = await ask_gpt(user_histories[user_id], API_KEYS)
    
    if not response:
        response = "❗ *Ответ не получен. Попробуйте ещё раз.*"

    user_histories[user_id].append({"role": "assistant", "content": response})
    user_last_messages[user_id] = response
    await increment_limit(user_id)
    await message.answer(response)

@dp.message(F.document)
async def handle_document(message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    user_id = message.from_user.id
    username = message.from_user.username or ""

    if not await check_limit(user_id, username):
        await message.answer("⛔ *Достигнут лимит 10 сообщений в сутки.*")
        return

    try:
        file = await bot.get_file(message.document.file_id)
        content = await bot.download_file(file.file_path)
        text_content = content.read().decode("utf-8")
    except Exception as e:
        logging.error(f"Ошибка при обработке документа: {e}")
        await message.answer("❗ *Не удалось обработать документ.*")
        return

    user_histories[user_id].append({"role": "user", "content": text_content})
    response = await ask_gpt(user_histories[user_id], API_KEYS)
    
    if not response:
        response = "❗ *Ответ не получен. Попробуйте ещё раз.*"

    user_histories[user_id].append({"role": "assistant", "content": response})
    user_last_messages[user_id] = response
    await increment_limit(user_id)
    await message.answer(response)

@dp.message(F.voice)
async def handle_voice(message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.answer("🎙 *Пока не поддерживаю голосовые сообщения!*")

# Веб-сервер для UptimeRobot
async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

async def main():
    await start_webserver()  # Запуск веб-сервера первым
    asyncio.create_task(clear_user_histories())
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logging.error(f"Ошибка поллинга: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
