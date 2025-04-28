import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv
from datetime import datetime
import json
import base64
import random
import googletrans
from googletrans import LANGUAGES
from typing import List, Dict, Any

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_USERNAME = "qqq5599"
OWNER_ID = int(os.getenv("OWNER_ID", "9995599"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", None)

API_KEY = "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"  # Вставьте сюда ваш ключ из https://openrouter.ai/settings/keys
MODEL = "deepseek/deepseek-r1"

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ХРАНИЛИЩА ---
user_histories = {}

# --- КЛАВИАТУРА ---
menu_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Анекдот"), KeyboardButton(text="Мотивация")],
    [KeyboardButton(text="Идеи"), KeyboardButton(text="Статья")],
    [KeyboardButton(text="Статистика"), KeyboardButton(text="Помощь")],
], resize_keyboard=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def process_content(content):
    # Удаляем теги <think> и </think>
    return content.replace('<think>', '').replace('</think>', '')

async def chat_stream(prompt: str, user_id: int) -> str:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data) as response:
            if response.status != 200:
                logging.warning(f"Ошибка API: {response.status}")
                return "⚠️ Ошибка при обработке запроса."
                
            full_response = []
            async for chunk in response.content.iter_any():
                if chunk:
                    chunk_str = chunk.decode('utf-8').replace('data: ', '')
                    try:
                        chunk_json = json.loads(chunk_str)
                        if "choices" in chunk_json:
                            content = chunk_json["choices"][0]["delta"].get("content", "")
                            if content:
                                cleaned = process_content(content)
                                full_response.append(cleaned)
                    except Exception as e:
                        logging.error(f"Ошибка обработки данных: {e}")

            return ''.join(full_response)

# --- ОБРАБОТКА КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer("👋 Привет! Выберите действие:", reply_markup=menu_kb)

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer("/start /help - Для получения помощи")

# --- ОБРАБОТКА ТЕКСТА ---
@dp.message(F.text & ~F.command)
async def handle_text(m: Message):
    uid = m.from_user.id
    user_input = m.text

    if user_input.lower() == 'exit':
        # Завершаем работу, очищаем историю
        if uid in user_histories:
            del user_histories[uid]
        return await m.answer("Завершение работы...")

    # Вставляем историю для пользователя, если её нет
    if uid not in user_histories:
        user_histories[uid] = []

    user_histories[uid].append({"role": "user", "content": user_input})

    await bot.send_chat_action(uid, "typing")
    response_text = await chat_stream(user_input, uid)

    # Сохраняем историю ответа
    user_histories[uid].append({"role": "assistant", "content": response_text})

    await m.answer(response_text)

# --- АВТОМАТИЧЕСКИЕ ФУНКЦИИ --- 
async def notify_admin(text: str):
    try:
        await bot.send_message(OWNER_ID, f"⚠️ {text}")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления владельцу: {e}")

if __name__ == "__main__":
    from aiogram import executor
    # Убедитесь, что бот продолжает работать без ошибок
    executor.start_polling(dp, skip_updates=True)
