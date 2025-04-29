import asyncio
import logging
import json
import os
import re
import time
import requests
from datetime import datetime, date
from typing import Dict, List, Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor




from aiogram import Bot, Dispatcher, Router, F, html
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ChatAction, ParseMode
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile,
    InputMediaPhoto, PhotoSize
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.exceptions import TelegramAPIError




# Конфигурация и константы
CONFIG = {
    "API_URL": "https://api.intelligence.io.solutions/api/v1",
    "TOKEN": os.getenv("TELEGRAM_TOKEN", "7839597384:AAFlm4v3qcudhJfiFfshz1HW6xpKhtqlV5g"),
    "API_KEY": os.getenv("AI_API_KEY", "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6ImJlMjYwYjFhLWI0OWMtNDU2MC04ODZiLTMwYTBmMGFlNGZlNSIsImV4cCI6NDg5OTUwNzg0MH0.Z46h1WZ-2jsXyg43r2M0okgeLoSEzrq-ULHRMS-EW6r3ccxYkXTZ5mNJO5Aw1qBAkRI5NX9t8zXc1sbUxt8WzA"),
    "DEFAULT_SYSTEM_PROMPT": "Вы - полезный AI-ассистент. Предоставляйте точные и информативные ответы. Для технических вопросов и примеров кода используйте Markdown-форматирование.",
    "MAX_MESSAGE_LENGTH": 4096,
    "MAX_CONTEXT_LENGTH": 15,  # Максимальное количество сообщений в истории для API
    "TEMPERATURE": 0.3,  # Уровень креативности (ниже = более предсказуемо)
    "MAX_TOKENS": 4000,  # Максимальная длина ответа
    "RETRY_ATTEMPTS": 3,  # Количество попыток переключения модели при ошибке
    "ADMIN_IDS": [5456372164],  # ID администраторов (заменить на ваши ID)
    "ALLOWED_FORMATS": ["jpg", "jpeg", "png", "webp"],  # Поддерживаемые форматы изображений
    "MAX_FILE_SIZE": 10 * 1024 * 1024,  # Максимальный размер файла (10 МБ)
    "CACHE_TIMEOUT": 3600,  # Время жизни кэша в секундах (1 час)
    "TYPING_INTERVAL": 3.0,  # Интервал отправки статуса печати в секундах
    "HISTORY_FILE": "user_history.json",  # Файл для хранения полной истории
}




# Категории моделей для более удобного представления
MODEL_CATEGORIES = {
    "Продвинутые": [
        "meta-llama/Llama-3.3-70B-Instruct",
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "mistralai/Mistral-Large-Instruct-2411",
        "databricks/dbrx-instruct",
        "google/gemma-3-27b-it",
    ],
    "С возможностью анализа изображений": [
        "meta-llama/Llama-3.2-90B-Vision-Instruct",
        "Qwen/Qwen2-VL-7B-Instruct",
    ],
    "Специализированные": [
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "nvidia/AceMath-7B-Instruct",
        "jinaai/ReaderLM-v2",
        "watt-ai/watt-tool-70B",
    ],
    "Универсальные": [
        "Qwen/QwQ-32B",
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        "mistralai/Ministral-8B-Instruct-2410",
        "netease-youdao/Confucius-01-14B",
        "microsoft/phi-4",
        "bespokelabs/Bespoke-Stratos-32B",
        "NovaSky-AI/Sky-T1-32B-Preview",
        "tiiuae/Falcon3-10B-Instruct",
        "THUDM/glm-4-9b-chat",
        "CohereForAI/aya-expanse-326",
        "openbmb/MiniCPM3-4B",
        "Qwen/Qwen2.5-1.5B-Instruct",
        "ozone-ai/ox-1",
        "microsoft/Phi-3.5-mini-instruct",
        "ibm-granite/granite-3.1-8b-instruct",
        "SentientAGI/Dobby-Mini-Unhinged-Llama-3.1-8B",
        "neuralmagic/Llama-3.1-Nemotron-70B-Instruct-HF-FP8-dynamic",
    ]
}




# Список всех моделей из категорий
ALL_MODELS = []
for category, models in MODEL_CATEGORIES.items():
    ALL_MODELS.extend(models)




# Приветственные фразы для простых вопросов
GREETINGS = {
    r"(?i)^(привет|хай|здравствуй|здрасте|хелло|hi|hello)": [
        "Привет! Чем я могу вам помочь?",
        "Здравствуйте! Готов помочь вам.",
        "Приветствую! Задавайте ваш вопрос."
    ],
    r"(?i)^как дела|как (ты|у тебя)": [
        "Всё отлично, спасибо! Чем могу помочь?",
        "Работаю в штатном режиме. Чем могу быть полезен?",
        "У меня всё хорошо. Готов помочь вам."
    ],
    r"(?i)^доброе утро": [
        "Доброе утро! Чем я могу помочь вам сегодня?",
        "Доброе утро! Готов к работе."
    ],
    r"(?i)^добрый день": [
        "Добрый день! Чем могу быть полезен?",
        "Добрый день! Готов ответить на ваши вопросы."
    ],
    r"(?i)^добрый вечер": [
        "Добрый вечер! Чем я могу вам помочь?",
        "Добрый вечер! Готов к работе."
    ]
}




# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("bot.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.addHandler(console_handler)




# Основные компоненты
bot = Bot(token=CONFIG["TOKEN"])
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)
dp.message.middleware(ChatActionMiddleware())




# FSM для состояний бота
class UserStates(StatesGroup):
    waiting_for_message = State()  # Ожидание сообщения
    custom_system_prompt = State()  # Ввод пользовательского системного промпта
    waiting_for_model_selection = State()  # Выбор модели
    waiting_for_model_search = State()  # Поиск модели
    waiting_for_direct_model = State()  # Прямой ввод названия модели
    waiting_for_temperature = State()  # Настройка temperature
    waiting_for_thinking_budget = State()  # Настройка thinking_budget
    viewing_history = State()  # Просмотр истории




# Кэш и переменные для моделей
model_cache = {}  # Кэш ответов моделей
user_settings = {}  # Настройки пользователей
user_contexts = {}  # История диалогов с пользователями (для API)
user_full_history = {}  # Полная история диалогов (для хранения)
typing_tasks = {}  # Задачи непрерывной отправки статуса печати
favorite_models = {}  # Избранные модели пользователей




# Функции-помощники
def format_model_name(model_name: str) -> str:
    """Форматирует имя модели для отображения."""
    return model_name.split('/')[-1]




def save_user_settings():
    """Сохраняет настройки пользователей в JSON-файл."""
    with open('user_settings.json', 'w', encoding='utf-8') as f:
        json.dump(user_settings, f, ensure_ascii=False, indent=2)




def save_user_history():
    """Сохраняет полную историю диалогов пользователей в JSON-файл."""
    with open(CONFIG["HISTORY_FILE"], 'w', encoding='utf-8') as f:
        # Преобразуем ключи-числа в строки для JSON
        serializable_history = {str(k): v for k, v in user_full_history.items()}
        json.dump(serializable_history, f, ensure_ascii=False, indent=2)




def load_user_settings():
    """Загружает настройки пользователей из JSON-файла."""
    global user_settings
    try:
        with open('user_settings.json', 'r', encoding='utf-8') as f:
            user_settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        user_settings = {}
        save_user_settings()




    # Миграция старых настроек
    for user_id, settings in user_settings.items():
        if "requests_left" not in settings:
            user_settings[user_id]["requests_left"] = 10
            user_settings[user_id]["last_reset"] = str(date.today())
        if "model" not in settings:
            user_settings[user_id]["model"] = ALL_MODELS[0]
        if "system_prompt" not in settings:
            user_settings[user_id]["system_prompt"] = CONFIG["DEFAULT_SYSTEM_PROMPT"]
        if "temperature" not in settings:
            user_settings[user_id]["temperature"] = CONFIG["TEMPERATURE"]
        if "thinking_budget" not in settings:
            user_settings[user_id]["thinking_budget"] = 0
        if "favorite_models" not in settings:
            user_settings[user_id]["favorite_models"] = []




    save_user_settings()




