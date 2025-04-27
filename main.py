import os
import logging
import asyncio
import sqlite3
import random
import requests
import socket
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import openai
from io import BytesIO
import qrcode

# ===== КОНФИГУРАЦИЯ =====
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # Ваш ID чата для уведомлений

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY

# ===== БАЗА ДАННЫХ =====
DB_NAME = "bot_database.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # Пользователи
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 100)''')
        # Мониторинг сервисов
        c.execute('''CREATE TABLE IF NOT EXISTS services
                     (id INTEGER PRIMARY KEY, name TEXT, url TEXT, last_status TEXT)''')
        conn.commit()

init_db()

# ===== УТИЛИТЫ =====
async def is_admin(update: Update):
    return update.effective_user.id == int(ADMIN_CHAT_ID)

# ===== ФУНКЦИИ UPTIME =====
async def ping_service(url: str) -> float:
    try:
        start_time = datetime.now()
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: socket.create_connection((url, 80), 5)
            ), 
            timeout=5
        )
        return (datetime.now() - start_time).total_seconds() * 1000
    except:
        return -1

async def auto_monitor(context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT url FROM services")
        services = c.fetchall()
        
        for service in services:
            latency = await ping_service(service[0])
            status = "🟢 ONLINE" if latency != -1 else "🔴 OFFLINE"
            
            c.execute("UPDATE services SET last_status = ? WHERE url = ?", 
                      (status, service[0]))
            
            if latency == -1:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"🚨 SERVICE DOWN: {service[0]}"
                )

# ===== КОМАНДЫ БОТА =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)",
                    (user.id, user.username))
        conn.commit()
    
    await update.message.reply_html(
        f"🚀 Привет, {user.mention_html()}!\n"
        "Доступные команды:\n"
        "/ping <url> - Проверить доступность\n"
        "/monitor_add <url> - Добавить в мониторинг\n"
        "/status - Статус всех сервисов\n"
        "/gpt <текст> - ChatGPT\n"
        "/weather <город> - Погода\n"
        "/qr <текст> - Генератор QR-кода\n"
        "/admin - Админ-панель"
    )

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Укажите URL: /ping google.com")
        return
    
    url = args[0]
    latency = await ping_service(url)
    
    if latency == -1:
        await update.message.reply_text(f"🔴 {url} недоступен!")
    else:
        await update.message.reply_text(f"🟢 {url} - {latency:.2f} мс")

async def cmd_monitor_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("❌ Только для админов!")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /monitor_add <имя> <url>")
        return
    
    name, url = args[0], args[1]
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO services (name, url) VALUES (?, ?)", (name, url))
        conn.commit()
    
    await update.message.reply_text(f"✅ Сервис {name} добавлен в мониторинг")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, url, last_status FROM services")
        services = c.fetchall()
    
    response = "📊 Статус сервисов:\n\n" + "\n".join(
        [f"{s[0]} ({s[1]}): {s[2]}" for s in services]
    )
    await update.message.reply_text(response)

# ===== ДОП. ФУНКЦИИ =====
async def cmd_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Напишите запрос: /gpt Как работает Вселенная?")
        return
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        await update.message.reply_text(response.choices[0].message['content'])
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args)
    if not city:
        await update.message.reply_text("Укажите город: /weather Москва")
        return
    
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url).json()
    
    if response.get("cod") != 200:
        await update.message.reply_text("🚫 Город не найден")
    else:
        weather_desc = response['weather'][0]['description'].capitalize()
        temp = response['main']['temp']
        await update.message.reply_text(
            f"🌍 {city}\n"
            f"🌡 {temp}°C\n"
            f"☁️ {weather_desc}"
        )

async def cmd_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Введите текст: /qr Hello World")
        return
    
    img = qrcode.make(text)
    bio = BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    
    await update.message.reply_photo(photo=InputFile(bio))

# ===== ЗАПУСК =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Планировщик для авто-мониторинга
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_monitor, 'interval', minutes=5, args=[app])
    scheduler.start()
    
    # Обработчики команд
    handlers = [
        CommandHandler("start", start),
        CommandHandler("ping", cmd_ping),
        CommandHandler("monitor_add", cmd_monitor_add),
        CommandHandler("status", cmd_status),
        CommandHandler("gpt", cmd_gpt),
        CommandHandler("weather", cmd_weather),
        CommandHandler("qr", cmd_qr),
    ]
    
    for handler in handlers:
        app.add_handler(handler)
    
    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
