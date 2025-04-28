import os
import logging
import aiohttp
import asyncio
import aiohttp.web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode, ChatAction, ContentType
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile, InputFile
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import List, Dict, Any
from functools import lru_cache
import random
import tempfile
import json
import base64
import googletrans
from googletrans import LANGUAGES

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEYS = os.getenv("OPENROUTER_API_KEYS").split(',')  # Обработка нескольких ключей
OWNER_USERNAME = "qqq5599"
OWNER_ID = int(os.getenv("OWNER_ID", "9995599"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", None)
DAILY_LIMIT = 15

MODELS = ["openrouter/gpt-4", "openrouter/gpt-3.5-turbo", "openrouter/gpt-3.5-turbo-16k"]

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher()

# --- ХРАНИЛИЩА ---
user_histories = defaultdict(lambda: deque(maxlen=100))
user_limits = defaultdict(lambda: {"count": 0, "reset": datetime.utcnow()})
user_last_ts = defaultdict(lambda: datetime.min)
user_stats = defaultdict(lambda: {"requests": 0, "last_active": None})
user_ratings = defaultdict(int)
user_langs = defaultdict(lambda: 'ru')
model_index = 0

# --- КЛАВИАТУРА ---
menu_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Анекдот"), KeyboardButton(text="Мотивация")],
    [KeyboardButton(text="Идеи"), KeyboardButton(text="Статья")],
    [KeyboardButton(text="Статистика"), KeyboardButton(text="Помощь")],
    [KeyboardButton(text="Голосовое"), KeyboardButton(text="Документ")]
], resize_keyboard=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_next_model() -> str:
    global model_index
    model_index = (model_index + 1) % len(MODELS)
    return MODELS[model_index]

# Выбираем ключ для API
def get_next_api_key() -> str:
    global OPENROUTER_API_KEYS
    key_index = random.randint(0, len(OPENROUTER_API_KEYS) - 1)  # Выбор случайного ключа
    return OPENROUTER_API_KEYS[key_index]

async def ask_model(messages: List[Dict[str, Any]]) -> str:
    global model_index
    for _ in range(len(MODELS)):
        model = MODELS[model_index]
        headers = {
            "Authorization": f"Bearer {get_next_api_key()}",  # Используем случайный ключ
            "HTTP-Referer": "https://yourdomain.com/",
            "X-Title": "YourBotTitle"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 300,
        }
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        logging.warning(f"Ошибка запроса: {await resp.text()}")
        except Exception as e:
            logging.error(f"Ошибка модели {model}: {e}")
            await notify_admin(f"Ошибка {model}: {e}")
        get_next_model()
    return "⚠️ Все модели заняты. Попробуйте позже."

def too_fast(user_id: int) -> bool:
    now = datetime.utcnow()
    if (now - user_last_ts[user_id]).total_seconds() < 2:
        return True
    user_last_ts[user_id] = now
    return False

@lru_cache(maxsize=512)
def cached_query(q: str) -> str:
    return ""

async def text_to_speech(text: str) -> FSInputFile:
    from gtts import gTTS
    tts = gTTS(text=text, lang="ru")
    filename = tempfile.mktemp(suffix=".mp3")
    tts.save(filename)
    return FSInputFile(filename)

async def gen_image(prompt: str) -> str:
    encoded = base64.urlsafe_b64encode(prompt.encode()).decode()
    return f"https://dummyimage.com/600x400/000/fff.png&text={encoded}"

async def notify_admin(text: str):
    try:
        await bot.send_message(OWNER_ID, f"⚠️ {text}")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления владельцу: {e}")

SUPPORTED_LANGS = ['ru', 'en']

async def translate_text(text: str, dest_lang: str) -> str:
    try:
        translator = googletrans.Translator()
        translated = translator.translate(text, dest=dest_lang)
        return translated.text
    except Exception as e:
        logging.error(f"Ошибка перевода: {e}")
        return "⚠️ Не удалось перевести текст."

# --- БЭКАПЫ ---
async def save_history():
    with open("backup_histories.json", "w", encoding="utf-8") as f:
        json.dump({str(uid): list(hist) for uid, hist in user_histories.items()}, f, ensure_ascii=False, indent=2)

async def load_history():
    if os.path.exists("backup_histories.json"):
        with open("backup_histories.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            for uid, hist in data.items():
                user_histories[int(uid)] = deque(hist, maxlen=100)

# --- АВТОЧИСТКА ---
async def daily_reset():
    while True:
        await asyncio.sleep(3600)
        now = datetime.utcnow()
        for u, lim in list(user_limits.items()):
            if now - lim["reset"] > timedelta(days=1):
                lim["count"] = 0
                lim["reset"] = now
                user_histories[u].clear()
        await save_history()

async def clean_inactive():
    while True:
        await asyncio.sleep(86400)
        cutoff = datetime.utcnow() - timedelta(days=30)
        for u, stat in list(user_stats.items()):
            if stat["last_active"] and stat["last_active"] < cutoff:
                user_histories.pop(u, None)
                user_stats.pop(u, None)
                user_limits.pop(u, None)

# --- ОБРАБОТКА КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer("👋 Привет! Выберите действие:", reply_markup=menu_kb)

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer("/start /help /stats /lang /backup /calc /webhook")

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    stat = user_stats[m.from_user.id]
    await m.answer(f"Запросов: {stat['requests']}\nАктивность: {stat['last_active']}")

@dp.message(Command("lang"))
async def set_lang(m: Message):
    parts = m.text.split()
    if len(parts) >= 2 and parts[1] in SUPPORTED_LANGS:
        user_langs[m.from_user.id] = parts[1]
        await m.answer(f"Язык установлен: {parts[1]}")
    else:
        await m.answer("Используйте: /lang ru или /lang en")

@dp.message(Command("backup"))
async def manual_backup(m: Message):
    await save_history()
    await m.answer("✅ Бэкап истории сохранён.")

@dp.message(Command("webhook"))
async def cmd_webhook(m: Message):
    if not WEBHOOK_URL:
        return await m.answer("❌ В переменных окружения не задан WEBHOOK_URL.")
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    await m.answer("Webhook установлен успешно.")

@dp.message(Command("calc"))
async def calc(m: Message):
    expr = m.text.partition(" ")[2]
    try:
        if not expr:
            raise ValueError("Пустое выражение.")
        val = eval(expr, {"__builtins__": {}})
        await m.answer(f"`= {val}`")
    except Exception as e:
        await m.answer(f"⚠️ Ошибка вычисления: {e}")

# --- ОБРАБОТКА ТЕКСТА И ФАЙЛОВ ---
@dp.message(F.text & ~F.command)
async def handle_text(m: Message):
    uid = m.from_user.id
    uname = m.from_user.username or ""

    if too_fast(uid):
        return await m.answer("⚠️ Пожалуйста, подождите пару секунд.")

    if uname != OWNER_USERNAME and user_limits[uid]["count"] >= DAILY_LIMIT:
        return await m.answer("⛔ Достигнут дневной лимит.")

    user_histories[uid].append({"role": "user", "content": m.text})
    user_limits[uid]["count"] += 1
    user_stats[uid]["requests"] += 1
    user_stats[uid]["last_active"] = datetime.utcnow()

    await bot.send_chat_action(uid, ChatAction.TYPING)

    response_text = cached_query(m.text) or await ask_model(list(user_histories[uid]))

    if user_langs[uid] != 'ru':
        response_text = await translate_text(response_text, user_langs[uid])

    user_histories[uid].append({"role": "assistant", "content": response_text})

    await m.answer(response_text)

@dp.message(F.voice)
async def handle_voice(m: Message):
    await m.answer("Голосовые пока не поддерживаются. Пожалуйста, отправьте текст.")

@dp.message(F.document)
async def handle_doc(m: Message):
    await m.answer("Документы пока не обрабатываются. Пожалуйста, отправьте текст.")

# --- СЕРВЕР И UPTIME ---
async def uptime(req):
    return aiohttp.web.Response(text="Bot is alive!")

async def main():
    await load_history()
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(daily_reset())
    asyncio.create_task(clean_inactive())

    app = aiohttp.web.Application()
    app.router.add_get("/", uptime)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner, "0.0.0.0", 8080).start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
