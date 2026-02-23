import telebot
import os
import time
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from threading import Thread

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
TOKEN = "8566730754:AAEz4B5Zqz5fTVpbsSJu8saMoS4yoFsa1QM"   # <--- ВСТАВЬ НОВЫЙ ТОКЕН!
ADMIN_ID = 959119542           # <--- ТВОЙ ID
WHITELIST_IDS = [959119542, 7918250010, 7029781826]    # <--- ID тех, кто может тегать
SHEET_URL = "https://docs.google.com/spreadsheets/d/18z6dhYd72WpOLKN_-Mgxl6paR8ptxDaOuhUHtutFL6w/edit?hl=ru&gid=0#gid=0" # <--- ВСТАВЬ ССЫЛКУ ИЗ БРАУЗЕРА

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 2. ПОДКЛЮЧЕНИЕ К GOOGLE ТАБЛИЦАМ
# ==========================================
# Файл credentials.json Render подтянет автоматически из Secret Files
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# Открываем таблицу по ссылке и берем первый лист
sheet = client.open_by_url(SHEET_URL).sheet1

# ==========================================
# 3. ВЕБ-СЕРВЕР (Для Cron-Job)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot v8.0 (Google Sheets) is running!"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.error(f"Server Error: {e}")

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# 4. ФУНКЦИИ БАЗЫ ДАННЫХ (GOOGLE SHEETS)
# ==========================================
def load_users():
    """Загружает список ID из первого столбца таблицы"""
    try:
        records = sheet.col_values(1)
        users = []
        for r in records:
            if r.isdigit(): # Игнорируем заголовок 'user_id' и пустые строки
                users.append(int(r))
        return users
    except Exception as e:
        logger.error(f"Ошибка чтения таблицы: {e}")
        return []

def save_new_user(user_id):
    """Сохраняет нового юзера прямо в таблицу"""
    try:
        users = load_users()
        if user_id not in users:
            sheet.append_row([user_id])
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка записи в таблицу: {e}")
        return False

# ==========================================
# 5. АДМИНСКИЕ КОМАНДЫ
# ==========================================
@bot.message_handler(commands=['list'])
def list_users(message):
    if message.chat.type == 'private' and message.from_user.id == ADMIN_ID:
        users = load_users()
        bot.send_message(message.chat.id, f"📊 Всего в таблице: {len(users)} чел.")

# ==========================================
# 6. ГЛАВНАЯ ЛОГИКА (@all)
# ==========================================
@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_messages(message):
    try:
        if not message.from_user or message.from_user.is_bot:
            return

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        chat_type = message.chat.type
        
        text_content = ""
        if message.text:
            text_content = message.text.lower()
        elif message.caption:
            text_content = message.caption.lower()

        # --- 1. СОХРАНЕНИЕ ---
        if chat_type in ['group', 'supergroup']:
            is_new = save_new_user(user_id)
            if is_new:
                try:
                    bot.send_message(ADMIN_ID, f"🔔 Новый: @{username} (ID: {user_id}) из {message.chat.title}\n💾 Записан в Google Таблицу!")
                except:
                    pass

        # --- 2. ОБРАБОТКА @all / /all ---
        triggers = ['@all', '/all']
        
        if any(t in text_content for t in triggers):
            
            # Проверка прав
            can_tag = False
            if user_id in WHITELIST_IDS:
                can_tag = True
            else:
                try:
                    mem = bot.get_chat_member(message.chat.id, user_id)
                    if mem.status in ['creator', 'administrator']:
                        can_tag = True
                except:
                    pass
            
            if not can_tag:
                return

            users = load_users()
            if not users:
                try:
                    bot.reply_to(message, "Список пуст.")
                except:
                    bot.send_message(message.chat.id, "Список пуст.")
                return

            try:
                bot.reply_to(message, "📢 <b>Внимание всем!</b>", parse_mode='HTML')
            except:
                bot.send_message(message.chat.id, "📢 <b>Внимание всем!</b>", parse_mode='HTML')

            chunk = ""
            count = 0
            for uid in users:
                # Используем надежный HTML
                chunk += f'<a href="tg://user?id={uid}">🔔</a> '
                count += 1
                if count % 5 == 0:
                    try:
                        bot.send_message(message.chat.id, chunk, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка отправки тегов: {e}")
                    chunk = ""
                    
                    # СПАСИТЕЛЬНАЯ ПАУЗА: защищает от бана Telegram за спам (ошибка 429)
                    time.sleep(1.5) 
            
            if chunk:
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Ошибка отправки остатка тегов: {e}")

    except Exception as e:
        logger.error(f"CRITICAL ERROR in handler: {e}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
