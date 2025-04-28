import os
import logging
import aiohttp
import asyncio
import aiohttp.web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import List, Dict, Any
from functools import lru_cache
import random
import tempfile

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()
BOT_TOKEN       = os.getenv("BOT_TOKEN")
IO_NET_API_KEY  = os.getenv("IO_NET_API_KEY")
OWNER_USERNAME  = "qqq5599"
OWNER_ID        = int(os.getenv("OWNER_ID", "9995599"))
WEBHOOK_URL     = os.getenv("WEBHOOK_URL", None)
DAILY_LIMIT     = 10

MODELS = [
    "Llama-4-Maverick-17B-128E-Instruct-FP8", "QwQ-32B", "DeepSeek-R1",
    # ...
]

# --- ЛОГИРОВАНИЕ И ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
dp  = Dispatcher()

# --- ХРАНИЛИЩА ---
user_histories  = defaultdict(lambda: deque(maxlen=50))
user_limits     = defaultdict(lambda: {"count": 0, "reset": datetime.utcnow()})
user_last_ts    = defaultdict(lambda: datetime.min)
user_stats      = defaultdict(lambda: {"requests": 0, "last_active": None})
user_ratings    = defaultdict(int)
user_langs      = defaultdict(lambda: 'ru')
model_index     = 0

# --- КЛАВИАТУРА ---
menu_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Анекдот"), KeyboardButton(text="Мотивация")],
    [KeyboardButton(text="Идеи"), KeyboardButton(text="Статья")],
    [KeyboardButton(text="Статистика"), KeyboardButton(text="Помощь")]
], resize_keyboard=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_next_model() -> str:
    global model_index
    model_index = (model_index + 1) % len(MODELS)
    return MODELS[model_index]

async def ask_model(messages: List[Dict[str, Any]]) -> str:
    global model_index
    for _ in range(len(MODELS)):
        model = MODELS[model_index]
        headers = {"Authorization": f"Bearer {IO_NET_API_KEY}"}
        payload = {"model": model, "messages": messages}
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    "https://io.net/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception as e:
            logging.warning(f"Ошибка модели {model}: {e}")
        get_next_model()
    return "⚠️ Ошибка генерации ответа."

def too_fast(user_id: int) -> bool:
    now = datetime.utcnow()
    if (now - user_last_ts[user_id]).total_seconds() < 2:
        return True
    user_last_ts[user_id] = now
    return False

@lru_cache(maxsize=256)
def cached_query(q: str) -> str:
    return ""

async def text_to_speech(text: str) -> FSInputFile:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
        f.write(b"OggS")
        return FSInputFile(f.name)

async def gen_image(prompt: str) -> str:
    return f"https://via.placeholder.com/300x200.png?text={prompt.replace(' ', '+')}"

async def notify_admin(text: str):
    await bot.send_message(OWNER_ID, f"⚠️ {text}")

# --- НОВЫЕ ФУНКЦИИ ---
SUPPORTED_LANGS = ['ru', 'en']

@dp.message(Command("lang"))
async def set_lang(m: Message):
    parts = m.text.split()
    if len(parts) >= 2 and parts[1] in SUPPORTED_LANGS:
        user_langs[m.from_user.id] = parts[1]
        await m.answer(f"Язык установлен: {parts[1]}")
    else:
        await m.answer("Используйте: /lang [ru|en]")

@dp.message(Command("backup"))
async def manual_backup(m: Message):
    await m.answer("✅ История (символически) сохранена.")

@dp.message(Command("webhook"))
async def cmd_webhook(m: Message):
    if not WEBHOOK_URL:
        return await m.answer("❌ WEBHOOK_URL не задан в переменных окружения.")
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    await m.answer("Webhook успешно установлен.")

@dp.message(Command("calc"))
async def calc(m: Message):
    expr = m.text.partition(" ")[2]
    try:
        val = eval(expr, {"__builtins__": {}})
        await m.answer(f"`= {val}`")
    except Exception as e:
        await m.answer(f"⚠️ Ошибка: {e}")

@dp.message(F.text.startswith("Оценка"))
async def rate_response(m: Message):
    try:
        score = int(m.text.split()[1])
        if 1 <= score <= 5:
            user_ratings[m.from_user.id] += score
            await m.answer("Спасибо за вашу оценку!")
        else:
            await m.answer("Оценка от 1 до 5.")
    except Exception:
        await m.answer("Используйте: Оценка [1-5]")

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

async def clean_inactive():
    while True:
        await asyncio.sleep(86400)
        cutoff = datetime.utcnow() - timedelta(days=30)
        for u, stat in list(user_stats.items()):
            if stat["last_active"] and stat["last_active"] < cutoff:
                user_histories.pop(u, None)
                user_stats.pop(u, None)
                user_limits.pop(u, None)

# --- ОБРАБОТКА ---
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer("👋 Привет! Вот меню ⬇️", reply_markup=menu_kb)

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer("/start /help /stats /lang /backup /calc /webhook")

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    stat = user_stats[m.from_user.id]
    await m.answer(f"Запросов: {stat['requests']}\nАктивность: {stat['last_active']}")

@dp.message(F.text & ~F.command)
async def handle_text(m: Message):
    uid = m.from_user.id
    uname = m.from_user.username or ""

    if too_fast(uid):
        return await m.answer("⚠️ Пожалуйста, подождите 2 секунды.")

    if uname != OWNER_USERNAME and user_limits[uid]["count"] >= DAILY_LIMIT:
        return await m.answer("⛔ Дневной лимит запросов исчерпан.")

    user_histories[uid].append({"role": "user", "content": m.text})
    user_limits[uid]["count"] += 1
    user_stats[uid]["requests"] += 1
    user_stats[uid]["last_active"] = datetime.utcnow()

    await bot.send_chat_action(uid, ChatAction.TYPING)

    response_text = cached_query(m.text)
    if not response_text:
        response_text = await ask_model(list(user_histories[uid]))

    user_histories[uid].append({"role": "assistant", "content": response_text})

    await m.answer(response_text)

# --- UPTIME И СЕРВЕР ---
async def uptime(req):
    return aiohttp.web.Response(text="OK")

async def main():
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
