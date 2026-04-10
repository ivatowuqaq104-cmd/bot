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
# ВАЖНО: Смени токен в BotFather и вставь новый здесь или в Environment Variables на Render
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_НОВЫЙ_ТОКЕН") 
ADMIN_ID = 959119542
WHITELIST_IDS = [959119542, 7918250010, 7029781826]
SHEET_URL = "https://docs.google.com/spreadsheets/d/18z6dhYd72WpOLKN_-Mgxl6paR8ptxDaOuhUHtutFL6w/edit?hl=ru&gid=0#gid=0"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)
cached_users = set()

# ==========================================
# 2. ПОДКЛЮЧЕНИЕ К GOOGLE ТАБЛИЦАМ
# ==========================================
def get_sheet():
    """Создает подключение к таблице с жестким таймаутом"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        client.request_timeout = 15 # Не ждем ответа от Google дольше 15 секунд
        return client.open_by_url(SHEET_URL).sheet1
    except Exception as e:
        logger.error(f"Ошибка подключения к таблице: {e}")
        return None

# Инициализируем объект листа
sheet = get_sheet()

# ==========================================
# 3. ФУНКЦИИ БАЗЫ ДАННЫХ (С ПОВТОРАМИ)
# ==========================================
def sync_users():
    """Загружает ID из таблицы в кэш при старте"""
    global cached_users, sheet
    try:
        if not sheet: sheet = get_sheet()
        if sheet:
            records = sheet.col_values(1)
            cached_users = {int(r) for r in records if r.isdigit()}
            logger.info(f"✅ База синхронизирована: {len(cached_users)} юзеров")
    except Exception as e:
        logger.error(f"Ошибка начальной синхронизации: {e}")

def _async_save_with_retry(user_id):
    """Фоновая функция записи с 3 попытками (чтобы не вешать бота)"""
    global sheet
    max_retries = 3
    delay = 5 # Пауза между попытками

    for attempt in range(1, max_retries + 1):
        try:
            if not sheet: sheet = get_sheet()
            if sheet:
                sheet.append_row([user_id])
                logger.info(f"✅ Юзер {user_id} сохранен в таблицу (попытка {attempt})")
                return # Успех — выходим
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt} для {user_id} не удалась: {e}")
            if attempt < max_retries:
                time.sleep(delay)
            else:
                logger.error(f"❌ КРИТИЧЕСКИЙ СБОЙ: Юзер {user_id} не сохранен после {max_retries} попыток")

def save_new_user(user_id):
    """Проверяет кэш и запускает фоновую запись"""
    global cached_users
    if user_id not in cached_users:
        cached_users.add(user_id) # Добавляем в память мгновенно
        # Запускаем запись в фоновом потоке
        Thread(target=_async_save_with_retry, args=(user_id,), daemon=True).start()
        return True
    return False

# ==========================================
# 4. ВЕБ-СЕРВЕР (Для UptimeRobot)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot LABERY v10.0 is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# ==========================================
# 5. ЛОГИКА БОТА
# ==========================================
@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_messages(message):
    try:
        if not message.from_user or message.from_user.is_bot:
            return

        user_id = message.from_user.id
        chat_type = message.chat.type
        
        # 1. Мгновенная проверка и фоновое сохранение
        if chat_type in ['group', 'supergroup']:
            if save_new_user(user_id):
                try:
                    bot.send_message(ADMIN_ID, f"🔔 Новый пользователь: {user_id}")
                except: pass

        # 2. Обработка команды тега
        text = (message.text or message.caption or "").lower()
        if '@all' in text or '/all' in text:
            # Проверка прав (Белый список или Админ группы)
            is_allowed = user_id in WHITELIST_IDS
            if not is_allowed:
                try:
                    member = bot.get_chat_member(message.chat.id, user_id)
                    is_allowed = member.status in ['creator', 'administrator']
                except: pass

            if is_allowed:
                if not cached_users:
                    bot.reply_to(message, "Список пуст.")
                    return

                bot.send_message(message.chat.id, "📢 <b>Внимание всем!</b>", parse_mode='HTML')
                
                users_list = list(cached_users)
                for i in range(0, len(users_list), 5):
                    chunk = users_list[i:i+5]
                    mentions = " ".join([f'<a href="tg://user?id={uid}">🔔</a>' for uid in chunk])
                    try:
                        bot.send_message(message.chat.id, mentions, parse_mode="HTML")
                        time.sleep(1.2) # Защита от спам-фильтра Telegram
                    except: continue

    except Exception as e:
        logger.error(f"Ошибка в основном обработчике: {e}")

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    sync_users()   # 1. Грузим базу
    keep_alive()   # 2. Запускаем Flask для пингов
    logger.info("Бот запущен и готов к работе")
    
    # infinity_polling с длинными таймаутами для стабильности на Render
    bot.infinity_polling(timeout=90, long_polling_timeout=20)
