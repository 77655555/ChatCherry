import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ChatAction
from aiogram.types import ReplyKeyboardRemove

# Конфигурация
API_URL = "https://api.intelligence.io.solutions/api/v1"
TOKEN = "7839597384:AAFlm4v3qcudhJfiFfshz1HW6xpKhtqlV5g"
API_KEY = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6ImJlMjYwYjFhLWI0OWMtNDU2MC04ODZiLTMwYTBmMGFlNGZlNSIsImV4cCI6NDg5OTUwNTM1M30.Et777QmMZrknZ3dvxqiBClOrbkZV4SkUDfvOz21lys2hoyZs4oV_RFClBNyux3W03ikZFlwu2sKngFYqJU3b8Q"
MODELS = [
    'meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8',
    'Qwen/QwQ-32B',
    'meta-llama/Llama-3.2-90B-Vision-Instruct',
    'deepseek-ai/DeepSeek-R1-Distill-Llama-70B',
    'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B',
    'meta-llama/Llama-3.3-70B-Instruct',
    'Qwen/Qwen2-VL-7B-Instruct',
    'databricks/dbrx-instruct',
    'mistralai/Ministral-8B-Instruct-2410',
    'netease-youdao/Confucius-01-14B',
    'nvidia/AceMath-7B-Instruct',
    'google/gemma-3-27b-it',
    'neuralmagic/Llama-3.1-Nemotron-70B-Instruct-HF-FP8-dynamic',
    'mistralai/Mistral-Large-Instruct-2411',
    'microsoft/phi-4',
    'SentientAGI/Dobby-Mini-Unhinged-Llama-3.1-8B',
    'watt-ai/watt-tool-70B',
    'bespokelabs/Bespoke-Stratos-32B',
    'NovaSky-AI/Sky-T1-32B-Preview',
    'tiiuae/Falcon3-10B-Instruct',
    'THUDM/glm-4-9b-chat',
    'Qwen/Qwen2.5-Coder-32B-Instruct',
    'CohereForAI/aya-expanse-326',
    'jinaai/ReaderLM-v2',
    'openbmb/MiniCPM3-4B',
    'Qwen/Qwen2.5-1.5B-Instruct',
    'ozone-ai/ox-1',
    'microsoft/Phi-3.5-mini-instruct',
    'ibm-granite/granite-3.1-8b-instruct'
]

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN)
dp = Dispatcher()
current_model_index = 0

async def show_typing(chat_id: int):
    """Активация индикатора набора текста"""
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1.5)

def rotate_model():
    """Переключение на следующую модель"""
    global current_model_index
    current_model_index = (current_model_index + 1) % len(MODELS)
    logger.info(f"Переключено на модель: {MODELS[current_model_index]}")

async def send_response(message: types.Message, text: str):
    """Отправка ответа с разбивкой на части"""
    for chunk in [text[i:i+4090] for i in range(0, len(text), 4090)]:
        await message.answer(chunk, parse_mode=None)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "🤖 Профессиональный AI-ассистент готов к работе.\n"
        "Отправьте ваш технический запрос для получения полного ответа.",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Command("models"))
async def cmd_models(message: types.Message):
    """Показать список доступных моделей"""
    models_list = "\n".join([f"▫️ {model.split('/')[-1]}" for model in MODELS])
    await message.answer(
        f"📚 Доступные модели ({len(MODELS)}):\n{models_list}\n\n"
        f"Текущая модель: {MODELS[current_model_index].split('/')[-1]}"
    )

@dp.message()
async def handle_message(message: types.Message):
    """Обработка пользовательских сообщений"""
    global current_model_index

    # Активация индикатора печати
    await show_typing(message.chat.id)

    for attempt in range(len(MODELS)):
        current_model = MODELS[current_model_index]
        payload = {
            "model": current_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Предоставь полный ответ с кодом и пояснениями. Сохраняй оригинальное форматирование."
                },
                {
                    "role": "user", 
                    "content": f"{message.text}\n\nВключи весь код полностью без сокращений."
                }
            ],
            "temperature": 0.2,
            "max_tokens": 4000
        }

        try:
            response = requests.post(
                f"{API_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if 'choices' in data and data['choices']:
                await send_response(message, data['choices'][0]['message']['content'])
                return

        except requests.exceptions.HTTPError as e:
            logger.error(f"Ошибка {e.response.status_code} | Модель: {current_model}")
            rotate_model()
            await show_typing(message.chat.id)
            continue

        except Exception as e:
            logger.error(f"Критическая ошибка: {str(e)}")
            rotate_model()
            continue

    await message.answer("🚨 Все модели временно недоступны. Попробуйте позже.")

async def main():
    """Запуск бота"""
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
