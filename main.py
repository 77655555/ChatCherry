import os
import random
import logging
import time
import json
import openai
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiohttp import ClientSession
import asyncio

# API ключи для OpenRouter (самые мощные бесплатные)
keys = [
    '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',  # Пример ключа 1
    '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',  # Пример ключа 2
    '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',  # Пример ключа 3
    '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',  # Пример ключа 4
    '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',  # Пример ключа 5
]

# Установка ключа Telegram бота
TOKEN = '7560419901:AAFNKVipqHgUZIuFrN3bqPKyGDXf9r4NZAM'
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Логгирование ошибок
logging.basicConfig(level=logging.INFO)

# Переменные
memory = {}

# Функция для получения ответа от OpenRouter
async def get_openai_response(message: str, key: str):
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
        }
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": message}],
        }
        async with ClientSession() as session:
            async with session.post('https://openrouter.ai/api/v1/chat/completions', json=payload, headers=headers) as response:
                data = await response.json()
                if response.status == 200 and 'choices' in data:
                    return data['choices'][0]['message']['content']
                else:
                    raise Exception("Error in OpenRouter response")
    except Exception as e:
        print(f"Error in get_openai_response: {e}")
        return None

# Функция для обработки сообщений и переключения ключей
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text

    # Показ уведомления о принятии сообщения
    await message.answer("🎓 Ваш вопрос принят в обработку... Пожалуйста, подождите пару секунд.")

    # Проверка истории сообщений
    if user_id not in memory:
        memory[user_id] = []

    # Добавление сообщения в память
    memory[user_id].append(user_text)
    if len(memory[user_id]) > 5:  # Храним последние 5 сообщений
        memory[user_id].pop(0)

    # Выбор случайного ключа из списка (для переключения нейросетей)
    current_key = random.choice(keys)
    
    # Получение ответа от OpenRouter с использованием выбранного ключа
    response = await get_openai_response(user_text, current_key)

    # Если ответ получен
    if response:
        # Отправляем ответ пользователю
        await message.answer(response, parse_mode=ParseMode.MARKDOWN)
    else:
        # Если ошибка, сообщаем пользователю
        await message.answer("Извините, произошла ошибка при обработке вашего запроса.")

# Функция для обработки команды /help
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    help_text = (
        "Привет! Я бот, который может помочь вам с решением задач, тестов, программированием и многим другим.\n"
        "Просто напишите мне ваш запрос, и я постараюсь дать ответ.\n\n"
        "Команды:\n"
        "/help - помощь\n"
        "/reset - сброс памяти\n"
    )
    await message.answer(help_text)

# Функция для обработки команды /reset (сброс памяти)
@dp.message_handler(commands=['reset'])
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    if user_id in memory:
        del memory[user_id]
    await message.answer("🎓 Ваша память была сброшена!")

# Основная функция запуска
async def on_start():
    print("Bot is running...")

if __name__ == '__main__':
    # Запуск бота
    loop = asyncio.get_event_loop()
    loop.create_task(on_start())
    executor.start_polling(dp, skip_updates=True)
