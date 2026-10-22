import os
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    LabeledPrice, PreCheckoutQuery
)
from flask import Flask, request

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8800276454:AAF0QTpC9CcvbchTY_bE01BAm1uKvIyPyCQ" 
RATE_USD = 0.0106      # Курс за 1 звезду в долларах
USD_TO_RUB = 85.0      # Курс доллара к рублю

# Настройки для Webhook (Render)
WEBHOOK_HOST = os.getenv("WEBHOOK_URL", "https://giftbot-kbx9.onrender.com")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ================= КЛАВИАТУРЫ =================
def get_main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🕶 Товары Telegram", callback_data="catalog"))
    markup.row(InlineKeyboardButton("🤝 Продать NFT", callback_data="sell_nft"))
    markup.row(InlineKeyboardButton("🕹 Игры", callback_data="games"))
    markup.row(
        InlineKeyboardButton("🧢 Пополнить баланс", callback_data="topup"),
        InlineKeyboardButton("👺 Профиль", callback_data="profile")
    )
    markup.row(
        InlineKeyboardButton("👨‍💻 Поддержка", callback_data="support"),
        InlineKeyboardButton("👤 Топ клиентов", callback_data="top_clients")
    )
    markup.row(InlineKeyboardButton("🧑‍💻 Создать своего бота", callback_data="create_bot"))
    markup.row(InlineKeyboardButton("🧐 Отзывы", callback_data="reviews"))
    return markup

def get_catalog_menu():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🌟 Купить звезды", callback_data="buy_stars"),
        InlineKeyboardButton("💳 Продать звезды", callback_data="sell_stars")
    )
    markup.row(InlineKeyboardButton("🔮 Премиум", callback_data="buy_premium"))
    markup.row(
        InlineKeyboardButton("🧸 Купить обычный", callback_data="buy_gift"),
        InlineKeyboardButton("🐸 NFT", callback_data="nft_menu")
    )
    markup.row(InlineKeyboardButton("💎 TON", callback_data="ton_menu"))
    markup.row(InlineKeyboardButton("« Назад", callback_data="back_to_menu"))
    return markup

def get_topup_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🏳️ СБП #1", callback_data="topup_stub"))
    markup.row(InlineKeyboardButton("🏳️ СБП #2", callback_data="topup_stub"))
    markup.row(InlineKeyboardButton("💳 Карты РФ #1", callback_data="topup_stub"))
    markup.row(InlineKeyboardButton("🐦 CryptoBot", callback_data="topup_stub"))
    markup.row(InlineKeyboardButton("🚀 xRocket", callback_data="topup_stub"))
    markup.row(InlineKeyboardButton("🪙 Криптовалюта", callback_data="topup_stub"))
    markup.row(InlineKeyboardButton("💎 Прямой перевод", callback_data="topup_stub"))
    markup.row(InlineKeyboardButton("« Назад", callback_data="back_to_menu"))
    return markup

def get_profile_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📜 История покупок", callback_data="stub"))
    markup.row(InlineKeyboardButton("🎫 Активировать промокод", callback_data="stub"))
    markup.row(InlineKeyboardButton("👥 Реферальная система", callback_data="stub"))
    markup.row(InlineKeyboardButton("🧮 Калькулятор", callback_data="stub"))
    markup.row(InlineKeyboardButton("ℹ️ Информация", callback_data="stub"))
    markup.row(InlineKeyboardButton("🔌 API", callback_data="stub"))
    markup.row(InlineKeyboardButton("💸 Вывести реф. баланс", callback_data="stub"))
    markup.row(InlineKeyboardButton("« В меню", callback_data="back_to_menu"))
    return markup

def get_support_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📝 Создать тикет", callback_data="create_ticket"))
    markup.row(InlineKeyboardButton("« В меню", callback_data="back_to_menu"))
    return markup

# ================= ОБРАБОТЧИКИ КОМАНД =================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    text = (
        "👋 <b>Добро пожаловать в HeiseyStars!</b>\n\n"
        "Мы поможем Вам приобрести Telegram звёзды по минимальной цене.\n\n"
        "Заказы отправляются автоматически и, как правило, приходят в течение 15 секунд.\n\n"
        "Приятных покупок ✌️"
    )
    bot.send_message(message.chat.id, text, reply_markup=get_main_menu())