def load_user_history():
    """Загружает полную историю диалогов пользователей из JSON-файла."""
    global user_full_history
    try:
        with open(CONFIG["HISTORY_FILE"], 'r', encoding='utf-8') as f:
            history_data = json.load(f)
            # Преобразуем ключи-строки обратно в числа
            user_full_history = {int(k): v for k, v in history_data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        user_full_history = {}
        save_user_history()




async def continuous_typing_action(chat_id: int, stop_event: asyncio.Event):
    """Непрерывно отправляет статус 'печатает' в чат, пока не будет остановлен."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(CONFIG["TYPING_INTERVAL"])
        except Exception as e:
            logger.error(f"Ошибка при отправке статуса печати: {e}")
            await asyncio.sleep(1)  # Короткая пауза в случае ошибки




async def start_typing_action(chat_id: int) -> asyncio.Event:
    """Запускает непрерывную отправку статуса 'печатает' и возвращает событие для остановки."""
    stop_event = asyncio.Event()

    # Останавливаем предыдущую задачу, если она существует
    if chat_id in typing_tasks and not typing_tasks[chat_id]["stop_event"].is_set():
        typing_tasks[chat_id]["stop_event"].set()
        try:
            await typing_tasks[chat_id]["task"]
        except Exception as e:
            logger.error(f"Ошибка при остановке предыдущей задачи печати: {e}")

    # Создаем новую задачу
    task = asyncio.create_task(continuous_typing_action(chat_id, stop_event))
    typing_tasks[chat_id] = {"task": task, "stop_event": stop_event}

    return stop_event




async def stop_typing_action(chat_id: int):
    """Останавливает непрерывную отправку статуса 'печатает'."""
    if chat_id in typing_tasks and not typing_tasks[chat_id]["stop_event"].is_set():
        typing_tasks[chat_id]["stop_event"].set()
        try:
            await typing_tasks[chat_id]["task"]
        except Exception as e:
            logger.error(f"Ошибка при остановке задачи печати: {e}")




def get_user_model(user_id: int) -> str:
    """Возвращает модель, выбранную пользователем, или модель по умолчанию."""
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "model": ALL_MODELS[0],
            "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
            "temperature": CONFIG["TEMPERATURE"],
            "thinking_budget": 0,
            "favorite_models": []
        }
        save_user_settings()
    return user_settings[str(user_id)].get("model", ALL_MODELS[0])




def get_system_prompt(user_id: int) -> str:
    """Возвращает системный промпт пользователя или промпт по умолчанию."""
    if str(user_id) not in user_settings:
        return CONFIG["DEFAULT_SYSTEM_PROMPT"]
    return user_settings[str(user_id)].get("system_prompt", CONFIG["DEFAULT_SYSTEM_PROMPT"])




def get_user_temperature(user_id: int) -> float:
    """Возвращает значение temperature для пользователя или значение по умолчанию."""
    if str(user_id) not in user_settings:
        return CONFIG["TEMPERATURE"]
    return user_settings[str(user_id)].get("temperature", CONFIG["TEMPERATURE"])




def get_user_thinking_budget(user_id: int) -> int:
    """Возвращает значение thinking_budget для пользователя."""
    if str(user_id) not in user_settings:
        return 0
    return user_settings[str(user_id)].get("thinking_budget", 0)




def get_user_favorite_models(user_id: int) -> List[str]:
    """Возвращает список избранных моделей пользователя."""
    if str(user_id) not in user_settings:
        return []
    return user_settings[str(user_id)].get("favorite_models", [])




def add_to_favorite_models(user_id: int, model: str):
    """Добавляет модель в избранное пользователя."""
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "model": ALL_MODELS[0],
            "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
            "temperature": CONFIG["TEMPERATURE"],
            "thinking_budget": 0,
            "favorite_models": []
        }

    favorites = user_settings[str(user_id)].get("favorite_models", [])
    if model not in favorites:
        favorites.append(model)
        user_settings[str(user_id)]["favorite_models"] = favorites
        save_user_settings()




def remove_from_favorite_models(user_id: int, model: str):
    """Удаляет модель из избранного пользователя."""
    if str(user_id) in user_settings and "favorite_models" in user_settings[str(user_id)]:
        favorites = user_settings[str(user_id)]["favorite_models"]
        if model in favorites:
            favorites.remove(model)
            user_settings[str(user_id)]["favorite_models"] = favorites
            save_user_settings()




def get_user_context(user_id: int) -> List[Dict[str, str]]:
    """Возвращает контекст диалога с пользователем для API."""
    if user_id not in user_contexts:
        user_contexts[user_id] = []
    return user_contexts[user_id]




def get_user_full_history(user_id: int) -> List[Dict[str, str]]:
    """Возвращает полную историю диалога с пользователем."""
    if user_id not in user_full_history:
        user_full_history[user_id] = []
    return user_full_history[user_id]




def add_to_user_context(user_id: int, role: str, content: str):
    """Добавляет сообщение в контекст диалога с пользователем для API."""
    if user_id not in user_contexts:
        user_contexts[user_id] = []

    # Добавляем новое сообщение
    user_contexts[user_id].append({"role": role, "content": content})

    # Ограничиваем длину истории для API
    if len(user_contexts[user_id]) > CONFIG["MAX_CONTEXT_LENGTH"] * 2:  # *2 чтобы учесть пары вопрос-ответ
        # Оставляем первое сообщение (обычно системное) и последние N сообщений
        user_contexts[user_id] = [user_contexts[user_id][0]] + user_contexts[user_id][-(CONFIG["MAX_CONTEXT_LENGTH"]*2-1):]

    # Также добавляем в полную историю
    add_to_user_full_history(user_id, role, content)




def add_to_user_full_history(user_id: int, role: str, content: str):
    """Добавляет сообщение в полную историю диалога с пользователем."""
    if user_id not in user_full_history:
        user_full_history[user_id] = []

    # Добавляем новое сообщение с временной меткой
    message = {
        "role": role, 
        "content": content,
        "timestamp": datetime.now().isoformat()
    }

    user_full_history[user_id].append(message)

    # Сохраняем историю в файл
    save_user_history()




def clear_user_context(user_id: int):
    """Очищает контекст диалога с пользователем для API."""
    if user_id in user_contexts:
        # Сохраняем только системный промпт, если он есть
        system_messages = [msg for msg in user_contexts[user_id] if msg["role"] == "system"]
        user_contexts[user_id] = system_messages if system_messages else []

    # Добавляем разделитель в полную историю
    if user_id in user_full_history and user_full_history[user_id]:
        add_to_user_full_history(user_id, "system", "--- НОВЫЙ ДИАЛОГ ---")




def is_greeting(text: str) -> Optional[str]:
    """Проверяет, является ли текст приветствием, и возвращает ответ, если да."""
    import random
    for pattern, responses in GREETINGS.items():
        if re.match(pattern, text.strip()):
            return random.choice(responses)
    return None




def search_models(query: str) -> List[str]:
    """Ищет модели по запросу."""
    query = query.lower()
    results = []

    for model in ALL_MODELS:
        model_name = model.lower()
        if query in model_name:
            results.append(model)

    return results




def extract_thinking_budget_param(message_text: str) -> tuple[str, Optional[int]]:
    """Извлекает параметр thinking_budget из текста сообщения."""
    pattern = r'--thinking_budget\s+(\d+)'
    match = re.search(pattern, message_text)

    if match:
        budget = int(match.group(1))
        # Удаляем параметр из текста
        cleaned_text = re.sub(pattern, '', message_text).strip()
        return cleaned_text, budget

    return message_text, None




def extract_model_param(message_text: str) -> tuple[str, Optional[str]]:
    """Извлекает параметр модели из текста сообщения."""
    pattern = r'--model\s+([^\s]+)'
    match = re.search(pattern, message_text)

    if match:
        model_query = match.group(1)
        # Удаляем параметр из текста
        cleaned_text = re.sub(pattern, '', message_text).strip()

        # Ищем модель по запросу
        matching_models = []
        for model in ALL_MODELS:
            if model_query.lower() in model.lower():
                matching_models.append(model)

        # Возвращаем первую найденную модель или None
        model = matching_models[0] if matching_models else None
        return cleaned_text, model

    return message_text, None




async def process_image(photo: PhotoSize) -> Optional[str]:
    """Обрабатывает изображение и возвращает его в base64 кодировке."""
    try:
        file_info = await bot.get_file(photo.file_id)
        file_path = file_info.file_path




        if file_info.file_size > CONFIG["MAX_FILE_SIZE"]:
            return None




        # Получаем файл через Telegram API
        file_url = f"https://api.telegram.org/file/bot{CONFIG['TOKEN']}/{file_path}"
        response = requests.get(file_url)




        if response.status_code != 200:
            return None




        # Кодируем файл в base64
        import base64
        file_content = base64.b64encode(response.content).decode('utf-8')




        # Определяем тип файла
        file_extension = file_path.split('.')[-1].lower()
        if file_extension not in CONFIG["ALLOWED_FORMATS"]:
            return None




        return f"data:image/{file_extension};base64,{file_content}"




    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        return None




async def split_and_send_message(message: Message, text: str, parse_mode: Optional[str] = ParseMode.MARKDOWN):
    """Разделяет длинный текст на части и отправляет их."""
    max_length = CONFIG["MAX_MESSAGE_LENGTH"]




    if len(text) <= max_length:
        await message.answer(text, parse_mode=parse_mode)
        return




    # Разбиваем на части с сохранением целостности блоков кода
    parts = []
    current_part = ""
    code_block = False




    for line in text.split('\n'):
        # Проверяем, является ли строка началом или концом блока кода
        if line.strip().startswith('```') and line.strip().count('```') % 2 != 0:
            code_block = not code_block




        # Если текущая часть + строка не превышает лимит
        if len(current_part + line + '\n') <= max_length:
            current_part += line + '\n'
        else:
            # Если мы находимся в блоке кода, завершаем его перед разрывом
            if code_block:
                current_part += '```\n'
                parts.append(current_part)
                current_part = '```' + line.split('```', 1)[-1] + '\n'
                # Восстанавливаем состояние блока кода
                if line.strip().count('```') % 2 != 0:
                    code_block = not code_block
            else:
                parts.append(current_part)
                current_part = line + '\n'




    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part)




    # Отправляем все части
    for part in parts:
        await message.answer(part, parse_mode=parse_mode)
        await asyncio.sleep(0.3)  # Небольшая задержка между сообщениями




async def format_history_page(user_id: int, page: int = 0, page_size: int = 5) -> tuple[str, int, int]:
    """Форматирует страницу истории диалогов пользователя."""
    history = get_user_full_history(user_id)

    if not history:
        return "📜 История диалогов пуста.", 0, 0

    # Разбиваем историю на блоки диалогов
    dialogs = []
    current_dialog = []

    for message in history:
        if message["role"] == "system" and "НОВЫЙ ДИАЛОГ" in message.get("content", ""):
            if current_dialog:
                dialogs.append(current_dialog)
                current_dialog = []
        else:
            current_dialog.append(message)

    if current_dialog:
        dialogs.append(current_dialog)

    # Разворачиваем диалоги в обратном порядке (новые сначала)
    dialogs.reverse()

    # Вычисляем общее количество страниц
    total_pages = len(dialogs)

    # Проверяем корректность номера страницы
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0

    # Если диалогов нет
    if not dialogs:
        return "📜 История диалогов пуста.", 0, 0

    # Форматируем выбранный диалог
    dialog = dialogs[page]

    dialog_date = None
    try:
        # Получаем дату первого сообщения в диалоге
        if "timestamp" in dialog[0]:
            dialog_date = datetime.fromisoformat(dialog[0]["timestamp"]).strftime("%d.%m.%Y %H:%M")
    except (IndexError, ValueError, KeyError) as e:
        logger.error(f"Ошибка при получении даты диалога: {e}")

    header = f"📜 **История диалогов** (диалог {page + 1} из {total_pages})"
    if dialog_date:
        header += f" - {dialog_date}"

    formatted_messages = []

    for msg in dialog:
        if msg["role"] == "system" and "НОВЫЙ ДИАЛОГ" not in msg.get("content", ""):
            # Системные сообщения (кроме разделителей) не показываем
            continue

        role_icon = {
            "user": "👤",
            "assistant": "🤖",
            "system": "🔄"
        }.get(msg["role"], "❓")

        # Для длинных сообщений делаем обрезку
        content = msg["content"]
        if len(content) > 300:
            content = content[:297] + "..."

        # Форматируем сообщение
        formatted_msg = f"{role_icon} **{msg['role'].capitalize()}**: {content}"
        formatted_messages.append(formatted_msg)

    return header + "\n\n" + "\n\n".join(formatted_messages), page, total_pages




async def create_model_selection_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора модели по категориям."""
    builder = InlineKeyboardBuilder()




    # Добавляем кнопки категорий
    for category in MODEL_CATEGORIES:
        builder.row(
            InlineKeyboardButton(
                text=f"📚 {category} ({len(MODEL_CATEGORIES[category])})",
                callback_data=f"category:{category}"
            )
        )

    # Добавляем кнопку поиска
    builder.row(
        InlineKeyboardButton(
            text="🔍 Поиск модели по названию",
            callback_data="search_model"
        )
    )

    # Добавляем кнопку прямого ввода модели
    builder.row(
        InlineKeyboardButton(
            text="⌨️ Ввести название модели",
            callback_data="direct_model"
        )
    )

    # Добавляем кнопку "Избранные модели"
    builder.row(
        InlineKeyboardButton(
            text="⭐ Избранные модели",
            callback_data="favorite_models"
        )
    )

    # Добавляем кнопку "Все модели"
    builder.row(
        InlineKeyboardButton(
            text="📋 Показать все модели",
            callback_data="all_models"
        )
    )




    return builder.as_markup()




async def create_category_models_keyboard(category: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру с моделями определенной категории."""
    builder = InlineKeyboardBuilder()




    # Добавляем модели из выбранной категории
    for model in MODEL_CATEGORIES.get(category, []):
        builder.row(
            InlineKeyboardButton(
                text=format_model_name(model),
                callback_data=f"model:{model}"
            )
        )




    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к категориям",
            callback_data="back_to_categories"
        )
    )




    return builder.as_markup()


async def create_all_models_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру со всеми доступными моделями."""
    builder = InlineKeyboardBuilder()

    # Добавляем все модели
    for model in ALL_MODELS:
        builder.row(
            InlineKeyboardButton(
                text=format_model_name(model),
                callback_data=f"model:{model}"
            )
        )

    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к категориям",
            callback_data="back_to_categories"
        )
    )

    return builder.as_markup()


