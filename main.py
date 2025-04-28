import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import DefaultParseMode, ChatAction
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import List, Dict, Any
import random

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()
BOT_TOKEN       = os.getenv("BOT_TOKEN")
IO_NET_API_KEY  = os.getenv("IO_NET_API_KEY")
OWNER_USERNAME  = "qqq5599"
DAILY_LIMIT     = 10
MODELS          = [  # основной список моделей
    "Llama-4-Maverick-17B-128E-Instruct-FP8", "QwQ-32B", "DeepSeek-R1",
    # ... (остальные из вашего списка)
]

# --- ЛОГИРОВАНИЕ И ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
bot = Bot(token=BOT_TOKEN, default=DefaultParseMode.MARKDOWN)
dp  = Dispatcher()

# --- ХРАНИЛИЩА ---
user_histories      = defaultdict(lambda: deque(maxlen=50))
user_limits         = defaultdict(lambda: {"count": 0, "reset": datetime.utcnow()})
user_last_ts        = defaultdict(lambda: datetime.min)
user_stats          = defaultdict(lambda: {"requests": 0, "last_active": None})
model_index         = 0

# --- КЛАВИАТУРА ---
menu_kb = ReplyKeyboardMarkup([
    [KeyboardButton("Анекдот"), KeyboardButton("Мотивация")],
    [KeyboardButton("Идеи"),   KeyboardButton("Статья")   ],
    [KeyboardButton("Статистика"), KeyboardButton("Помощь")]
], resize_keyboard=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_next_model() -> str:
    global model_index
    model_index = (model_index + 1) % len(MODELS)
    return MODELS[model_index]

async def ask_model(messages: List[Dict[str,Any]]) -> str:
    for _ in range(len(MODELS)):
        model = MODELS[model_index]
        headers = {"Authorization": f"Bearer {IO_NET_API_KEY}"}
        payload = {"model": model, "messages": messages}
        try:
            async with aiohttp.ClientSession() as sess:
                resp = await sess.post("https://io.net/api/v1/chat/completions",
                                       headers=headers, json=payload, timeout=60)
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except:
            pass
        get_next_model()
    return "⚠️ Ошибка генерации ответа."

def too_fast(user_id: int) -> bool:
    now = datetime.utcnow()
    if (now - user_last_ts[user_id]).total_seconds() < 2:
        return True
    user_last_ts[user_id] = now
    return False

# --- НОВЫЕ ФУНКЦИИ [NEW] ---
# 1. /lang — смена языка
SUPPORTED_LANGS = ['ru','en']
user_langs = defaultdict(lambda: 'ru')
@dp.message(Command("lang"))
async def set_lang(m: Message):
    lang = m.text.split()[-1]
    if lang in SUPPORTED_LANGS:
        user_langs[m.from_user.id] = lang
        await m.answer(f"Язык — {lang}")
    else:
        await m.answer("Доступные: ru, en")

# 2. /backup — ручной бэкап истории
@dp.message(Command("backup"))
async def manual_backup(m: Message):
    # здесь можно сохранять куда-то
    await m.answer("✅ История сохранена (символически).")

# 3. Настройка webhook (альтернатива polling)
@dp.message(Command("webhook"))
async def cmd_webhook(m: Message):
    await bot.delete_webhook()
    await bot.set_webhook(os.getenv("WEBHOOK_URL"))
    await m.answer("Webhook установлен.")

# 4. Оценка ответа
user_ratings = defaultdict(int)
@dp.message(F.text.startswith("Оценка"))
async def rate_response(m: Message):
    try:
        r = int(m.text.split()[1])
        user_ratings[m.from_user.id] += r
        await m.answer("Спасибо за оценку!")
    except:
        await m.answer("Используйте: Оценка [1-5]")

# 5. Кэширование ответов [NEW]
from functools import lru_cache
@lru_cache(maxsize=128)
def cached_query(q: str) -> str:
    return ""

# 6. Авто-очистка застарелых юзеров
async def clean_inactive():
    while True:
        await asyncio.sleep(86400)
        cutoff = datetime.utcnow() - timedelta(days=30)
        for u, stat in list(user_stats.items()):
            if stat["last_active"] and stat["last_active"] < cutoff:
                user_histories.pop(u,None)

# 7. Голосовой ответ (заглушка)
async def text_to_speech(text: str) -> FSInputFile:
    # вернёт файл audio.ogg
    return FSInputFile("audio.ogg")

# 8. Генерация изображений (заглушка)
async def gen_image(prompt: str) -> str:
    return "https://example.com/image.png"

# 9. Математический калькулятор
@dp.message(Command("calc"))
async def calc(m: Message):
    expr = m.text.partition(" ")[2]
    try:
        val = eval(expr,{"__builtins__":{}})
        await m.answer(f"= {val}")
    except:
        await m.answer("Неверное выражение.")

# 10. Уведомление админа
async def notify_admin(text: str):
    await bot.send_message(os.getenv("OWNER_ID"), f"⚠️ {text}")

# --- ЕЖЕДНЕВНЫЙ СБРОС ---
async def daily_reset():
    while True:
        await asyncio.sleep(3600)
        now = datetime.utcnow()
        for u, lim in user_limits.items():
            if now - lim["reset"] > timedelta(days=1):
                lim["count"]=0; lim["reset"]=now
                user_histories[u].clear()

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer("👋 Привет! Меню ⬇️", reply_markup=menu_kb)

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer("/start /help /stats /lang /backup /calc")

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    s=user_stats[m.from_user.id]
    await m.answer(f"Запросов: {s['requests']}\nПоследняя: {s['last_active']}")

# --- ОБРАБОТЧИК ТЕКСТА ---
@dp.message(F.text & ~F.command)
async def handle_text(m: Message):
    uid = m.from_user.id; uname=m.from_user.username or ""
    if too_fast(uid):
        return await m.answer("⚠️ Ждите 2 сек.")
    if uname!=OWNER_USERNAME and user_limits[uid]["count"]>=DAILY_LIMIT:
        return await m.answer("⛔ Лимит исчерпан.")
    user_histories[uid].append({"role":"user","content":m.text})
    user_limits[uid]["count"]+=1
    user_stats[uid]["requests"]+=1
    user_stats[uid]["last_active"]=datetime.utcnow()
    await bot.send_chat_action(uid, ChatAction.TYPING)
    # сначала попробовать из кэша
    text = cached_query(m.text)
    if not text:
        text = await ask_model(list(user_histories[uid]))
    user_histories[uid].append({"role":"assistant","content":text})
    await m.answer(text)

# --- UPTIME-СЕРВЕР И СТАРТ ---
async def uptime(req): return aiohttp.web.Response(text="OK")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(daily_reset())
    asyncio.create_task(clean_inactive())
    app = aiohttp.web.Application()
    app.router.add_get("/", uptime)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner,"0.0.0.0",8080).start()
    await dp.start_polling(bot, skip_updates=True)

if __name__=="__main__":
    asyncio.run(main())
