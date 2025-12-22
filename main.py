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
TOKEN = "8566730754:AAEz4B5Zqz5fTVpbsSJu8saMoS4yoFsa1QM"   # <--- ВСТАВЬ ТОКЕН
ADMIN_ID = 959119542           # <--- ТВОЙ ID
WHITELIST_IDS = [959119542, 7918250010, 7029781826]    # <--- ТВОЙ ID
DATA_FILE = "users_db.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 2. ВЕБ-СЕРВЕР
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot v6.3 (Names fixed) is running!"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        print(f"Server Error: {e}")

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
# 4. КОМАНДЫ АДМИНА
# ==========================================
@bot.message_handler(commands=['getfile'])
def send_file(message):
    if message.chat.type == 'private' and message.from_user.id == ADMIN_ID:
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "rb") as file:
                    bot.send_document(message.chat.id, file, caption="📂 База данных")
            else:
                bot.send_message(message.chat.id, "База пуста.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.message_handler(commands=['list'])
def list_users(message):
    if message.chat.type == 'private' and message.from_user.id == ADMIN_ID:
        users = load_users()
        bot.send_message(message.chat.id, f"Всего в базе: {len(users)} чел.")

@bot.message_handler(content_types=['document'])
def restore_backup(message):
    if message.chat.type == 'private' and message.from_user.id == ADMIN_ID:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            with open(DATA_FILE, 'wb') as new_file:
                new_file.write(downloaded_file)
            bot.reply_to(message, "✅ База восстановлена!")
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: {e}")

# ==========================================
# 5. ГЛАВНАЯ ЛОГИКА
# ==========================================
@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_messages(message):
    try:
        if not message.from_user or message.from_user.is_bot:
            return

        user_id = message.from_user.id
        # --- ИСПРАВЛЕНИЕ: ВОЗВРАЩАЕМ ИМЯ ---
        username = message.from_user.username
        if not username:
            username = message.from_user.first_name # Если нет ника, берем имя
            
        chat_type = message.chat.type
        
        text_content = ""
        if message.text:
            text_content = message.text.lower()
        elif message.caption:
            text_content = message.caption.lower()

        # 1. Сохраняем, если пишут в группе
        if chat_type in ['group', 'supergroup']:
            is_new = save_new_user(user_id)
            if is_new:
                try:
                    # Теперь пишем имя и ID
                    bot.send_message(ADMIN_ID, f"🔔 Новый: @{username} (ID: {user_id}) из чата {message.chat.title}")
                except:
                    pass

        # 2. Обработка @all / /all
        triggers = ['@all', '/all']
        
        if any(t in text_content for t in triggers):
            
            can_tag = False
            if user_id in WHITELIST_IDS:
                can_tag = True
            else:
                try:
                    mem = bot.get_chat_member(message.chat.id, user_id)
                    if mem.status in ['creator', 'administrator']:
                        can_tag = True
                except:
                    can_tag = False
            
            if not can_tag:
                return

            users = load_users()
            if not users:
                bot.reply_to(message, "Список пуст.")
                return

            bot.reply_to(message, "📢 <b>Внимание всем!</b>", parse_mode='HTML')

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
        logger.error(f"Error in handler: {e}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