async def create_favorite_models_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру с избранными моделями пользователя."""
    builder = InlineKeyboardBuilder()

    favorite_models = get_user_favorite_models(user_id)

    if not favorite_models:
        builder.row(
            InlineKeyboardButton(
                text="У вас нет избранных моделей",
                callback_data="no_action"
            )
        )
    else:
        # Добавляем избранные модели
        for model in favorite_models:
            builder.row(
                InlineKeyboardButton(
                    text=format_model_name(model),
                    callback_data=f"model:{model}"
                )
            )

    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к категориям",
            callback_data="back_to_categories"
        )
    )

    return builder.as_markup()


async def create_search_results_keyboard(models: List[str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с результатами поиска моделей."""
    builder = InlineKeyboardBuilder()

    if not models:
        builder.row(
            InlineKeyboardButton(
                text="Модели не найдены",
                callback_data="no_action"
            )
        )
    else:
        # Добавляем найденные модели
        for model in models:
            builder.row(
                InlineKeyboardButton(
                    text=format_model_name(model),
                    callback_data=f"model:{model}"
                )
            )

    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к категориям",
            callback_data="back_to_categories"
        )
    )

    return builder.as_markup()


async def create_model_actions_keyboard(model: str, user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру с действиями для модели."""
    builder = InlineKeyboardBuilder()

    # Проверяем, находится ли модель в избранном
    is_favorite = model in get_user_favorite_models(user_id)

    # Текущая выбранная модель
    current_model = get_user_model(user_id)
    is_current = model == current_model

    # Добавляем кнопку выбора/текущей модели
    if is_current:
        builder.row(
            InlineKeyboardButton(
                text="✅ Текущая модель",
                callback_data="no_action"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="✅ Выбрать эту модель",
                callback_data=f"select_model:{model}"
            )
        )

    # Добавляем кнопку добавления/удаления из избранного
    if is_favorite:
        builder.row(
            InlineKeyboardButton(
                text="❌ Удалить из избранного",
                callback_data=f"unfavorite:{model}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="⭐ Добавить в избранное",
                callback_data=f"favorite:{model}"
            )
        )

    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад к моделям",
            callback_data="back_to_categories"
        )
    )

    return builder.as_markup()




async def create_temperature_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора значения temperature."""
    builder = InlineKeyboardBuilder()




    # Значения temperature от 0.0 до 1.0 с шагом 0.2
    values = [
        ("0.0 (Наиболее точно)", "0.0"),
        ("0.2 (Точно)", "0.2"),
        ("0.4 (Сбалансировано)", "0.4"),
        ("0.6 (Творчески)", "0.6"),
        ("0.8 (Более творчески)", "0.8"),
        ("1.0 (Максимально творчески)", "1.0")
    ]




    for label, value in values:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"temp:{value}"
            )
        )




    return builder.as_markup()


