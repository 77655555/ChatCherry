import os

# Токен Telegram-бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ID разрешённого пользователя (ваш ID)
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", 9995599))

# Ваши ключи OpenRouter через запятую
OPENROUTER_KEYS = os.getenv("OPENROUTER_KEYS", "").split(",")