# ================= ОБРАБОТЧИКИ КНОПОК (CALLBACK) =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "back_to_menu":
        bot.edit_message_text("👋 <b>Главное меню</b>", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
    
    elif call.data == "catalog":
        text = "🌟 <b>Покупка Telegram Stars</b>\n\n• Цена Telegram Stars: 1.5₽/шт.\n\nНажмите кнопку ниже для покупки\n👇"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_catalog_menu())
    
    # --- ПРОДАЖА ЗВЕЗД (ЗДЕСЬ БУДЕТ ОФИЦИАЛЬНАЯ ОПЛАТА) ---
    elif call.data == "sell_stars":
        text = (
            "💳 <b>Продажа звёзд</b>\n\n"
            f"• Цена за 1 звезду: {RATE_USD}$.\n\n"
            "🔍 Введите количество звёзд для продажи (минимум 100 звёзд):"
        )
        # Создаем кнопку "Назад" для этого шага
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("« Назад", callback_data="catalog"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.register_next_step_handler(call.message, process_sell_stars)
    
    # --- ПОКУПКА ЗВЕЗД ---
    elif call.data == "buy_stars":
        bot.edit_message_text(
            "🌟 <b>Покупка звезд</b>\n\nВведите количество звезд (мин. 50):", 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=InlineKeyboardMarkup().row(InlineKeyboardButton("« Назад", callback_data="catalog"))
        )
        bot.register_next_step_handler(call.message, process_buy_stars)
    
    elif call.data == "topup":
        text = "💳 <b>Пополнение баланса</b>\n\nВыберите удобный способ пополнения:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_topup_menu())
    
    elif call.data == "profile":
        user = call.from_user
        username = f"@{user.username}" if user.username else "Нет"
        text = (
            "👤 <b>Профиль</b>\n\n"
            f"🆔 ID: <code>{user.id}</code>;\n"
            f"📝 Username: {username}.\n\n"
            "💰 Баланс: 0₽;\n└ Общий депозит: 0₽.\n\n"
            "📦 Заказы:\n├ Всего заказов: 0;\n├ Выполнено: 0;\n├ В обработке: 0;\n"
            "├ Арендовано NFT-подарков: 0 шт. (~0₽);\n├ Арендовано NFT-username: 0 шт. (~0₽);\n"
            "├ Куплено подарков: 0 шт. (~0₽);\n└ Всего куплено звёзд: 0 шт. (~0₽).\n\n"
            "📅 Регистрация: 22.10.2026."
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_profile_menu())
    
    elif call.data == "support":
        text = (
            "📞 <b>Техническая поддержка</b>\n\n"
            "В этом разделе Вы можете создать тикет для связи с поддержкой.\n\n"
            "📊 <b>Статистика:</b>\n• Активных тикетов: 0\n\n"
            "✅ Вы можете создать новый тикет для обращения в поддержку."
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_support_menu())
    
    elif call.data == "create_ticket":
        bot.edit_message_text("Напишите ваш вопрос одним сообщением:", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(call.message, process_ticket)
    
    elif call.data == "sell_history":
        bot.answer_callback_query(call.id, "История продаж пуста.", show_alert=True)
    
    elif call.data in ["buy_premium", "buy_gift", "nft_menu", "ton_menu", "games", "top_clients", "create_bot", "reviews", "sell_nft", "stub", "topup_stub"]:
        bot.answer_callback_query(call.id, "Раздел в разработке 🛠", show_alert=True)

# ================= ШАГИ (ВВОД ТЕКСТА) =================
def process_sell_stars(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "Пожалуйста, введите число (например, 100).")
        return
    amount = int(message.text)
    if amount < 100:
        bot.send_message(message.chat.id, "Минимальное количество для продажи — 100 звёзд.")
        return
    
    # Считаем сумму к выплате в рублях
    total_usd = amount * RATE_USD
    total_rub = int(total_usd * USD_TO_RUB)
    
    # Отправляем официальный счет от Telegram на оплату нужного количества звезд
    bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Продажа {amount} Stars",
        description=f"Перевод {amount} звезд боту. К выплате: {total_rub} ₽",
        invoice_payload=f"sell_{amount}_{total_rub}", # Сохраняем сумму к выплате в payload
        provider_token="", 
        currency="XTR", 
        prices=[LabeledPrice(label=f"{amount} Stars", amount=amount)]
    )

def process_buy_stars(message):
    if not message.text.isdigit() or int(message.text) < 50:
        bot.send_message(message.chat.id, "Введите число от 50.")
        return
    amount = int(message.text)
    
    bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Покупка {amount} Stars",
        description=f"Покупка {amount} звезд.",
        invoice_payload=f"buy_{amount}_{message.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} Stars", amount=amount)]
    )

def process_ticket(message):
    bot.send_message(message.chat.id, "✅ <b>Тикет создан!</b>\nВаше обращение зарегистрировано.", reply_markup=get_support_menu())

# ================= ОПЛАТА ЗВЕЗДАМИ =================
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    # Обязательно разрешаем оплату
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    # Проверяем, что это была продажа звезд
    if payload.startswith("sell_"):
        parts = payload.split("_")
        amount = int(parts[1])
        payout_rub = int(parts[2])
        
        bot.send_message(
            message.chat.id, 
            f"✅ <b>Успешно!</b>\n\n"
            f"Вы продали <b>{amount} ⭐</b>.\n"
            f"На ваш баланс зачислено: <b>{payout_rub} ₽</b>.",
            reply_markup=get_catalog_menu()
        )
    else:
        bot.send_message(
            message.chat.id, 
            f"✅ <b>Оплата получена!</b>\nКуплено: {payment.total_amount} ⭐",
            reply_markup=get_catalog_menu()
        )

# ================= НАСТРОЙКА FLASK ДЛЯ RENDER =================
@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return '', 403

bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