async def create_thinking_budget_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора значения thinking_budget."""
    builder = InlineKeyboardBuilder()

    # Различные значения thinking_budget
    values = [
        ("Выключено (0)", "0"),
        ("Небольшой (2048)", "2048"),
        ("Средний (4096)", "4096"),
        ("Большой (8192)", "8192"),
        ("Максимальный (16384)", "16384")
    ]

    for label, value in values:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"think:{value}"
            )
        )

    return builder.as_markup()


async def create_history_navigation_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для навигации по истории диалогов."""
    builder = InlineKeyboardBuilder()

    # Кнопки навигации
    if total_pages > 1:
        row = []

        # Кнопка "В начало"
        if current_page > 0:
            row.append(
                InlineKeyboardButton(
                    text="« Первый",
                    callback_data="history:0"
                )
            )

        # Кнопка "Назад"
        if current_page > 0:
            row.append(
                InlineKeyboardButton(
                    text="< Пред.",
                    callback_data=f"history:{current_page-1}"
                )
            )

        # Кнопка "Вперед"
        if current_page < total_pages - 1:
            row.append(
                InlineKeyboardButton(
                    text="След. >",
                    callback_data=f"history:{current_page+1}"
                )
            )

        # Кнопка "В конец"
        if current_page < total_pages - 1:
            row.append(
                InlineKeyboardButton(
                    text="Последний »",
                    callback_data=f"history:{total_pages-1}"
                )
            )

        builder.row(*row)

    # Закрыть историю
    builder.row(
        InlineKeyboardButton(
            text="🔙 Закрыть историю",
            callback_data="close_history"
        )
    )

    return builder.as_markup()




async def get_ai_response(user_id: int, message_text: str, image_data: Optional[str] = None) -> str:
    """Получает ответ от API на основе настроек пользователя."""
    # Извлекаем параметр модели из сообщения, если он есть
    message_text, model_param = extract_model_param(message_text)

    # Используем модель из параметра сообщения или берем из настроек пользователя
    model = model_param if model_param is not None else get_user_model(user_id)

    system_prompt = get_system_prompt(user_id)
    temperature = get_user_temperature(user_id)

    # Извлекаем параметр thinking_budget из сообщения, если он есть
    message_text, thinking_budget_param = extract_thinking_budget_param(message_text)

    # Используем значение из сообщения или берем из настроек пользователя
    thinking_budget = thinking_budget_param if thinking_budget_param is not None else get_user_thinking_budget(user_id)




    # Запускаем непрерывную отправку статуса "печатает"
    stop_event = await start_typing_action(user_id)




    # Проверяем кэш для экономии запросов к API
    cache_key = f"{model}:{message_text}:{temperature}:{thinking_budget}"
    if cache_key in model_cache and time.time() - model_cache[cache_key]["timestamp"] < CONFIG["CACHE_TIMEOUT"]:
        # Останавливаем отправку статуса "печатает"
        await stop_typing_action(user_id)
        return model_cache[cache_key]["response"]




    # Получаем контекст пользователя
    context = get_user_context(user_id)




    # Если контекст пуст, добавляем системное сообщение
    if not context:
        add_to_user_context(user_id, "system", system_prompt)




    # Создаем новое сообщение от пользователя
    user_message = {"role": "user", "content": message_text}




    # Если есть изображение, добавляем его в сообщение
    if image_data:
        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": message_text},
                {"type": "image_url", "image_url": {"url": image_data}}
            ]
        }




    # Добавляем сообщение пользователя в контекст
    add_to_user_context(user_id, "user", message_text)




    # Подготавливаем данные для API
    payload = {
        "model": model,
        "messages": context,
        "temperature": temperature,
        "max_tokens": CONFIG["MAX_TOKENS"]
    }

    # Если указан thinking_budget, добавляем его в запрос
    if thinking_budget > 0:
        payload["thinking_budget"] = thinking_budget




    # Выполняем запрос к API с несколькими попытками
    for attempt in range(CONFIG["RETRY_ATTEMPTS"]):
        try:
            # Используем ThreadPoolExecutor для выполнения запроса в отдельном потоке,
            # чтобы не блокировать основной поток и продолжать отправлять статус "печатает"
            with ThreadPoolExecutor() as executor:
                future = executor.submit(
                    requests.post,
                    f"{CONFIG['API_URL']}/chat/completions",
                    headers={"Authorization": f"Bearer {CONFIG['API_KEY']}"},
                    json=payload,
                    timeout=120  # Увеличиваем таймаут для длинных задач
                )

                # Ожидаем ответа, продолжая отправлять статус "печатает"
                while not future.done():
                    await asyncio.sleep(0.1)

                response = future.result()

            response.raise_for_status()
            data = response.json()




            if 'choices' in data and data['choices']:
                ai_response = data['choices'][0]['message']['content']




                # Кэшируем ответ
                model_cache[cache_key] = {
                    "response": ai_response,
                    "timestamp": time.time()
                }




                # Добавляем ответ в контекст пользователя
                add_to_user_context(user_id, "assistant", ai_response)

                # Останавливаем отправку статуса "печатает"
                await stop_typing_action(user_id)

                return ai_response




        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка: {e}, модель: {model}, попытка {attempt+1}/{CONFIG['RETRY_ATTEMPTS']}")




            # Если это последняя попытка, возвращаем сообщение об ошибке
            if attempt == CONFIG["RETRY_ATTEMPTS"] - 1:
                # Останавливаем отправку статуса "печатает"
                await stop_typing_action(user_id)

                error_message = f"❌ Ошибка при обработке запроса (HTTP {e.response.status_code}). Пожалуйста, попробуйте позже."
                return error_message




            # Переключаемся на другую модель
            current_index = ALL_MODELS.index(model)
            next_index = (current_index + 1) % len(ALL_MODELS)
            model = ALL_MODELS[next_index]
            payload["model"] = model
            logger.info(f"Переключение на модель: {model}")




            # Обновляем полезную нагрузку с новой моделью
            continue

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при запросе к API, модель: {model}, попытка {attempt+1}/{CONFIG['RETRY_ATTEMPTS']}")

            # Если это последняя попытка, возвращаем сообщение об ошибке
            if attempt == CONFIG["RETRY_ATTEMPTS"] - 1:
                # Останавливаем отправку статуса "печатает"
                await stop_typing_action(user_id)

                error_message = "❌ Время ожидания ответа истекло. Возможно, запрос слишком сложный. Попробуйте упростить запрос или использовать параметр --thinking_budget для увеличения времени обработки."
                return error_message

            # Пробуем еще раз
            continue




        except Exception as e:
            logger.error(f"Ошибка при запросе к API: {str(e)}")

            # Останавливаем отправку статуса "печатает"
            await stop_typing_action(user_id)

            return f"❌ Произошла ошибка: {str(e)[:100]}... Пожалуйста, попробуйте позже."




    # Если все попытки не удались
    # Останавливаем отправку статуса "печатает"
    await stop_typing_action(user_id)

    return "❌ Все модели временно недоступны. Пожалуйста, попробуйте позже."




