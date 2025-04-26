from config import OPENROUTER_KEYS

# Индекс текущего ключа
current_index = 0

def get_next_key():
    global current_index
    if not OPENROUTER_KEYS:
        raise Exception("Нет доступных API-ключей для OpenRouter.")
    key = OPENROUTER_KEYS[current_index]
    current_index = (current_index + 1) % len(OPENROUTER_KEYS)
    return key
