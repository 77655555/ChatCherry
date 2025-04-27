import os
import asyncio
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, Any, List, Optional

import dotenv
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    Document, Voice
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import speech_recognition as sr
from pydub import AudioSegment

# Расширенная конфигурация
class Config:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENROUTER_API_KEYS = os.getenv('OPENROUTER_API_KEYS', '').split(',')
    DAILY_MESSAGE_LIMIT = int(os.getenv('DAILY_MESSAGE_LIMIT', 50))
    MAX_MESSAGE_LENGTH = 4096
    CONTEXT_WINDOW = 10
    SUPPORTED_DOCUMENT_TYPES = ['.txt', '.pdf', '.md']

# Расширенное логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedUserStates(StatesGroup):
    waiting_for_input = State()
    processing_document = State()
    voice_transcription = State()

class AIBotManager:
    def __init__(self):
        self.bot = Bot(
            token=Config.TELEGRAM_BOT_TOKEN, 
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        self.dp = Dispatcher()
        
        # Передовые хранилища
        self.user_contexts = {}
        self.user_stats = {}
        
        # Менеджеры ресурсов
        self.rate_limiter = RateLimiter()
        self.error_handler = ErrorHandler()
        
        self._register_handlers()

    def _register_handlers(self):
        # Расширенные обработчики команд
        handlers = {
            "start": self.handle_start,
            "help": self.handle_help,
            "reset": self.handle_reset,
            "stats": self.handle_stats
        }
        
        for command, handler in handlers.items():
            self.dp.message(Command(command))(handler)
        
        # Обработка различных типов сообщений
        self.dp.message(F.text)(self.handle_text)
        self.dp.message(F.document)(self.handle_document)
        self.dp.message(F.voice)(self.handle_voice)

    async def handle_start(self, message: Message):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🤖 Начать чат")],
                [KeyboardButton(text="📊 Статистика")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "Привет! Я мощный AI-ассистент с расширенными возможностями.",
            reply_markup=keyboard
        )

    async def handle_text(self, message: Message):
        try:
            # Проверка лимитов и безопасности
            if not self.rate_limiter.check_user_limit(message.from_user.id):
                return await message.reply("⚠️ Превышен лимит сообщений")

            # Получение AI-ответа
            response = await self._get_ai_response(
                message.from_user.id, 
                message.text
            )
            
            # Разбитие длинных сообщений
            for chunk in self._split_long_message(response):
                await message.reply(chunk)

        except Exception as e:
            await self.error_handler.handle(message, e)

    async def _get_ai_response(self, user_id: int, text: str) -> str:
        # Управление контекстом и получение ответа
        context = self._get_user_context(user_id)
        context.append({"role": "user", "content": text})
        
        try:
            async with aiohttp.ClientSession() as session:
                response = await self._call_openrouter(session, context)
                context.append({"role": "assistant", "content": response})
                return response
        except Exception as e:
            logger.error(f"AI Response Error: {e}")
            return "Произошла ошибка при генерации ответа."

    async def _call_openrouter(self, session, messages):
        # Интеллектуальный выбор и ротация API-ключей
        headers = {
            "Authorization": f"Bearer {self._select_api_key()}",
            "Content-Type": "application/json"
        }
        
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions", 
            json={
                "model": "openai/gpt-3.5-turbo",
                "messages": messages[-Config.CONTEXT_WINDOW:]
            },
            headers=headers
        ) as response:
            data = await response.json()
            return data['choices'][0]['message']['content']

    def _select_api_key(self):
        # Циклический выбор и обработка ключей
        key = Config.OPENROUTER_API_KEYS[0]
        Config.OPENROUTER_API_KEYS.append(
            Config.OPENROUTER_API_KEYS.pop(0)
        )
        return key

    def _get_user_context(self, user_id):
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        return self.user_contexts[user_id]

    def _split_long_message(self, text: str) -> List[str]:
        return [
            text[i:i+Config.MAX_MESSAGE_LENGTH] 
            for i in range(0, len(text), Config.MAX_MESSAGE_LENGTH)
        ]

class RateLimiter:
    def __init__(self):
        self.user_limits = {}
    
    def check_user_limit(self, user_id: int) -> bool:
        now = datetime.now()
        if user_id not in self.user_limits:
            self.user_limits[user_id] = {
                'count': 1, 
                'timestamp': now
            }
            return True
        
        user_data = self.user_limits[user_id]
        if (now - user_data['timestamp']).days >= 1:
            user_data['count'] = 1
            user_data['timestamp'] = now
            return True
        
        return user_data['count'] < Config.DAILY_MESSAGE_LIMIT

class ErrorHandler:
    async def handle(self, message: Message, error: Exception):
        error_id = hash(str(error))
        logger.error(f"Error {error_id}: {error}")
        await message.reply(
            f"❌ Произошла ошибка (ID: {error_id}). "
            "Техническая поддержка уже извещена."
        )

async def main():
    bot_manager = AIBotManager()
    await bot_manager.dp.start_polling(bot_manager.bot)

if __name__ == '__main__':
    dotenv.load_dotenv()
    asyncio.run(main())