# Обработчики команд и сообщений
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    user_name = message.from_user.first_name




    # Создаем клавиатуру быстрого доступа
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text="🔄 Новый диалог"))
    keyboard.add(KeyboardButton(text="🤖 Выбрать модель"))
    keyboard.add(KeyboardButton(text="📜 История диалогов"))
    keyboard.add(KeyboardButton(text="⚙️ Настройки"))
    keyboard.adjust(2)




    welcome_text = (
        f"👋 Здравствуйте, {user_name}!\n\n"
        f"🤖 Я профессиональный AI-ассистент, работающий на основе передовых языковых моделей.\n\n"
        f"🔍 Я могу помочь вам с:\n"
        f"• Ответами на вопросы и объяснениями\n"
        f"• Написанием и анализом кода\n"
        f"• Созданием и редактированием текстов\n"
        f"• Анализом данных и рассуждениями\n\n"
        f"💡 Просто напишите ваш вопрос или задачу, и я постараюсь помочь!\n\n"
        f"🔤 Для быстрой смены модели, добавьте `--model название` в ваше сообщение."
    )




    await message.answer(
        welcome_text,
        reply_markup=keyboard.as_markup(resize_keyboard=True)
    )




    # Инициализируем настройки пользователя, если их еще нет
    user_id = message.from_user.id
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "model": ALL_MODELS[0],
            "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
            "temperature": CONFIG["TEMPERATURE"],
            "thinking_budget": 0,
            "favorite_models": [],
            "requests_left": 10,
            "last_reset": str(date.today())
        }
        save_user_settings()


@router.message(Command("history"))
async def cmd_history(message: Message, state: FSMContext):
    """Показывает историю диалогов пользователя."""
    user_id = message.from_user.id

    # Устанавливаем состояние просмотра истории
    await state.set_state(UserStates.viewing_history)

    # Получаем и форматируем первую страницу истории
    history_text, current_page, total_pages = await format_history_page(user_id)

    # Создаем клавиатуру навигации
    keyboard = await create_history_navigation_keyboard(current_page, total_pages)

    await message.answer(
        history_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )




@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показывает справку по командам бота."""
    help_text = (
        "🔍 **Справка по командам:**\n\n"
        "/start - Начать общение с ботом\n"
        "/newchat - Начать новый диалог\n"
        "/models - Выбрать AI модель\n"
        "/prompt - Настроить системный промпт\n"
        "/resetprompt - Сбросить системный промпт\n"
        "/temp - Настроить креативность (temperature)\n"
        "/thinking - Настроить бюджет размышлений для сложных задач\n"
        "/history - Просмотр истории диалогов\n"
        "/settings - Показать текущие настройки\n"
        "/help - Показать эту справку\n\n"
        "📝 **Дополнительные параметры в сообщениях:**\n"
        "Можно добавить параметры в сообщение для быстрой настройки:\n"
        "• `--model название` - Использовать указанную модель для этого запроса\n"
        "• `--thinking_budget N` - Использовать бюджет размышлений для сложного запроса\n\n"
        "Примеры:\n"
        "• `Расскажи о квантовой физике --model Llama-3.3-70B-Instruct`\n"
        "• `Реши сложную математическую задачу... --thinking_budget 8192`\n\n"
        "📝 **Форматирование:**\n"
        "Бот поддерживает Markdown для кода и текста:\n"
        "```\n# Заголовок\n**жирный текст**\n*курсив*\n`код`\n```\n"
        "📊 **Отправка изображений:**\n"
        "Вы можете отправить изображение с подписью, и я проанализирую его содержимое."
    )




    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)




@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Показывает текущие настройки пользователя."""
    user_id = message.from_user.id




    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "model": ALL_MODELS[0],
            "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
            "temperature": CONFIG["TEMPERATURE"],
            "thinking_budget": 0,
            "favorite_models": [],
            "requests_left": 10,
            "last_reset": str(date.today())
        }
        save_user_settings()




    settings = user_settings[str(user_id)]
    model = settings.get("model", ALL_MODELS[0])
    system_prompt = settings.get("system_prompt", CONFIG["DEFAULT_SYSTEM_PROMPT"])
    temperature = settings.get("temperature", CONFIG["TEMPERATURE"])
    thinking_budget = settings.get("thinking_budget", 0)
    favorite_models = settings.get("favorite_models", [])




    # Создаем клавиатуру для настроек
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔄 Сменить модель", callback_data="change_model"))
    keyboard.row(InlineKeyboardButton(text="📝 Изменить системный промпт", callback_data="change_prompt"))
    keyboard.row(InlineKeyboardButton(text="🎛️ Настроить креативность", callback_data="change_temp"))
    keyboard.row(InlineKeyboardButton(text="🧠 Настроить бюджет размышлений", callback_data="change_thinking"))
    keyboard.row(InlineKeyboardButton(text="📜 История диалогов", callback_data="view_history"))
    keyboard.row(InlineKeyboardButton(text="🔄 Начать новый диалог", callback_data="new_chat"))


    thinking_budget_text = "Выключен" if thinking_budget == 0 else str(thinking_budget)
    favorite_models_text = "\n".join([f"• {format_model_name(m)}" for m in favorite_models]) if favorite_models else "Нет избранных моделей"

    settings_text = (
        "⚙️ **Текущие настройки:**\n\n"
        f"🤖 **Модель:** `{format_model_name(model)}`\n\n"
        f"🌡️ **Креативность:** `{temperature}`\n\n"
        f"🧠 **Бюджет размышлений:** `{thinking_budget_text}`\n\n"
        f"⭐ **Избранные модели:**\n```\n{favorite_models_text}\n```\n\n"
        f"📝 **Системный промпт:**\n```\n{system_prompt}\n```"
    )




    await message.answer(settings_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard.as_markup())




@router.message(Command("models"))
async def cmd_models(message: Message, state: FSMContext):
    """Показывает список доступных моделей."""
    await state.set_state(UserStates.waiting_for_model_selection)




    await message.answer(
        "📚 Выберите категорию моделей:",
        reply_markup=await create_model_selection_keyboard()
    )


