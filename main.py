import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурационные параметры
TELEGRAM_TOKEN = "8035488978:AAFMLVN3Ya_E4GYeWrxnKUkrAlGMirSP8gw"
API_KEYS = [
    "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",
    "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",
    "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",
    "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",
    "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"
]
MODEL = "deepseek/deepseek-r1"
ADMIN_USERNAME = "qqq5599"
FREE_MESSAGES_PER_DAY = 10
MAX_MESSAGE_LENGTH = 4096

# Глобальные переменные с блокировкой
user_data = {}
data_lock = asyncio.Lock()

class APIError(Exception):
    pass

def process_content(content: str) -> str:
    """Очистка контента от служебных тегов"""
    return content.replace('<think>', '').replace('</think>', '').strip()

async def reset_daily_limits(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный сброс лимитов"""
    try:
        async with data_lock:
            logger.info("Начало сброса дневных лимитов...")
            
            for user_id in list(user_data.keys()):
                if user_data[user_id].get('username') != ADMIN_USERNAME:
                    user_data[user_id]['messages_today'] = 0
            
            logger.info("Дневные лимиты успешно сброшены")
            
    except Exception as e:
        logger.error(f"Ошибка при сбросе лимитов: {str(e)}")

async def call_openrouter_api(prompt: str) -> str:
    """Улучшенный вызов API с ротацией ключей"""
    for api_key in API_KEYS:
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
                    timeout=60
                ) as response:
                    if response.status == 401:
                        logger.error(f"Неверный API ключ: {api_key[:8]}...")
                        continue
                    
                    if response.status != 200:
                        error = await response.json()
                        logger.error(f"Ошибка API {response.status}: {error.get('error', {})}")
                        continue
                    
                    result = await response.json()
                    return process_content(result['choices'][0]['message']['content'])
                    
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            continue
        except json.JSONDecodeError:
            logger.error("Неверный формат ответа API")
            continue
    
    raise APIError("Все API ключи недействительны или сервис недоступен")

async def check_user_limit(user_id: int, username: str) -> bool:
    """Потокобезопасная проверка лимитов"""
    async with data_lock:
        if username == ADMIN_USERNAME:
            return True

        if user_id not in user_data:
            user_data[user_id] = {
                'messages_today': 0,
                'username': username
            }
        
        if user_data[user_id]['messages_today'] >= FREE_MESSAGES_PER_DAY:
            return False
        
        user_data[user_id]['messages_today'] += 1
        return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    welcome_message = (
        "👋 Привет! Я DeepSeek R1 бот.\n\n"
        "Я могу ответить на твои вопросы и помочь с различными задачами.\n\n"
        f"🔹 У обычных пользователей есть {FREE_MESSAGES_PER_DAY} бесплатных запросов в день.\n"
        f"🔹 Администратор @{ADMIN_USERNAME} имеет неограниченный доступ.\n\n"
        "Просто напиши свой вопрос, и я отвечу!"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /help"""
    help_text = (
        "🤖 Команды бота:\n\n"
        "/start - Начать общение с ботом\n"
        "/help - Показать эту справку\n"
        "/status - Проверить статус аккаунта\n\n"
        f"Лимиты: {FREE_MESSAGES_PER_DAY} сообщений/день\n"
        f"Админ: @{ADMIN_USERNAME}"
    )
    await update.message.reply_text(help_text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /status"""
    user = update.effective_user
    async with data_lock:
        if user.username == ADMIN_USERNAME:
            status_text = "🔰 Статус: Администратор (безлимитный доступ)"
        else:
            user_info = user_data.get(user.id, {'messages_today': 0})
            remaining = max(0, FREE_MESSAGES_PER_DAY - user_info['messages_today'])
            current_time = datetime.now()
            reset_time = current_time.replace(hour=23, minute=59, second=59)
            hours_left = (reset_time - current_time).seconds // 3600
            
            status_text = (
                f"📊 Использовано сообщений: {user_info['messages_today']}/{FREE_MESSAGES_PER_DAY}\n"
                f"🔄 Осталось: {remaining}\n"
                f"⏳ Сброс лимита через: {hours_left} ч."
            )
    
    await update.message.reply_text(status_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящих сообщений"""
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text("Ошибка: Не удалось определить пользователя!")
        return

    try:
        if not await check_user_limit(user.id, user.username):
            current_hour = datetime.now().hour
            await update.message.reply_text(
                f"⚠️ Лимит исчерпан! Сброс через {24 - current_hour} ч.\n"
                f"Контакт: @{ADMIN_USERNAME}"
            )
            return

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action='typing'
        )

        response = await call_openrouter_api(update.message.text)
        
        for i in range(0, len(response), MAX_MESSAGE_LENGTH):
            await update.message.reply_text(response[i:i+MAX_MESSAGE_LENGTH])
            
    except APIError as e:
        logger.error(f"API Error: {str(e)}")
        await update.message.reply_text("🚧 Сервис временно недоступен. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await update.message.reply_text("❌ Произошла ошибка при обработке запроса.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    try:
        if update and update.effective_message:
            logger.error(f"Ошибка в обновлении {update.update_id}: {context.error}")
            await update.effective_message.reply_text("⚠️ Произошла внутренняя ошибка. Повторите попытку.")
        else:
            logger.error(f"Ошибка без обновления: {context.error}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {str(e)}")

def main():
    """Инициализация и запуск бота"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков
    handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("status", status),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    application.add_error_handler(error_handler)
    
    # Планирование ежедневного сброса в 00:00
    application.job_queue.run_daily(
        reset_daily_limits,
        time=datetime.strptime("00:00", "%H:%M").time(),
        days=(0, 1, 2, 3, 4, 5, 6)
    )
    
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
