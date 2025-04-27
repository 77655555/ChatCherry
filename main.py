import asyncio
import datetime
import json
import logging
import os
import tempfile
from typing import List, Dict, Any, Optional, Union, Tuple

import aiohttp
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
)
from aiogram.utils.chat_action import ChatActionMiddleware
from pydub import AudioSegment
import speech_recognition as sr
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEYS = os.getenv("OPENROUTER_API_KEYS", "").split(",")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
DAILY_MESSAGE_LIMIT = int(os.getenv("DAILY_MESSAGE_LIMIT", "50"))
HTTP_RETRY_COUNT = int(os.getenv("HTTP_RETRY_COUNT", "3"))
MESSAGE_HISTORY_LIMIT = int(os.getenv("MESSAGE_HISTORY_LIMIT", "50"))
HISTORY_EXPIRATION_HOURS = int(os.getenv("HISTORY_EXPIRATION_HOURS", "24"))

# Класс для хранения информации о пользователе
class UserData:
    def __init__(self):
        self.message_history: List[Dict[str, Any]] = []
        self.last_activity: datetime.datetime = datetime.datetime.now()
        self.daily_messages: int = 0
        self.last_reset_date: datetime.date = datetime.datetime.now().date()
    
    def add_message(self, role: str, content: str):
        # Обновление счетчика сообщений
        current_date = datetime.datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_messages = 0
            self.last_reset_date = current_date
        
        if role == "user":
            self.daily_messages += 1
        
        # Добавление сообщения в историю
        self.message_history.append({
            "role": role,
            "content": content
        })
        
        # Ограничение истории сообщений
        if len(self.message_history) > MESSAGE_HISTORY_LIMIT:
            self.message_history = self.message_history[-MESSAGE_HISTORY_LIMIT:]
        
        self.last_activity = datetime.datetime.now()
    
    def clear_history(self):
        self.message_history = []
    
    def is_history_expired(self) -> bool:
        expiration_time = self.last_activity + datetime.timedelta(hours=HISTORY_EXPIRATION_HOURS)
        return datetime.datetime.now() > expiration_time
    
    def can_send_message(self) -> bool:
        current_date = datetime.datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_messages = 0
            self.last_reset_date = current_date
            return True
        return self.daily_messages < DAILY_MESSAGE_LIMIT
    
    def remaining_messages(self) -> int:
        return DAILY_MESSAGE_LIMIT - self.daily_messages

# Хранилище данных пользователей
user_data: Dict[int, UserData] = {}

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Добавление middleware для имитации печати
dp.message.middleware(ChatActionMiddleware())

# Функция для очистки истории неактивных пользователей
async def cleanup_expired_history():
    while True:
        try:
            to_remove = []
            for user_id, data in user_data.items():
                if data.is_history_expired():
                    to_remove.append(user_id)
            
            for user_id in to_remove:
                user_data[user_id].clear_history()
                logger.info(f"Cleared history for user {user_id} due to inactivity")
            
            await asyncio.sleep(3600)  # Проверка раз в час
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(3600)

# Функция для взаимодействия с OpenRouter API
async def query_openrouter(messages: List[Dict[str, Any]]) -> Tuple[Optional[str], bool]:
    headers = {
        "Content-Type": "application/json",
    }
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
    }
    
    # Попытка использования разных API ключей
    for api_key in OPENROUTER_API_KEYS:
        current_headers = headers.copy()
        current_headers["Authorization"] = f"Bearer {api_key}"
        
        for attempt in range(HTTP_RETRY_COUNT):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        OPENROUTER_URL,
                        headers=current_headers,
                        json=data,
                        timeout=60
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result["choices"][0]["message"]["content"], True
                        else:
                            error_text = await response.text()
                            logger.error(f"API error: {response.status}, {error_text}")
                            # Если ошибка связана с API ключом, пробуем следующий
                            if response.status in [401, 403]:
                                break
                            # Иначе повторяем попытку
                            await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Request error: {e}")
                await asyncio.sleep(1)
    
    return "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.", False

# Создание клавиатуры главного меню
def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 Начать диалог")],
            [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="🔄 Сбросить историю")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# Создание инлайн клавиатуры меню
def get_inline_menu() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Начать диалог", callback_data="start_dialog")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help"), 
             InlineKeyboardButton(text="🔄 Сбросить", callback_data="reset")]
        ]
    )
    return keyboard

# Обработчик команды /start
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = UserData()
    
    await message.answer(
        "👋 Добро пожаловать! Я ваш личный AI-ассистент на базе GPT-3.5-Turbo.\n\n"
        "Я могу помочь с ответами на вопросы, написанием текстов и многим другим.\n\n"
        "Отправьте мне текстовое сообщение, голосовое сообщение или документ, и я постараюсь помочь!",
        reply_markup=get_main_keyboard()
    )

