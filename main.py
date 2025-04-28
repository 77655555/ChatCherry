import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ApplicationBuilder,
)
import aiohttp
from urllib.parse import quote

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = "8035488978:AAFMLVN3Ya_E4GYeWrxnKUkrAlGMirSP8gw"
API_KEYS = [
    "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",
    "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",
    "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",
    "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",
    "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",
]
MODEL = "deepseek/deepseek-r1"
ADMIN_USERNAME = "qqq5599"
FREE_MESSAGES = 10
MAX_LENGTH = 4096
REQUEST_TIMEOUT = 60
CACHE_EXPIRATION = timedelta(hours=1)

# Глобальные данные
user_data = {}
response_cache = {}
data_lock = asyncio.Lock()
key_usage = {key: {"count": 0, "errors": 0} for key in API_KEYS}

class APIError(Exception): pass
class RateLimitExceeded(Exception): pass

# Функции обработки
def process_content(content: str) -> str:
    return content.replace("<think>", "").replace("</think>", "").strip()

async def reset_limits(context: ContextTypes.DEFAULT_TYPE):
    async with data_lock:
        for user_id in list(user_data.keys()):
            if user_data[user_id].get("username") != ADMIN_USERNAME:
                user_data[user_id]["messages_today"] = 0
        logger.info("Daily limits reset")

async def rotate_key() -> str:
    async with data_lock:
        return min(API_KEYS, key=lambda k: key_usage[k]["count"])

async def call_api(prompt: str) -> str:
    cache_key = quote(prompt.lower())
    async with data_lock:
        cached = response_cache.get(cache_key)
        if cached and datetime.now() - cached["timestamp"] < CACHE_EXPIRATION:
            return cached["response"]

    for attempt in range(3):
        api_key = await rotate_key()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}]},
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                ) as response:
                    result = await response.json()
                    
                    async with data_lock:
                        key_usage[api_key]["count"] += 1

                    if response.status == 429:
                        raise RateLimitExceeded()
                    if response.status != 200:
                        continue

                    content = process_content(result["choices"][0]["message"]["content"])
                    async with data_lock:
                        response_cache[cache_key] = {
                            "response": content,
                            "timestamp": datetime.now()
                        }
                    return content
        except Exception as e:
            async with data_lock:
                key_usage[api_key]["errors"] += 1
            await asyncio.sleep(2 ** attempt)
    
    raise APIError("All API attempts failed")

async def check_limit(user_id: int, username: str) -> bool:
    async with data_lock:
        if username == ADMIN_USERNAME:
            return True

        if user_id not in user_data:
            user_data[user_id] = {
                "messages_today": 0,
                "username": username,
                "first_seen": datetime.now()
            }

        if user_data[user_id]["messages_today"] >= FREE_MESSAGES:
            return False

        user_data[user_id]["messages_today"] += 1
        return True

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"🔹 Бесплатно: {FREE_MESSAGES} запросов/день\n"
        f"🔹 Поддержка: @{ADMIN_USERNAME}"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with data_lock:
        if user.username == ADMIN_USERNAME:
            stats = (
                f"👤 Пользователей: {len(user_data)}\n"
                f"🔑 Запросов: {sum(v['count'] for v in key_usage.values())}"
            )
        else:
            info = user_data.get(user.id, {"messages_today": 0})
            reset_time = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
            time_left = reset_time - datetime.now()
            stats = (
                f"✉️ Использовано: {info['messages_today']}/{FREE_MESSAGES}\n"
                f"⏳ Сброс через: {time_left.seconds//3600} ч. {(time_left.seconds%3600)//60} мин."
            )
    
    await update.message.reply_text(stats)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        if not await check_limit(user.id, user.username):
            await update.message.reply_text("⚠️ Лимит исчерпан!")
            return

        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        response = await call_api(update.message.text)
        
        for i in range(0, len(response), MAX_LENGTH):
            await update.message.reply_text(response[i:i+MAX_LENGTH])

    except RateLimitExceeded:
        await update.message.reply_text("🚧 Слишком много запросов")
    except APIError:
        await update.message.reply_text("🔧 Технические неполадки")
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка обработки")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=True)
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ Произошла ошибка")

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Начало работы"),
        BotCommand("status", "Статистика"),
    ])

# Основная конфигурация
def setup_handlers(application: Application):
    handlers = [
        CommandHandler("start", start),
        CommandHandler("status", status),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
    ]
    for handler in handlers:
        application.add_handler(handler)

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    setup_handlers(application)
    application.add_error_handler(error_handler)
    application.job_queue.run_daily(reset_limits, time=datetime.strptime("00:00", "%H:%M").time())

    if 'RENDER' in os.environ:
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 10000)),
            webhook_url=f"https://{os.environ['RENDER_SERVICE_NAME']}.onrender.com/{TELEGRAM_TOKEN}",
            url_path=TELEGRAM_TOKEN,
            secret_token=os.environ.get('SECRET_TOKEN', 'DEFAULT'),
            drop_pending_updates=True
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