@router.message(Command("thinking"))
async def cmd_thinking(message: Message, state: FSMContext):
    """Позволяет пользователю настроить параметр thinking_budget."""
    await state.set_state(UserStates.waiting_for_thinking_budget)

    current_budget = get_user_thinking_budget(message.from_user.id)
    current_budget_text = "Выключен" if current_budget == 0 else str(current_budget)

    await message.answer(
        f"🧠 Текущий бюджет размышлений: **{current_budget_text}**\n\n"
        "Бюджет размышлений позволяет моделям лучше справляться со сложными задачами, "
        "давая им больше «пространства» для промежуточных вычислений и рассуждений.\n\n"
        "Чем сложнее задача (например, сложные математические вычисления, программирование или логические головоломки), "
        "тем больший бюджет может потребоваться. Однако это может увеличить время генерации ответа.\n\n"
        "Выберите желаемый бюджет размышлений:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=await create_thinking_budget_keyboard()
    )




@router.message(Command("prompt"))
async def cmd_prompt(message: Message, state: FSMContext):
    """Позволяет пользователю задать свой системный промпт."""
    await state.set_state(UserStates.custom_system_prompt)




    current_prompt = get_system_prompt(message.from_user.id)




    await message.answer(
        f"📝 Текущий системный промпт:\n```\n{current_prompt}\n```\n\n"
        "Отправьте новый системный промпт, который будет использоваться в диалоге. "
        "Это инструкции для AI о том, как ему следует отвечать.",
        parse_mode=ParseMode.MARKDOWN
    )




@router.message(Command("resetprompt"))
async def cmd_reset_prompt(message: Message):
    """Сбрасывает системный промпт на значение по умолчанию."""
    user_id = message.from_user.id




    if str(user_id) in user_settings:
        user_settings[str(user_id)]["system_prompt"] = CONFIG["DEFAULT_SYSTEM_PROMPT"]
        save_user_settings()




    # Обновляем контекст пользователя, если он существует
    if user_id in user_contexts:
        # Ищем и обновляем системное сообщение
        for i, msg in enumerate(user_contexts[user_id]):
            if msg["role"] == "system":
                user_contexts[user_id][i]["content"] = CONFIG["DEFAULT_SYSTEM_PROMPT"]
                break
        # Если системного сообщения нет, добавляем его
        else:
            user_contexts[user_id].insert(0, {"role": "system", "content": CONFIG["DEFAULT_SYSTEM_PROMPT"]})




    await message.answer(
        "✅ Системный промпт сброшен на значение по умолчанию.",
        parse_mode=ParseMode.MARKDOWN
    )




@router.message(Command("temp"))
async def cmd_temperature(message: Message, state: FSMContext):
    """Позволяет пользователю настроить параметр temperature."""
    await state.set_state(UserStates.waiting_for_temperature)




    current_temp = get_user_temperature(message.from_user.id)




    await message.answer(
        f"🌡️ Текущее значение креативности (temperature): **{current_temp}**\n\n"
        "Более низкие значения делают ответы более предсказуемыми и точными, "
        "более высокие значения делают ответы более творческими и разнообразными.\n\n"
        "Выберите желаемый уровень креативности:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=await create_temperature_keyboard()
    )




@router.message(Command("newchat"))
async def cmd_new_chat(message: Message):
    """Начинает новый диалог, очищая историю контекста."""
    user_id = message.from_user.id
    clear_user_context(user_id)




    # Добавляем системный промпт в начало нового диалога
    system_prompt = get_system_prompt(user_id)
    add_to_user_context(user_id, "system", system_prompt)




    await message.answer(
        "🔄 Начат новый диалог. Вся предыдущая история очищена.\n"
        "Задайте мне вопрос или опишите, с чем я могу вам помочь."
    )




