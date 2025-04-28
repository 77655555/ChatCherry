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

# Конфигурационные параметры
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
FREE_MESSAGES_PER_DAY = 10
MAX_MESSAGE_LENGTH = 4096
REQUEST_TIMEOUT = 60
CACHE_EXPIRATION = timedelta(hours=1)

# Глобальные структуры данных
user_data = {}
response_cache = {}
data_lock = asyncio.Lock()
key_usage = {key: {"count": 0, "errors": 0} for key in API_KEYS}

class APIError(Exception):
    pass

class RateLimitExceeded(Exception):
    pass

def process_content(content: str) -> str:
    return content.replace("<think>", "").replace("</think>", "").strip()

async def reset_daily_limits(context: ContextTypes.DEFAULT_TYPE):
    async with data_lock:
        logger.info("Resetting daily limits...")
        for user_id in list(user_data.keys()):
            if user_data[user_id].get("username") != ADMIN_USERNAME:
                user_data[user_id]["messages_today"] = 0
        logger.info("Daily limits reset complete")

async def rotate_api_key() -> str:
    async with data_lock:
        return min(API_KEYS, key=lambda k: key_usage[k]["count"])

async def call_openrouter_api(prompt: str) -> str:
    cache_key = quote(prompt.lower())
    async with data_lock:
        if cache_key in response_cache:
            if datetime.now() - response_cache[cache_key]["timestamp"] < CACHE_EXPIRATION:
                return response_cache[cache_key]["response"]

    for attempt in range(3):
        api_key = await rotate_api_key()
        try:
            async with aiohttp.ClientSession() as session:
                start_time = datetime.now()
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://github.com/your-repository",
                        "X-Title": "Telegram Bot",
                    },
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                    },
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                ) as response:
                    response_text = await response.text()
                    result = json.loads(response_text)

                    async with data_lock:
                        key_usage[api_key]["count"] += 1

                    if response.status == 429:
                        raise RateLimitExceeded()
                    if response.status != 200:
                        logger.error(f"API Error {response.status}: {result.get('error', {})}")
                        continue

                    content = process_content(result["choices"][0]["message"]["content"])
                    async with data_lock:
                        response_cache[cache_key] = {
                            "response": content,
                            "timestamp": datetime.now(),
                        }
                    return content
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            async with data_lock:
                key_usage[api_key]["errors"] += 1
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            await asyncio.sleep(2 ** attempt)

    raise APIError("All API attempts failed")

async def check_user_limit(user_id: int, username: str) -> bool:
    async with data_lock:
        if username == ADMIN_USERNAME:
            return True

        if user_id not in user_data:
            user_data[user_id] = {
                "messages_today": 0,
                "username": username,
                "first_seen": datetime.now(),
            }

        if user_data[user_id]["messages_today"] >= FREE_MESSAGES_PER_DAY:
            return False

        user_data[user_id]["messages_today"] += 1
        return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я интеллектуальный ассистент на базе DeepSeek R1.\n\n"
        f"🔹 Бесплатно: {FREE_MESSAGES_PER_DAY} запросов/день\n"
        f"🔹 Поддержка: @{ADMIN_USERNAME}\n\n"
        "Просто задай свой вопрос!"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 Доступные команды:\n\n"
        "/start - Начало работы\n"
        "/help - Эта справка\n"
        "/status - Ваша статистика\n"
        "/feedback - Оставить отзыв\n\n"
        f"Администратор: @{ADMIN_USERNAME}"
    )
    await update.message.reply_text(help_text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with data_lock:
        if user.username == ADMIN_USERNAME:
            total_users = len(user_data)
            active_users = sum(1 for u in user_data.values() if u["messages_today"] > 0)
            status_text = (
                "⚙️ Админ-статистика:\n"
                f"👤 Пользователей: {total_users}\n"
                f"🔢 Активных: {active_users}\n"
                f"🔑 Использовано ключей: {sum(v['count'] for v in key_usage.values())}"
            )
        else:
            user_info = user_data.get(user.id, {"messages_today": 0})
            remaining = max(0, FREE_MESSAGES_PER_DAY - user_info["messages_today"])
            reset_time = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
            time_left = reset_time - datetime.now()

            status_text = (
                "📊 Ваша статистика:\n"
                f"✉️ Использовано: {user_info['messages_today']}/{FREE_MESSAGES_PER_DAY}\n"
                f"🔄 Осталось: {remaining}\n"
                f"⏳ Сброс через: {time_left.seconds // 3600} ч. {(time_left.seconds % 3600) // 60} мин."
            )
    
    await update.message.reply_text(status_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        if not await check_user_limit(user.id, user.username):
            await update.message.reply_text(
                "⚠️ Дневной лимит исчерпан!\n"
                f"Сброс через {24 - datetime.now().hour} часов\n"
                f"Контакт: @{ADMIN_USERNAME}"
            )
            return

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        response = await call_openrouter_api(update.message.text)
        
        # Отправка ответа частями с индикатором прогресса
        message_parts = [response[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(response), MAX_MESSAGE_LENGTH)]
        for i, part in enumerate(message_parts):
            await update.message.reply_text(
                f"📝 Ответ ({i+1}/{len(message_parts)}):\n\n{part}"
            )

    except RateLimitExceeded:
        await update.message.reply_text("🚧 Превышена скорость запросов. Попробуйте через минуту.")
    except APIError as e:
        logger.error(f"API Error: {str(e)}")
        await update.message.reply_text("🔧 Временные технические неполадки. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла непредвиденная ошибка.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(f"Error: {str(error)}", exc_info=True)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Произошла ошибка при обработке запроса. Разработчик уже уведомлен."
        )

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Помощь"),
        BotCommand("status", "Статистика"),
    ])

def setup_handlers(application: Application):
    handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("status", status),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
    ]
    for handler in handlers:
        application.add_handler(handler)

def main():
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    setup_handlers(application)
    application.add_error_handler(error_handler)

    # Планировщик задач
    job_queue = application.job_queue
    job_queue.run_daily(reset_daily_limits, time=datetime.strptime("00:00", "%H:%M").time())

    # Конфигурация для Render
    if 'RENDER' in os.environ:
        PORT = int(os.environ.get('PORT', 10000))
        WEBHOOK_URL = f"https://{os.environ['RENDER_SERVICE_NAME']}.onrender.com/{TELEGRAM_TOKEN}"
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            url_path=TELEGRAM_TOKEN,
            secret_token=os.environ.get('SECRET_TOKEN', 'DEFAULT_SECRET'),
        )
    else:
        application.run_polling(
            drop_pending_updates=True,
            close_loop=False,
            allowed_updates=Update.ALL_TYPES,
        )

if __name__ == "__main__":
    main()
