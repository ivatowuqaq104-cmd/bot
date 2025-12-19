import telebot
import os
import time
import logging
import json
from flask import Flask
from threading import Thread

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
TOKEN = "8566730754:AAEz4B5Zqz5fTVpbsSJu8saMoS4yoFsa1QM"
ADMIN_ID = 959119542          # Твой ID
WHITELIST_IDS = [959119542]   # Кто может тегать всех
DATA_FILE = "users_db.json"   # Файл базы

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 2. ВЕБ-СЕРВЕР
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        print(f"Server error: {e}")

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# 3. ФУНКЦИИ БАЗЫ ДАННЫХ
# ==========================================
def load_users():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("users", [])
    except:
        return []

def save_new_user(user_id):
    """Сохраняет юзера и возвращает True, если он новенький."""
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"users": users}, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Save error: {e}")
    return False

# ==========================================
# 4. КОМАНДА /getfile (ТОЛЬКО ЛИЧКА)
# ==========================================
@bot.message_handler(commands=['getfile'])
def send_file(message):
    # Игнорируем команды в общих чатах
    if message.chat.type != 'private':
        return

    # Проверяем, что пишет Админ
    if message.from_user.id != ADMIN_ID:
        return

    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "rb") as file:
                bot.send_document(message.chat.id, file, caption="📂 Список участников чата")
        else:
            bot.send_message(message.chat.id, "База пуста.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

# ==========================================
# 5. ГЛАВНАЯ ЛОГИКА
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    try:
        if not message.from_user or message.from_user.is_bot:
            return

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        chat_type = message.chat.type
        text = message.text.lower() if message.text else ""

        # --- ЛОГИКА 1: СОХРАНЕНИЕ (ТОЛЬКО ИЗ ГРУПП) ---
        # Мы сохраняем человека, ТОЛЬКО если сообщение пришло из группы
        if chat_type in ['group', 'supergroup']:
            is_new = save_new_user(user_id)
            
            if is_new:
                # Уведомляем админа, что в ГРУППЕ появился новый активный игрок
                try:
                    alert = (f"🔔 <b>Новый игрок в чате!</b>\n"
                             f"Кто: @{username}\nID: <code>{user_id}</code>")
                    bot.send_message(ADMIN_ID, alert, parse_mode='HTML')
                except:
                    pass
        
        # Если пишут в личку (private) - мы просто игнорируем сохранение.
        # (Ничего не делаем, база не засоряется)

        # --- ЛОГИКА 2: ОБРАБОТКА @all ---
        triggers = ['@all', '/all', 'everyone', 'все сюда']
        
        if any(t in text for t in triggers):
            
            # Проверяем права
            if user_id not in WHITELIST_IDS:
                return

            users = load_users()
            if not users:
                bot.reply_to(message, "Список участников пуст.")
                return

            bot.reply_to(message, "📢 <b>Внимание Альянс!</b>", parse_mode='HTML')

            # Рассылка скрытых тегов
            chunk = ""
            count = 0
            for uid in users:
                chunk += f"[🔔](tg://user?id={uid}) "
                count += 1
                if count % 5 == 0:
                    bot.send_message(message.chat.id, chunk, parse_mode="Markdown")
                    chunk = ""
            
            if chunk:
                bot.send_message(message.chat.id, chunk, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
