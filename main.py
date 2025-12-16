import telebot
import os
import time
import logging
from flask import Flask
from threading import Thread

# ==========================================
# 1. НАСТРОЙКИ (ВСТАВЬ СВОИ ДАННЫЕ!)
# ==========================================
TOKEN = "8566730754:AAEz4B5Zqz5fTVpbsSJu8saMoS4yoFsa1QM"  # <-- Твой токен
WHITELIST_IDS = [959119542]       # <-- Твой ID
USERS_FILE = "users_list.txt"

# Настройка логирования (чтобы видеть ошибки в консоли)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 2. ВЕБ-СЕРВЕР (ЧТОБЫ UPTIMEROBOT ВИДЕЛ НАС)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "I'm alive! Бот работает и ждет команд."

def run():
    # Запускаем сервер на порту 8080
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        print(f"Ошибка веб-сервера: {e}")

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# 3. ФУНКЦИИ БОТА
# ==========================================
def load_users():
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_user(user_id):
    users = load_users()
    if str(user_id) not in users:
        with open(USERS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{user_id}\n")

def can_tag(chat_id, user_id):
    if user_id in WHITELIST_IDS:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if member.status in ['creator', 'administrator']:
            return True
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
    return False

# ==========================================
# 4. ОБРАБОТКА СООБЩЕНИЙ
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        # 1. Запоминаем ID
        if message.from_user and not message.from_user.is_bot:
            save_user(message.from_user.id)

        # 2. Проверяем команду
        text = message.text.lower() if message.text else ""
        if text in ['/all', '@all', '/everyone', 'все сюда']:
            chat_id = message.chat.id
            user_id = message.from_user.id

            if not can_tag(chat_id, user_id):
                bot.reply_to(message, "❌ У вас нет прав отмечать всех.")
                return

            users = load_users()
            if not users:
                bot.reply_to(message, "🤷‍♂️ Я пока никого не запомнил.")
                return

            bot.reply_to(message, "📢 Вызываю всех:")

            chunk = ""
            count = 0
            for uid in users:
                chunk += f"[🔔](tg://user?id={uid}) "
                count += 1
                if count % 5 == 0:
                    bot.send_message(chat_id, chunk, parse_mode="Markdown")
                    chunk = ""

            if chunk:
                bot.send_message(chat_id, chunk, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка в обработчике: {e}")

# ==========================================
# 5. ГЛАВНЫЙ ЗАПУСК (БЕССМЕРТНЫЙ РЕЖИМ)
# ==========================================

if __name__ == "__main__":
    # Запускаем веб-сервер в фоновом режиме
    keep_alive()

    # Бесконечный цикл перезапуска бота
    while True:
        try:
            print("🤖 Бот запускается...")
            bot.infinity_polling(timeout=60, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Бот упал с ошибкой: {e}")
            print("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)