@router.callback_query(lambda c: c.data == "new_chat")
async def callback_new_chat(callback: CallbackQuery):
    """Обработчик кнопки "Новый диалог"."""
    user_id = callback.from_user.id
    clear_user_context(user_id)




    # Добавляем системный промпт в начало нового диалога
    system_prompt = get_system_prompt(user_id)
    add_to_user_context(user_id, "system", system_prompt)




    await callback.message.answer(
        "🔄 Начат новый диалог. Вся предыдущая история очищена.\n"
        "Задайте мне вопрос или опишите, с чем я могу вам помочь."
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "view_history")
async def callback_view_history(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки просмотра истории диалогов."""
    user_id = callback.from_user.id

    # Устанавливаем состояние просмотра истории
    await state.set_state(UserStates.viewing_history)

    # Получаем и форматируем первую страницу истории
    history_text, current_page, total_pages = await format_history_page(user_id)

    # Создаем клавиатуру навигации
    keyboard = await create_history_navigation_keyboard(current_page, total_pages)

    await callback.message.answer(
        history_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("history:"))
async def callback_history_navigation(callback: CallbackQuery):
    """Обработчик навигации по истории диалогов."""
    user_id = callback.from_user.id
    page = int(callback.data.split(":", 1)[1])

    # Получаем и форматируем запрошенную страницу истории
    history_text, current_page, total_pages = await format_history_page(user_id, page)

    # Создаем клавиатуру навигации
    keyboard = await create_history_navigation_keyboard(current_page, total_pages)

    await callback.message.edit_text(
        history_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "close_history")
async def callback_close_history(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки закрытия истории диалогов."""
    # Сбрасываем состояние
    await state.clear()

    await callback.message.edit_text(
        "📜 Просмотр истории диалогов завершен."
    )
    await callback.answer()




@router.callback_query(lambda c: c.data == "change_model")
async def callback_change_model(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки смены модели."""
    await state.set_state(UserStates.waiting_for_model_selection)




    await callback.message.answer(
        "📚 Выберите категорию моделей:",
        reply_markup=await create_model_selection_keyboard()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "search_model")
async def callback_search_model(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки поиска модели."""
    await state.set_state(UserStates.waiting_for_model_search)

    await callback.message.answer(
        "🔍 Введите часть названия модели для поиска:"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "direct_model")
async def callback_direct_model(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки прямого ввода названия модели."""
    await state.set_state(UserStates.waiting_for_direct_model)

    await callback.message.answer(
        "⌨️ Введите точное название модели (например, Llama-3.3-70B-Instruct):"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "favorite_models")
async def callback_favorite_models(callback: CallbackQuery):
    """Обработчик кнопки просмотра избранных моделей."""
    user_id = callback.from_user.id

    await callback.message.edit_text(
        "⭐ Ваши избранные модели:",
        reply_markup=await create_favorite_models_keyboard(user_id)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "all_models")
async def callback_all_models(callback: CallbackQuery):
    """Обработчик кнопки показа всех моделей."""
    await callback.message.edit_text(
        "📋 Выберите модель из полного списка:",
        reply_markup=await create_all_models_keyboard()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("favorite:"))
async def callback_add_favorite(callback: CallbackQuery):
    """Обработчик добавления модели в избранное."""
    user_id = callback.from_user.id
    model = callback.data.split(":", 1)[1]

    add_to_favorite_models(user_id, model)

    await callback.answer("✅ Модель добавлена в избранное")

    # Обновляем клавиатуру действий с моделью
    await callback.message.edit_reply_markup(
        reply_markup=await create_model_actions_keyboard(model, user_id)
    )


@router.callback_query(lambda c: c.data.startswith("unfavorite:"))
async def callback_remove_favorite(callback: CallbackQuery):
    """Обработчик удаления модели из избранного."""
    user_id = callback.from_user.id
    model = callback.data.split(":", 1)[1]

    remove_from_favorite_models(user_id, model)

    await callback.answer("✅ Модель удалена из избранного")

    # Обновляем клавиатуру действий с моделью
    await callback.message.edit_reply_markup(
        reply_markup=await create_model_actions_keyboard(model, user_id)
    )


@router.message(StateFilter(UserStates.waiting_for_model_search))
async def process_model_search(message: Message, state: FSMContext):
    """Обрабатывает поиск модели по запросу."""
    search_query = message.text.strip()

    if len(search_query) < 2:
        await message.answer(
            "⚠️ Запрос слишком короткий. Введите минимум 2 символа для поиска."
        )
        return

    # Ищем модели по запросу
    search_results = search_models(search_query)

    if not search_results:
        await message.answer(
            f"🔍 По запросу «{search_query}» не найдено моделей. Попробуйте другой запрос или выберите из категорий:",
            reply_markup=await create_model_selection_keyboard()
        )
    else:
        await message.answer(
            f"🔍 Результаты поиска по запросу «{search_query}»:",
            reply_markup=await create_search_results_keyboard(search_results)
        )

    # Сбрасываем состояние
    await state.clear()


@router.message(StateFilter(UserStates.waiting_for_direct_model))
async def process_direct_model(message: Message, state: FSMContext):
    """Обрабатывает прямой ввод названия модели."""
    model_query = message.text.strip()

    # Ищем модель по запросу
    matching_models = []
    for model in ALL_MODELS:
        if model_query.lower() in model.lower():
            matching_models.append(model)

    if not matching_models:
        await message.answer(
            f"❌ Модель с названием «{model_query}» не найдена. Попробуйте другое название или выберите из списка:",
            reply_markup=await create_model_selection_keyboard()
        )
    else:
        # Если нашли несколько моделей, показываем список
        if len(matching_models) > 1:
            await message.answer(
                f"🔍 Найдено несколько моделей по запросу «{model_query}». Выберите одну из них:",
                reply_markup=await create_search_results_keyboard(matching_models)
            )
        else:
            # Если нашли только одну модель, предлагаем действия с ней
            model = matching_models[0]
            await message.answer(
                f"📝 Информация о модели: **{format_model_name(model)}**\n\n"
                f"Выберите действие с этой моделью:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=await create_model_actions_keyboard(model, message.from_user.id)
            )

    # Сбрасываем состояние
    await state.clear()


@router.callback_query(lambda c: c.data.startswith("select_model:"))
async def callback_select_actual_model(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора модели для использования."""
    user_id = callback.from_user.id
    model = callback.data.split(":", 1)[1]

    # Сохраняем выбранную модель в настройках пользователя
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
            "temperature": CONFIG["TEMPERATURE"],
            "thinking_budget": 0,
            "favorite_models": []
        }

    user_settings[str(user_id)]["model"] = model
    save_user_settings()

    # Возвращаемся к нормальному состоянию
    await state.clear()

    # Обновляем текст сообщения
    await callback.message.edit_text(
        f"✅ Модель успешно изменена на: **{format_model_name(model)}**\n\n"
        "Теперь вы можете задать мне любой вопрос!",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer("Модель установлена!")




@router.callback_query(lambda c: c.data == "change_prompt")
async def callback_change_prompt(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки изменения системного промпта."""
    await state.set_state(UserStates.custom_system_prompt)




    current_prompt = get_system_prompt(callback.from_user.id)




    await callback.message.answer(
        f"📝 Текущий системный промпт:\n```\n{current_prompt}\n```\n\n"
        "Отправьте новый системный промпт, который будет использоваться в диалоге. "
        "Это инструкции для AI о том, как ему следует отвечать.",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "change_thinking")
async def callback_change_thinking(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки изменения бюджета размышлений."""
    await state.set_state(UserStates.waiting_for_thinking_budget)

    current_budget = get_user_thinking_budget(callback.from_user.id)
    current_budget_text = "Выключен" if current_budget == 0 else str(current_budget)

    await callback.message.answer(
        f"🧠 Текущий бюджет размышлений: **{current_budget_text}**\n\n"
        "Бюджет размышлений позволяет моделям лучше справляться со сложными задачами, "
        "давая им больше «пространства» для промежуточных вычислений и рассуждений.\n\n"
        "Чем сложнее задача (например, сложные математические вычисления, программирование или логические головоломки), "
        "тем больший бюджет может потребоваться. Однако это может увеличить время генерации ответа.\n\n"
        "Выберите желаемый бюджет размышлений:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=await create_thinking_budget_keyboard()
    )
    await callback.answer()




@router.callback_query(lambda c: c.data == "change_temp")
async def callback_change_temp(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки изменения температуры."""
    await state.set_state(UserStates.waiting_for_temperature)




    current_temp = get_user_temperature(callback.from_user.id)




    await callback.message.answer(
        f"🌡️ Текущее значение креативности (temperature): **{current_temp}**\n\n"
        "Более низкие значения делают ответы более предсказуемыми и точными, "
        "более высокие значения делают ответы более творческими и разнообразными.\n\n"
        "Выберите желаемый уровень креативности:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=await create_temperature_keyboard()
    )
    await callback.answer()




@router.callback_query(lambda c: c.data.startswith("category:"))
async def callback_select_category(callback: CallbackQuery):
    """Обработчик выбора категории моделей."""
    category = callback.data.split(":", 1)[1]




    await callback.message.edit_text(
        f"📚 Выберите модель из категории «{category}»:",
        reply_markup=await create_category_models_keyboard(category)
    )
    await callback.answer()




@router.callback_query(lambda c: c.data == "back_to_categories")
async def callback_back_to_categories(callback: CallbackQuery):
    """Обработчик кнопки "Назад к категориям"."""
    await callback.message.edit_text(
        "📚 Выберите категорию моделей:",
        reply_markup=await create_model_selection_keyboard()
    )
    await callback.answer()




@router.callback_query(lambda c: c.data.startswith("model:"))
async def callback_select_model(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора модели."""
    user_id = callback.from_user.id
    model = callback.data.split(":", 1)[1]

    # Показываем информацию о модели и действия с ней
    await callback.message.edit_text(
        f"📝 Информация о модели: **{format_model_name(model)}**\n\n"
        f"Выберите действие с этой моделью:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=await create_model_actions_keyboard(model, user_id)
    )
    await callback.answer()




@router.callback_query(lambda c: c.data.startswith("temp:"))
async def callback_select_temperature(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора значения temperature."""
    user_id = callback.from_user.id
    temperature = float(callback.data.split(":", 1)[1])




    # Сохраняем выбранное значение temperature
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "model": ALL_MODELS[0],
            "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
            "thinking_budget": 0,
            "favorite_models": []
        }




    user_settings[str(user_id)]["temperature"] = temperature
    save_user_settings()




    # Возвращаемся к нормальному состоянию
    await state.clear()




    await callback.message.edit_text(
        f"✅ Значение креативности успешно изменено на: **{temperature}**\n\n"
        "Теперь вы можете продолжить диалог!",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer("Настройка сохранена!")


@router.callback_query(lambda c: c.data.startswith("think:"))
async def callback_select_thinking_budget(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора значения thinking_budget."""
    user_id = callback.from_user.id
    thinking_budget = int(callback.data.split(":", 1)[1])

    # Сохраняем выбранное значение thinking_budget
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "model": ALL_MODELS[0],
            "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
            "temperature": CONFIG["TEMPERATURE"],
            "favorite_models": []
        }

    user_settings[str(user_id)]["thinking_budget"] = thinking_budget
    save_user_settings()

    # Возвращаемся к нормальному состоянию
    await state.clear()

    thinking_budget_text = "выключен" if thinking_budget == 0 else str(thinking_budget)

    await callback.message.edit_text(
        f"✅ Бюджет размышлений успешно изменен на: **{thinking_budget_text}**\n\n"
        "Теперь вы можете продолжить диалог!",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer("Настройка сохранена!")


@router.callback_query(lambda c: c.data == "no_action")
async def callback_no_action(callback: CallbackQuery):
    """Обработчик пустой кнопки без действия."""
    await callback.answer("Нет доступных действий")




@router.message(StateFilter(UserStates.custom_system_prompt))
async def process_custom_prompt(message: Message, state: FSMContext):
    """Обрабатывает ввод пользовательского системного промпта."""
    user_id = message.from_user.id
    new_prompt = message.text




    # Проверяем, что промпт не пустой
    if not new_prompt or len(new_prompt) < 5:
        await message.answer(
            "❌ Промпт слишком короткий. Пожалуйста, введите более подробный системный промпт."
        )
        return




    # Сохраняем промпт в настройках
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = {
            "model": ALL_MODELS[0],
            "temperature": CONFIG["TEMPERATURE"],
            "thinking_budget": 0,
            "favorite_models": []
        }




    user_settings[str(user_id)]["system_prompt"] = new_prompt
    save_user_settings()




    # Обновляем контекст пользователя
    if user_id in user_contexts:
        # Ищем и обновляем системное сообщение
        for i, msg in enumerate(user_contexts[user_id]):
            if msg["role"] == "system":
                user_contexts[user_id][i]["content"] = new_prompt
                break
        # Если системного сообщения нет, добавляем его
        else:
            user_contexts[user_id].insert(0, {"role": "system", "content": new_prompt})
    else:
        # Создаем новый контекст с системным промптом
        user_contexts[user_id] = [{"role": "system", "content": new_prompt}]




    # Возвращаемся к нормальному состоянию
    await state.clear()




    await message.answer(
        "✅ Системный промпт успешно изменен!\n\n"
        "Теперь вы можете продолжить диалог с учетом новых инструкций."
    )




@router.message(F.text == "🔄 Новый диалог")
async def handle_new_chat_button(message: Message):
    """Обработчик кнопки "Новый диалог" на клавиатуре."""
    user_id = message.from_user.id
    clear_user_context(user_id)




    # Добавляем системный промпт в начало нового диалога
    system_prompt = get_system_prompt(user_id)
    add_to_user_context(user_id, "system", system_prompt)




    await message.answer(
        "🔄 Начат новый диалог. Вся предыдущая история очищена.\n"
        "Задайте мне вопрос или опишите, с чем я могу вам помочь."
    )


@router.message(F.text == "📜 История диалогов")
async def handle_history_button(message: Message, state: FSMContext):
    """Обработчик кнопки "История диалогов" на клавиатуре."""
    # Просто вызываем существующий обработчик команды /history
    await cmd_history(message, state)


@router.message(F.text == "🤖 Выбрать модель")
async def handle_models_button(message: Message, state: FSMContext):
    """Обработчик кнопки "Выбрать модель" на клавиатуре."""
    # Просто вызываем существующий обработчик команды /models
    await cmd_models(message, state)


@router.message(F.text == "⚙️ Настройки")
async def handle_settings_button(message: Message):
    """Обработчик кнопки "Настройки" на клавиатуре."""
    # Просто вызываем существующий обработчик команды /settings
    await cmd_settings(message)




@router.message(F.photo)
async def handle_photo(message: Message):
    """Обрабатывает сообщения с фотографиями."""
    user_id = message.from_user.id




    # Получаем фото наилучшего качества
    photo = message.photo[-1]




    # Получаем подпись к фото или используем дефолтный текст
    caption = message.caption or "Что на этом изображении?"




    # Проверяем, поддерживает ли текущая модель анализ изображений
    current_model = get_user_model(user_id)
    supports_vision = any(vision_model in current_model for vision_model in ["Vision", "VL", "vision"])




    if not supports_vision:
        # Автоматически переключимся на модель с поддержкой изображений
        vision_models = MODEL_CATEGORIES["С возможностью анализа изображений"]
        if vision_models:
            new_model = vision_models[0]




            # Сохраняем предыдущую модель для возврата
            if str(user_id) not in user_settings:
                user_settings[str(user_id)] = {
                    "system_prompt": CONFIG["DEFAULT_SYSTEM_PROMPT"],
                    "temperature": CONFIG["TEMPERATURE"],
                    "thinking_budget": 0,
                    "favorite_models": []
                }




            # Запоминаем предыдущую модель
            previous_model = user_settings[str(user_id)].get("model", ALL_MODELS[0])
            user_settings[str(user_id)]["previous_model"] = previous_model




            # Устанавливаем модель с поддержкой изображений
            user_settings[str(user_id)]["model"] = new_model
            save_user_settings()




            await message.answer(
                f"🔄 Временно переключаюсь на модель с поддержкой анализа изображений: "
                f"**{format_model_name(new_model)}**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.answer(
                "❌ Текущая модель не поддерживает анализ изображений, и нет доступных моделей с такой функциональностью."
            )
            return




    # Запускаем непрерывную отправку статуса "печатает"
    stop_event = await start_typing_action(user_id)




    # Обрабатываем изображение
    image_data = await process_image(photo)




    if not image_data:
        # Останавливаем отправку статуса "печатает"
        await stop_typing_action(user_id)

        await message.answer(
            "❌ Не удалось обработать изображение. Убедитесь, что оно в формате JPG, JPEG, PNG или WEBP "
            "и его размер не превышает 10 МБ."
        )
        return




    # Получаем ответ от AI (непрерывная отправка статуса "печатает" обрабатывается внутри функции)
    ai_response = await get_ai_response(user_id, caption, image_data)




    # Если временно переключили модель, возвращаемся к предыдущей
    if not supports_vision and str(user_id) in user_settings and "previous_model" in user_settings[str(user_id)]:
        previous_model = user_settings[str(user_id)]["previous_model"]
        user_settings[str(user_id)]["model"] = previous_model
        del user_settings[str(user_id)]["previous_model"]
        save_user_settings()




        # Отправляем ответ
        await split_and_send_message(message, ai_response)




        await message.answer(
            f"🔄 Вернулся к предыдущей модели: **{format_model_name(previous_model)}**",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Отправляем ответ
        await split_and_send_message(message, ai_response)




@router.message()
async def handle_message(message: Message, state: FSMContext):
    """Обрабатывает все остальные текстовые сообщения."""
    # Проверяем, не является ли сообщение простым приветствием
    greeting_response = is_greeting(message.text)
    if greeting_response:
        await message.answer(greeting_response)
        return




    user_id = str(message.from_user.id)




    # Проверяем и обновляем количество запросов
    if message.from_user.username == "qqq5599":
        pass  # Безлимит
    else:
        today = date.today().strftime("%Y-%m-%d")
        if user_settings[user_id]["last_reset"] != today:
            user_settings[user_id]["requests_left"] = 10
            user_settings[user_id]["last_reset"] = today
            save_user_settings()




        if user_settings[user_id]["requests_left"] <= 0:
            await message.answer("❌ Лимит запросов на сегодня исчерпан. Пожалуйста, попробуйте завтра.")
            return




        user_settings[user_id]["requests_left"] -= 1
        save_user_settings()




    # Запускаем непрерывную отправку статуса "печатает"
    stop_event = await start_typing_action(int(user_id))




    # Получаем ответ от AI
    ai_response = await get_ai_response(int(user_id), message.text)




    # Отправляем ответ с разбивкой на части при необходимости
    await split_and_send_message(message, ai_response)




# Функция инициализации и запуска бота
async def main():
    """Инициализация и запуск бота."""
    # Загружаем настройки пользователей
    load_user_settings()

    # Загружаем историю диалогов
    load_user_history()




    # Очищаем веб-хуки и запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)




    # Выводим информацию о запуске
    logger.info(f"Бот запущен! Используется {len(ALL_MODELS)} моделей.")




    # Запускаем бота
    await dp.start_polling(bot)




if __name__ == "__main__":
    # Запускаем бота в асинхронном режиме
    asyncio.run(main())
