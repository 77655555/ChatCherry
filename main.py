import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from config import TELEGRAM_TOKEN, ALLOWED_USER_ID
from utils import ask_openrouter
from key_manager import get_next_key

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher()

# Память сообщений (словарь)
user_memory = {}

# Команда /start
@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Отправь мне сообщение, и я отвечу через OpenRouter!")

# Команда /help
@dp.message(commands=["help"])
async def cmd_help(message: types.Message):
    await message.answer("Просто напиши мне текст, голосовое или отправь документ — я обработаю всё!")

# Команда /reset
@dp.message(commands=["reset"])
async def cmd_reset(message: types.Message):
    user_memory.pop(message.from_user.id, None)
    await message.answer("История диалога очищена.")

# Обработка текстовых сообщений
@dp.message()
async def handle_message(message: types.Message):
    if message.from_user.id != ALLOWED_USER_ID:
        await message.answer("Извините, доступ запрещен.")
        return

    text = message.text
    if not text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    # Получение истории пользователя
    history = user_memory.get(message.from_user.id, [])
    history.append({"role": "user", "content": text})

    try:
        response_text = await ask_openrouter(history)
        history.append({"role": "assistant", "content": response_text})
        user_memory[message.from_user.id] = history[-10:]  # Оставляем последние 10 сообщений
        await message.answer(response_text)
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        await message.answer("Произошла ошибка при обращении к OpenRouter.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
