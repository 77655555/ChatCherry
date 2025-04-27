# bot.py - Full Telegram Bot with OpenRouter AI Integration

import os
import asyncio
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, Any, List

import dotenv
import aiofiles
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Загрузка переменных окружения
dotenv.load_dotenv()

# Конфигурация бота
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEYS = os.getenv('OPENROUTER_API_KEYS', '').split(',')
DAILY_MESSAGE_LIMIT = int(os.getenv('DAILY_MESSAGE_LIMIT', 50))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserStates(StatesGroup):
    waiting_for_input = State()

class TelegramAIBot:
    def __init__(self, bot_token: str, openrouter_keys: List[str]):
        self.bot = Bot(token=bot_token)
        self.dp = Dispatcher()
        self.openrouter_keys = openrouter_keys
        self.current_key_index = 0
        
        # Инициализация хранилищ
        self.user_messages = {}
        self.user_daily_messages = {}

        # Регистрация хендлеров
        self.register_handlers()

    def register_handlers(self):
        # Основные команды
        self.dp.message(Command("start"))(self.handle_start)
        self.dp.message(Command("help"))(self.handle_help)
        self.dp.message(Command("reset"))(self.handle_reset)
        self.dp.message(Command("menu"))(self.handle_menu)

        # Обработка сообщений
        self.dp.message(F.text)(self.handle_text_message)
        self.dp.message(F.document)(self.handle_document)
        self.dp.message(F.voice)(self.handle_voice)

    async def handle_start(self, message: Message):
        # Обработчик команды /start
        keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="📝 Начать чат")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ], resize_keyboard=True)
        
        await message.answer(
            "Привет! Я AI-бот с поддержкой OpenRouter. Готов помочь вам.",
            reply_markup=keyboard
        )

    async def handle_help(self, message: Message):
        # Обработчик команды /help
        help_text = """
🤖 Справка по боту:
• /start - Начать общение
• /help - Показать справку
• /reset - Сбросить контекст диалога
• /menu - Открыть меню

Я могу обрабатывать текст, документы и голосовые сообщения.
"""
        await message.answer(help_text)

    async def handle_reset(self, message: Message):
        # Сброс контекста для пользователя
        user_id = message.from_user.id
        if user_id in self.user_messages:
            del self.user_messages[user_id]
        await message.answer("🔄 История диалога сброшена.")

    async def handle_menu(self, message: Message):
        # Создание inline-клавиатуры
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 О боте", callback_data="about")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
        ])
        await message.answer("Меню:", reply_markup=keyboard)

    async def handle_text_message(self, message: Message):
        # Основная логика обработки текстовых сообщений
        user_id = message.from_user.id
        
        # Проверка лимита сообщений
        if not self.check_daily_limit(user_id):
            await message.answer("⚠️ Превышен дневной лимит сообщений.")
            return

        # Имитация печати
        await self.bot.send_chat_action(message.chat.id, "typing")

        # Логика работы с OpenRouter AI
        try:
            response = await self.get_ai_response(user_id, message.text)
            await message.reply(response, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка при получении ответа: {e}")
            await message.answer("🚫 Произошла ошибка. Попробуйте позже.")

    async def handle_document(self, message: Message):
        # Обработка документов
        user_id = message.from_user.id
        
        if not self.check_daily_limit(user_id):
            await message.answer("⚠️ Превышен дневной лимит сообщений.")
            return

        try:
            file = await self.bot.get_file(message.document.file_id)
            file_path = file.file_path
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}') as response:
                    content = await response.read()
                    text_content = content.decode('utf-8', errors='ignore')[:4000]
            
            await self.bot.send_chat_action(message.chat.id, "typing")
            response = await self.get_ai_response(user_id, f"Содержимое документа: {text_content}")
            await message.reply(response, parse_mode="Markdown")
        
        except Exception as e:
            logger.error(f"Ошибка при обработке документа: {e}")
            await message.answer("🚫 Не удалось обработать документ.")

    async def handle_voice(self, message: Message):
        # Обработка голосовых сообщений
        user_id = message.from_user.id
        
        if not self.check_daily_limit(user_id):
            await message.answer("⚠️ Превышен дневной лимит сообщений.")
            return

        try:
            file = await self.bot.get_file(message.voice.file_id)
            file_path = file.file_path
            
            # Здесь должна быть интеграция с сервисом распознавания речи
            # Для простоты используем заглушку
            transcription = "Голосовое сообщение не распознано"
            
            await self.bot.send_chat_action(message.chat.id, "typing")
            response = await self.get_ai_response(user_id, transcription)
            await message.reply(response, parse_mode="Markdown")
        
        except Exception as e:
            logger.error(f"Ошибка при обработке голосового: {e}")
            await message.answer("🚫 Не удалось обработать голосовое сообщение.")

    async def get_ai_response(self, user_id: int, message_text: str) -> str:
        # Управление историей сообщений
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        
        self.user_messages[user_id].append({"role": "user", "content": message_text})
        
        # Очистка истории если больше 50 сообщений или старше 24 часов
        self.clean_message_history(user_id)

        messages = self.user_messages[user_id][-10:]  # Берем последние 10 сообщений

        # Циклический перебор API-ключей
        for _ in range(len(self.openrouter_keys)):
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "model": "openai/gpt-3.5-turbo",
                        "messages": messages
                    }
                    headers = {
                        "Authorization": f"Bearer {self.openrouter_keys[self.current_key_index]}",
                        "Content-Type": "application/json"
                    }
                    
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions", 
                        json=payload, 
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            response_text = result['choices'][0]['message']['content']
                            
                            # Добавляем ответ в историю
                            self.user_messages[user_id].append({
                                "role": "assistant", 
                                "content": response_text
                            })
                            
                            return response_text
                        
                        elif response.status == 429:
                            # Переключаемся на следующий ключ при превышении лимита
                            self.current_key_index = (self.current_key_index + 1) % len(self.openrouter_keys)
                        else:
                            logger.error(f"Ошибка OpenRouter: {await response.text()}")
            
            except Exception as e:
                logger.error(f"Ошибка при запросе к OpenRouter: {e}")
                self.current_key_index = (self.current_key_index + 1) % len(self.openrouter_keys)
        
        return "🚫 Все API-ключи исчерпаны. Попробуйте позже."

    def check_daily_limit(self, user_id: int) -> bool:
        # Проверка дневного лимита сообщений
        current_time = datetime.now()
        
        if user_id not in self.user_daily_messages:
            self.user_daily_messages[user_id] = {
                'count': 1,
                'timestamp': current_time
            }
            return True
        
        user_data = self.user_daily_messages[user_id]
        time_diff = current_time - user_data['timestamp']
        
        if time_diff > timedelta(days=1):
            # Сброс счетчика после 24 часов
            user_data['count'] = 1
            user_data['timestamp'] = current_time
            return True
        
        if user_data['count'] < DAILY_MESSAGE_LIMIT:
            user_data['count'] += 1
            return True
        
        return False

    def clean_message_history(self, user_id: int):
        # Очистка истории сообщений
        current_time = datetime.now()
        
        if user_id in self.user_messages:
            self.user_messages[user_id] = [
                msg for msg in self.user_messages[user_id] 
                if (current_time - datetime.fromtimestamp(msg.get('timestamp', current_time.timestamp()))) 
                   < timedelta(hours=24)
            ]
            
            if len(self.user_messages[user_id]) > 50:
                self.user_messages[user_id] = self.user_messages[user_id][-50:]

    async def start_bot(self):
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")

async def main():
    bot = TelegramAIBot(TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEYS)
    await bot.start_bot()

if __name__ == '__main__':
    asyncio.run(main())