# Обработчик команды /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id
    remaining = user_data.get(user_id, UserData()).remaining_messages()
    
    await message.answer(
        "📖 *Справка по боту*\n\n"
        "Я могу обрабатывать следующие типы сообщений:\n"
        "• Текстовые сообщения\n"
        "• Голосовые сообщения (я распознаю речь и отвечу на запрос)\n"
        "• Документы (я прочитаю содержимое и отвечу)\n\n"
        "Доступные команды:\n"
        "/start - Начать диалог\n"
        "/help - Показать эту справку\n"
        "/reset - Сбросить историю диалога\n"
        "/menu - Показать меню с кнопками\n\n"
        f"Лимит: {DAILY_MESSAGE_LIMIT} сообщений в день (осталось: {remaining}).",
        parse_mode="Markdown"
    )

# Обработчик команды /reset
@router.message(Command("reset"))
async def cmd_reset(message: Message):
    user_id = message.from_user.id
    if user_id in user_data:
        user_data[user_id].clear_history()
    
    await message.answer(
        "🔄 История диалога сброшена. Теперь мы можем начать общение заново!",
        reply_markup=get_main_keyboard()
    )

# Обработчик команды /menu
@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(
        "🧠 Выберите действие из меню:",
        reply_markup=get_inline_menu()
    )

# Обработчик инлайн кнопок
@router.callback_query()
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    action = callback_query.data
    
    if action == "start_dialog":
        await bot.send_message(
            user_id,
            "🤖 Давайте начнем диалог! О чем вы хотите поговорить?",
            reply_markup=get_main_keyboard()
        )
    elif action == "help":
        remaining = user_data.get(user_id, UserData()).remaining_messages()
        await bot.send_message(
            user_id,
            "📖 *Справка по боту*\n\n"
            "Я могу обрабатывать следующие типы сообщений:\n"
            "• Текстовые сообщения\n"
            "• Голосовые сообщения (я распознаю речь и отвечу на запрос)\n"
            "• Документы (я прочитаю содержимое и отвечу)\n\n"
            "Доступные команды:\n"
            "/start - Начать диалог\n"
            "/help - Показать эту справку\n"
            "/reset - Сбросить историю диалога\n"
            "/menu - Показать меню с кнопками\n\n"
            f"Лимит: {DAILY_MESSAGE_LIMIT} сообщений в день (осталось: {remaining}).",
            parse_mode="Markdown"
        )
    elif action == "reset":
        if user_id in user_data:
            user_data[user_id].clear_history()
        await bot.send_message(
            user_id,
            "🔄 История диалога сброшена. Теперь мы можем начать общение заново!"
        )
    
    # Удаление уведомления об обработке инлайн кнопки
    await bot.answer_callback_query(callback_query.id)

# Обработчик текстовых кнопок
@router.message(F.text.in_(["🤖 Начать диалог", "❓ Помощь", "🔄 Сбросить историю"]))
async def handle_text_buttons(message: Message):
    text = message.text
    
    if text == "🤖 Начать диалог":
        await message.answer(
            "🤖 Давайте начнем диалог! О чем вы хотите поговорить?"
        )
    elif text == "❓ Помощь":
        await cmd_help(message)
    elif text == "🔄 Сбросить историю":
        await cmd_reset(message)

# Функция для распознавания речи из голосового сообщения
async def transcribe_voice(file_path: str) -> str:
    try:
        # Конвертация OGG в WAV (голосовые сообщения в Telegram - OGG)
        audio = AudioSegment.from_ogg(file_path)
        wav_path = file_path.replace(".ogg", ".wav")
        audio.export(wav_path, format="wav")
        
        # Распознавание речи
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="ru-RU")
            
        # Удаление временных файлов
        os.remove(wav_path)
        return text
    except Exception as e:
        logger.error(f"Error transcribing voice: {e}")
        return "Извините, я не смог распознать речь в голосовом сообщении."

# Функция для обработки документов
async def process_document(file_path: str) -> str:
    try:
        # Определение типа документа по расширению
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in [".txt", ".md", ".py", ".js", ".html", ".css", ".json"]:
            # Текстовые файлы
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return content
        else:
            return "Извините, я могу обрабатывать только текстовые файлы (TXT, MD, PY, JS, HTML, CSS, JSON)"
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        return "Извините, произошла ошибка при обработке документа."

