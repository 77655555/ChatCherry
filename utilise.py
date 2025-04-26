import aiohttp
from config import get_next_key

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

async def ask_openrouter(messages):
    api_key = get_next_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_API_URL, headers=headers, json=payload) as resp:
            if resp.status != 200:
                raise Exception(f"Ошибка OpenRouter: {resp.status}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]
