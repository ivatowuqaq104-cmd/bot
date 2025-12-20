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
TOKEN = "ТВОЙ_ТОКЕН_ЗДЕСЬ"
ADMIN_ID = 959119542          # Твой ID (Главный админ бота)
WHITELIST_IDS = [959119542]   # ID тех, кому можно ВСЁ (даже если не админ в чате)
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
    return "Bot v6.0 (Admins Allowed) is running!"

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
# 4. СЛУЖЕБНЫЕ КОМАНДЫ (ТОЛЬКО ДЛЯ ТЕБЯ)
# ==========================================

# --- СКАЧАТЬ БАЗУ (/getfile) ---
@bot.message_handler(commands=['getfile'])
def send_file(message):
    if message.chat.type != 'private' or message.from_user.id != ADMIN_ID:
        return
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "rb") as file:
                bot.send_document(message.chat.id, file, caption="📂 Резервная копия базы")
        else:
            bot.send_message(message.chat.id, "База пуста.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

# --- ВОССТАНОВИТЬ БАЗУ (Файлом) ---
@bot.message_handler(content_types=['document'])
def restore_backup(message):
    if message.chat.type != 'private' or message.from_user.id != ADMIN_ID:
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(DATA_FILE, 'wb') as new_file:
            new_file.write(downloaded_file)
        bot.reply_to(message, "✅ База восстановлена!")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# --- СПИСОК ИМЕН (/list) ---
@bot.message_handler(commands=['list'])
def list_users(message):
    if message.chat.type != 'private' or message.from_user.id != ADMIN_ID:
        return
    users = load_users()
    text_report = f"Список ({len(users)} чел):\n"
    for uid in users:
        text_report += f"ID: {uid}\n"
    if len(text_report) > 4000:
        bot.send_message(message.chat.id, text_report[:4000])
    else:
        bot.send_message(message.chat.id, text_report)

# ==========================================
# 5. ГЛАВНАЯ ЛОГИКА
# ==========================================
@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_messages(message):
    try:
        if not message.from_user or message.from_user.is_bot:
            return

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        chat_type = message.chat.type
        # Безопасно получаем текст (даже если это картинка с подписью)
        text = message.text.lower() if message.text else (message.caption.lower() if message.caption else "")

        # --- 1. СОХРАНЕНИЕ (ТОЛЬКО В ГРУППАХ) ---
        if chat_type in ['group', 'supergroup']:
            is_new = save_new_user(user_id)
            if is_new:
                try:
                    bot.send_message(ADMIN_ID, f"🔔 Новый: {username} (ID: {user_id}) в {message.chat.title}")
                except:
                    pass

        # --- 2. КОМАНДА @all ---
        triggers = ['@all', '/all', 'everyone', 'все сюда']
        
        if text and any(t in text for t in triggers):
            
            # === ПРОВЕРКА ПРАВ (НОВАЯ) ===
            can_tag = False
            
            # А. Если ты в белом списке
            if user_id in WHITELIST_IDS:
                can_tag = True
            # Б. Если ты Админ или Создатель чата
            else:
                try:
                    chat_member = bot.get_chat_member(message.chat.id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        can_tag = True
                except Exception as e:
                    logger.error(f"Не смог проверить права: {e}")
            
            # Если прав нет — выходим
            if not can_tag:
                return 

            # Если права есть — погнали
            users = load_users()
            if not users:
                bot.reply_to(message, "Список пуст.")
                return

            bot.reply_to(message, "📢 <b>Внимание Альянс!</b>", parse_mode='HTML')

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