# Обработчик текстовых сообщений
@router.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    user_text = message.text
    
    # Инициализация данных пользователя, если их еще нет
    if user_id not in user_data:
        user_data[user_id] = UserData()
    
    # Проверка лимита сообщений
    if not user_data[user_id].can_send_message():
        await message.answer(
            f"⚠️ Вы достигли дневного лимита сообщений ({DAILY_MESSAGE_LIMIT}). "
            "Лимит будет сброшен завтра."
        )
        return
    
    # Добавление сообщения пользователя в историю
    user_data[user_id].add_message("user", user_text)
    
    # Начало имитации печати
    async with message.chat.action("typing"):
        # Запрос к API
        response, success = await query_openrouter(user_data[user_id].message_history)
        
        if success:
            # Добавление ответа бота в историю
            user_data[user_id].add_message("assistant", response)
            
            # Отправка ответа с поддержкой Markdown
            try:
                await message.answer(
                    response,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending markdown message: {e}")
                # Отправка без форматирования при ошибке
                await message.answer(response)
        else:
            await message.answer(response)

# Обработчик голосовых сообщений
@router.message(F.voice)
async def handle_voice(message: Message):
    user_id = message.from_user.id
    
    # Инициализация данных пользователя, если их еще нет
    if user_id not in user_data:
        user_data[user_id] = UserData()
    
    # Проверка лимита сообщений
    if not user_data[user_id].can_send_message():
        await message.answer(
            f"⚠️ Вы достигли дневного лимита сообщений ({DAILY_MESSAGE_LIMIT}). "
            "Лимит будет сброшен завтра."
        )
        return
    
    # Сообщение о начале обработки
    processing_msg = await message.answer("🎤 Распознаю голосовое сообщение...")
    
    try:
        # Скачивание голосового сообщения
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = os.path.join(tempfile.gettempdir(), f"{file_id}.ogg")
        await bot.download_file(file.file_path, file_path)
        
        # Распознавание речи
        text = await transcribe_voice(file_path)
        
        # Удаление временного файла
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Обновление сообщения с распознанным текстом
        await bot.edit_message_text(
            f"🎤 Распознанный текст: {text}",
            user_id,
            processing_msg.message_id
        )
        
        # Добавление сообщения пользователя в историю
        user_data[user_id].add_message("user", text)
        
        # Начало имитации печати
        async with message.chat.action("typing"):
            # Запрос к API
            response, success = await query_openrouter(user_data[user_id].message_history)
            
            if success:
                # Добавление ответа бота в историю
                user_data[user_id].add_message("assistant", response)
                
                # Отправка ответа с поддержкой Markdown
                try:
                    await message.answer(
                        response,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error sending markdown message: {e}")
                    # Отправка без форматирования при ошибке
                    await message.answer(response)
            else:
                await message.answer(response)
    except Exception as e:
        logger.error(f"Error processing voice message: {e}")
        await bot.edit_message_text(
            "❌ Произошла ошибка при обработке голосового сообщения.",
            user_id,
            processing_msg.message_id
        )

# Обработчик документов
@router.message(F.document)
async def handle_document(message: Message):
    user_id = message.from_user.id
    
    # Инициализация данных пользователя, если их еще нет
    if user_id not in user_data:
        user_data[user_id] = UserData()
    
    # Проверка лимита сообщений
    if not user_data[user_id].can_send_message():
        await message.answer(
            f"⚠️ Вы достигли дневного лимита сообщений ({DAILY_MESSAGE_LIMIT}). "
            "Лимит будет сброшен завтра."
        )
        return
    
    # Сообщение о начале обработки
    processing_msg = await message.answer("📄 Обрабатываю документ...")
    
    try:
        # Скачивание документа
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_name = message.document.file_name or f"{file_id}"
        file_path = os.path.join(tempfile.gettempdir(), file_name)
        await bot.download_file(file.file_path, file_path)
        
        # Обработка документа
        text = await process_document(file_path)
        
        # Удаление временного файла
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Обновление сообщения с информацией о документе
        await bot.edit_message_text(
            f"📄 Документ обработан: {message.document.file_name}",
            user_id,
            processing_msg.message_id
        )
        
        # Добавление сообщения пользователя в историю
        user_data[user_id].add_message("user", f"Содержимое документа: {text}")
        
        # Начало имитации печати
        async with message.chat.action("typing"):
            # Запрос к API
            response, success = await query_openrouter(user_data[user_id].message_history)
            
            if success:
                # Добавление ответа бота в историю
                user_data[user_id].add_message("assistant", response)
                
                # Отправка ответа с поддержкой Markdown
                try:
                    await message.answer(
                        response,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error sending markdown message: {e}")
                    # Отправка без форматирования при ошибке
                    await message.answer(response)
            else:
                await message.answer(response)
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        await bot.edit_message_text(
            "❌ Произошла ошибка при обработке документа.",
            user_id,
            processing_msg.message_id
        )

# Обработчик для нераспознанных сообщений
@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "Извините, я не смог обработать этот тип сообщения. "
        "Пожалуйста, отправьте текстовое сообщение, голосовое сообщение или документ."
    )

# Функция для запуска веб-сервера (для работы с Render.com)
async def on_startup():
    # Запуск фоновой задачи по очистке устаревшей истории
    asyncio.create_task(cleanup_expired_history())
    
    # Установка вебхука (если нужно для Render.com)
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await bot.set_webhook(webhook_url)
    
    logger.info("Bot started!")

# Основная функция запуска бота
async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
