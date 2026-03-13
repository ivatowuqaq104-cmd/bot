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
# На Render лучше добавь TOKEN в Environment Variables, чтобы не светить в коде
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_НОВЫЙ_ТОКЕН") 
ADMIN_ID = 959119542
WHITELIST_IDS = [959119542, 7918250010, 7029781826]
SHEET_URL = "https://docs.google.com/spreadsheets/d/18z6dhYd72WpOLKN_-Mgxl6paR8ptxDaOuhUHtutFL6w/edit?hl=ru&gid=0#gid=0"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# Локальный кэш пользователей, чтобы не дергать таблицу каждую секунду
cached_users = set()

# ==========================================
# 2. ПОДКЛЮЧЕНИЕ К GOOGLE ТАБЛИЦАМ
# ==========================================
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL).sheet1

# ==========================================
# 4. ФУНКЦИИ БАЗЫ ДАННЫХ
# ==========================================
def sync_users():
    """Синхронизирует локальный кэш с таблицей при запуске"""
    global cached_users
    try:
        records = sheet.col_values(1)
        cached_users = {int(r) for r in records if r.isdigit()}
        logger.info(f"✅ База синхронизирована: {len(cached_users)} юзеров")
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")

def save_new_user(user_id):
    """Сохраняет в кэш и таблицу только если юзера там нет"""
    global cached_users
    if user_id not in cached_users:
        try:
            sheet.append_row([user_id])
            cached_users.add(user_id)
            return True
        except Exception as e:
            logger.error(f"Ошибка записи: {e}")
    return False

# ==========================================
# 3. ВЕБ-СЕРВЕР (Для Render/UptimeRobot)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run, daemon=True).start()

# ==========================================
# 6. ГЛАВНАЯ ЛОГИКА
# ==========================================
@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_messages(message):
    if not message.from_user or message.from_user.is_bot:
        return

    user_id = message.from_user.id
    chat_type = message.chat.type
    
    # 1. Быстрое сохранение нового юзера
    if chat_type in ['group', 'supergroup']:
        if save_new_user(user_id):
            try:
                bot.send_message(ADMIN_ID, f"🔔 Новый юзер: {user_id}")
            except: pass

    # 2. Обработка тега @all
    text = (message.text or message.caption or "").lower()
    if '@all' in text or '/all' in text:
        # Проверка прав (админ или белый список)
        is_admin = False
        if user_id in WHITELIST_IDS:
            is_admin = True
        else:
            try:
                member = bot.get_chat_member(message.chat.id, user_id)
                if member.status in ['creator', 'administrator']:
                    is_admin = True
            except: pass

        if not is_admin: return

        if not cached_users:
            bot.reply_to(message, "Список пуст.")
            return

        bot.send_message(message.chat.id, "📢 <b>Внимание всем!</b>", parse_mode='HTML')

        # Рассылка тегов пачками по 5 штук
        users_list = list(cached_users)
        for i in range(0, len(users_list), 5):
            chunk = users_list[i:i+5]
            mentions = " ".join([f'<a href="tg://user?id={uid}">🔔</a>' for uid in chunk])
            try:
                bot.send_message(message.chat.id, mentions, parse_mode="HTML")
                time.sleep(1.0) # Защита от Flood Limit
            except Exception as e:
                logger.error(f"Ошибка тега: {e}")

if __name__ == "__main__":
    sync_users() # Загружаем базу один раз при старте
    keep_alive()
    # Увеличиваем таймауты для стабильности на Render
    bot.infinity_polling(timeout=90, long_polling_timeout=20, logger_level=logging.INFO)
