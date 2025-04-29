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

def process_content(content: str) -> str:
    return content.replace("<think>", "").replace("</think>", "").strip()

async def reset_limits(context: ContextTypes.DEFAULT_TYPE):
    async with data_lock:
        for user_id in list(user_data.keys()):
            if user_data[user_id].get("username") != ADMIN_USERNAME:
                user_data[user_id]["messages_today"] = 0
        logger.info("Ежедневный сброс лимитов выполнен")

async def rotate_key() -> str:
    async with data_lock:
        return min(API_KEYS, key=lambda k: (key_usage[k]["count"], key_usage[k]["errors"]))

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
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://github.com/your-repository",
                        "X-Title": "Telegram Bot"
                    },
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7
                    },
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
            logger.error(f"Ошибка API ({attempt+1}/3): {str(e)}")
    
    raise APIError("Все попытки запроса завершились ошибкой")

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Добро пожаловать, {user.first_name}!\n\n"
        f"• {FREE_MESSAGES} бесплатных запросов в день\n"
        f"• Поддержка: @{ADMIN_USERNAME}"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with data_lock:
        if user.username == ADMIN_USERNAME:
            total_requests = sum(v["count"] for v in key_usage.values())
            stats = (
                f"📊 Админ-панель:\n"
                f"👥 Пользователей: {len(user_data)}\n"
                f"📨 Всего запросов: {total_requests}\n"
                f"🔑 Активных ключей: {sum(1 for k in API_KEYS if key_usage[k]['errors'] < 5)}/{len(API_KEYS)}"
            )
        else:
            user_info = user_data.get(user.id, {"messages_today": 0})
            reset_time = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            time_left = reset_time - datetime.now()
            stats = (
                f"📆 Лимиты:\n"
                f"• Использовано: {user_info['messages_today']}/{FREE_MESSAGES}\n"
                f"• Сброс через: {time_left.seconds//3600} ч. {(time_left.seconds%3600)//60} мин."
            )
    
    await update.message.reply_text(stats)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        if not user or not user.username:
            await update.message.reply_text("❌ Ошибка идентификации пользователя")
            return

        if not await check_limit(user.id, user.username):
            reset_time = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            time_left = reset_time - datetime.now()
            await update.message.reply_text(
                f"⚠️ Лимит исчерпан!\n"
                f"Следующий сброс через: {time_left.seconds//3600} ч. {(time_left.seconds%3600)//60} мин.\n"
                f"Контакт: @{ADMIN_USERNAME}"
            )
            return

        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        response = await call_api(update.message.text)
        
        # Разделение длинных сообщений с нумерацией
        chunks = [response[i:i+MAX_LENGTH] for i in range(0, len(response), MAX_LENGTH)]
        for idx, chunk in enumerate(chunks, 1):
            await update.message.reply_text(f"📝 Ответ ({idx}/{len(chunks)}):\n\n{chunk}")

    except RateLimitExceeded:
        await update.message.reply_text("⏳ Превышена частота запросов. Попробуйте через 1-2 минуты.")
    except APIError:
        await update.message.reply_text("🔧 Временные технические неполадки. Пожалуйста, попробуйте позже.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла непредвиденная ошибка. Администратор уведомлен.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(f"Глобальная ошибка: {str(error)}", exc_info=True)
    if update and update.effective_message:
        await update.effective_message.reply_text("⚡ Произошла системная ошибка. Повторите запрос позже.")

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("status", "Проверить статистику"),
    ])
    logger.info("Бот успешно инициализирован")

def main():
    application = ApplicationBuilder() \
        .token(TELEGRAM_TOKEN) \
        .post_init(post_init) \
        .http_version("1.1") \
        .get_updates_http_version("1.1") \
        .build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Планировщик задач
    application.job_queue.run_daily(
        reset_limits,
        time=datetime.strptime("00:00", "%H:%M").time(),
        name="daily_reset"
    )

    # Конфигурация для Render
    if 'RENDER' in os.environ:
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 10000)),
            webhook_url=f"https://{os.environ['RENDER_SERVICE_NAME']}.onrender.com/{TELEGRAM_TOKEN}",
            url_path=TELEGRAM_TOKEN,
            secret_token=os.environ.get('SECRET_TOKEN', 'DEFAULT_SECRET_TOKEN'),
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            cert=None,
            key=None
        )
    else:
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

if __name__ == "__main__":
    main()
