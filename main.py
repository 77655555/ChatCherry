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

async def reset_daily_limits():
    """Ежедневный сброс лимитов"""
    while True:
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((midnight - now).total_seconds())
        
        async with data_lock:
            for user_id in list(user_data.keys()):
                if user_data[user_id].get('username') != ADMIN_USERNAME:
                    user_data[user_id]['messages_today'] = 0
        logger.info("Дневные лимиты сообщений сброшены")

async def call_openrouter_api(prompt: str) -> str:
    """Улучшенный вызов API с ротацией ключей"""
    for api_key in API_KEYS:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7
                    },
                    timeout=60
                ) as response:
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
    
    raise APIError("Все API ключи исчерпаны")

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
            status_text = (
                f"📊 Использовано сообщений: {user_info['messages_today']}/{FREE_MESSAGES_PER_DAY}\n"
                f"🔄 Осталось: {remaining}\n"
                "⏳ Сброс лимита через: "
                f"{(datetime.now().replace(hour=23, minute=59, second=59) - datetime.now()).seconds // 3600} ч."
            )
    
    await update.message.reply_text(status_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящих сообщений"""
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text("Ошибка: Не удалось определить пользователя!")
        return

    try:
        # Проверка лимита
        if not await check_user_limit(user.id, user.username):
            await update.message.reply_text(
                f"⚠️ Лимит исчерпан! Сброс через {24 - datetime.now().hour} ч.\n"
                f"Контакт: @{ADMIN_USERNAME}"
            )
            return

        # Индикатор набора сообщения
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action='typing'
        )

        # Обработка запроса
        response = await call_openrouter_api(update.message.text)
        
        # Отправка ответа с учетом ограничений Telegram
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
    logger.error(f"Ошибка в обновлении {update}: {context.error}")
    if update.effective_message:
        await update.effective_message.reply_text("⚠️ Произошла внутренняя ошибка. Повторите попытку.")

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
    application.create_task(reset_daily_limits())
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
