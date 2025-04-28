import os
import json
import logging
import asyncio
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен Telegram-бота
TELEGRAM_TOKEN = "8035488978:AAFMLVN3Ya_E4GYeWrxnKUkrAlGMirSP8gw"

# API ключи OpenRouter - будут использоваться последовательно, если один не работает
API_KEYS = [
    "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",
    "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",
    "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",
    "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",
    "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"
]

# Конфигурация модели
MODEL = "deepseek/deepseek-r1"
ADMIN_USERNAME = "qqq5599"  # Имя пользователя администратора без @
FREE_MESSAGES_PER_DAY = 10  # Количество бесплатных сообщений для обычных пользователей

# Хранение пользовательских данных - счетчик сообщений и время сброса
user_data = {}

def process_content(content):
    """Обработка контента путем удаления тегов <think>"""
    return content.replace('<think>', '').replace('</think>', '')

async def reset_daily_limits():
    """Сброс дневных лимитов сообщений в полночь"""
    while True:
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        seconds_until_midnight = (midnight - now).total_seconds()
        
        # Спим до полуночи
        await asyncio.sleep(seconds_until_midnight)
        
        # Сбрасываем лимиты пользователей
        for user_id in user_data:
            if user_id != ADMIN_USERNAME:
                user_data[user_id]['messages_today'] = 0
        
        logger.info("Дневные лимиты сообщений сброшены")

async def call_openrouter_api(prompt, current_key_index=0):
    """Вызов API OpenRouter с запросом, перебор ключей при необходимости"""
    if current_key_index >= len(API_KEYS):
        return "Ошибка: Все API ключи исчерпаны. Пожалуйста, попробуйте позже."
    
    current_key = API_KEYS[current_key_index]
    headers = {
        "Authorization": f"Bearer {current_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False  # Используем non-streaming для простоты в боте
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            ) as response:
                if response.status != 200:
                    logger.error(f"Ошибка API с ключом {current_key_index}: {response.status}")
                    # Пробуем со следующим ключом
                    return await call_openrouter_api(prompt, current_key_index + 1)
                
                response_json = await response.json()
                content = response_json["choices"][0]["message"]["content"]
                return process_content(content)
    except Exception as e:
        logger.error(f"Исключение с ключом {current_key_index}: {str(e)}")
        # Пробуем со следующим ключом
        return await call_openrouter_api(prompt, current_key_index + 1)

async def check_user_limit(user_id, username):
    """Проверка, достиг ли пользователь дневного лимита сообщений"""
    # У администратора неограниченные сообщения
    if username == ADMIN_USERNAME:
        return True
    
    # Инициализируем данные пользователя, если они не существуют
    if user_id not in user_data:
        user_data[user_id] = {
            'messages_today': 0,
            'username': username
        }
    
    # Проверяем, превысил ли пользователь дневной лимит
    if user_data[user_id]['messages_today'] >= FREE_MESSAGES_PER_DAY:
        return False
    
    # Увеличиваем счетчик сообщений
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
        "/status - Проверить статус вашего аккаунта и количество оставшихся сообщений\n\n"
        f"У обычных пользователей есть {FREE_MESSAGES_PER_DAY} бесплатных запросов в день.\n"
        f"Администратор @{ADMIN_USERNAME} имеет неограниченный доступ."
    )
    await update.message.reply_text(help_text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /status"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if username == ADMIN_USERNAME:
        status_text = "🔰 У вас статус администратора с неограниченным доступом."
    else:
        # Инициализируем данные пользователя, если они не существуют
        if user_id not in user_data:
            user_data[user_id] = {
                'messages_today': 0,
                'username': username
            }
        
        messages_used = user_data[user_id]['messages_today']
        messages_left = max(0, FREE_MESSAGES_PER_DAY - messages_used)
        
        status_text = (
            f"📊 Ваш статус:\n\n"
            f"Использовано сообщений сегодня: {messages_used}/{FREE_MESSAGES_PER_DAY}\n"
            f"Осталось сообщений: {messages_left}\n\n"
            "Лимит сбрасывается ежедневно в полночь."
        )
    
    await update.message.reply_text(status_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящих сообщений и генерация ответов"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Проверяем, достиг ли пользователь своего лимита
    has_access = await check_user_limit(user_id, username)
    if not has_access:
        await update.message.reply_text(
            "⚠️ Вы достигли дневного лимита бесплатных сообщений.\n"
            "Лимит сбросится в полночь, или свяжитесь с администратором @" + ADMIN_USERNAME
        )
        return
    
    # Отправляем действие "печатает"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Обрабатываем сообщение
    user_message = update.message.text
    
    try:
        # Получаем ответ от DeepSeek R1
        response = await call_openrouter_api(user_message)
        
        # Отправляем ответ (при необходимости разбиваем на части)
        max_length = 4096  # Лимит размера сообщения в Telegram
        
        if len(response) <= max_length:
            await update.message.reply_text(response)
        else:
            # Разбиваем ответ на части
            chunks = [response[i:i+max_length] for i in range(0, len(response), max_length)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
                
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {str(e)}")
        await update.message.reply_text("Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.")

async def error_handler(update, context):
    """Логирование ошибок, вызванных обновлениями"""
    logger.error(f"Обновление {update} вызвало ошибку {context.error}")

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем задачу сброса дневных лимитов
    application.create_task(reset_daily_limits())
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()
