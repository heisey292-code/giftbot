import asyncio
import logging
import datetime
import os
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, 
    PreCheckoutQuery, SuccessfulPayment, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8800276454:AAF0QTpC9CcvbchTY_bE01BAm1uKvIyPyCQ"  # ОБЯЗАТЕЛЬНО ЗАМЕНИ НА СВОЙ ТОКЕН!
RATE_USD = 0.0106 

# Настройки для Webhook
WEBHOOK_HOST = os.getenv("WEBHOOK_URL", "https://giftbot-kbx9.onrender.com") # Твой URL из Render
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

class UserFlow(StatesGroup):
    buy_stars_input = State()
    sell_stars_input = State()
    support_ticket = State()

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def send_photo_or_text(call_or_msg, photo_name, text, reply_markup):
    """Пытается отправить фото, если его нет - отправляет текст."""
    try:
        photo = FSInputFile(photo_name)
        if isinstance(call_or_msg, CallbackQuery):
            asyncio.create_task(call_or_msg.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup))
            asyncio.create_task(call_or_msg.message.delete())
        else:
            asyncio.create_task(call_or_msg.answer_photo(photo=photo, caption=text, reply_markup=reply_markup))
    except Exception:
        if isinstance(call_or_msg, CallbackQuery):
            asyncio.create_task(call_or_msg.message.edit_text(text, reply_markup=reply_markup))
        else:
            asyncio.create_task(call_or_msg.answer(text, reply_markup=reply_markup))

# ================= КЛАВИАТУРЫ =================
def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🕶 Товары Telegram", callback_data="catalog")
    builder.button(text="🤝 Продать NFT", callback_data="sell_nft")
    builder.button(text="🕹 Игры", callback_data="games")
    builder.button(text="🧢 Пополнить баланс", callback_data="topup")
    builder.button(text="👺 Профиль", callback_data="profile")
    builder.button(text="👨‍💻 Поддержка", callback_data="support")
    builder.button(text="👤 Топ клиентов", callback_data="top_clients")
    builder.button(text="🧑‍💻 Создать своего бота", callback_data="create_bot")
    builder.button(text="🧐 Отзывы", callback_data="reviews")
    builder.adjust(1, 1, 1, 2, 2, 1, 1)
    return builder.as_markup()

def get_catalog_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🌟 Купить звезды", callback_data="buy_stars")
    builder.button(text="💳 Продать звезды", callback_data="sell_stars")
    builder.button(text="🔮 Премиум", callback_data="buy_premium")
    builder.button(text="🧸 Купить обычный", callback_data="buy_gift")
    builder.button(text="🐸 NFT", callback_data="nft_menu")
    builder.button(text="💎 TON", callback_data="ton_menu")
    builder.button(text="« Назад", callback_data="back_to_menu")
    builder.adjust(2, 1, 2, 1, 1)
    return builder.as_markup()

def get_back_to_catalog():
    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад", callback_data="catalog")
    return builder.as_markup()

def get_sell_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 История", callback_data="sell_history")
    builder.button(text="« Назад", callback_data="catalog")
    builder.adjust(1, 1)
    return builder.as_markup()

def get_topup_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏳️ СБП #1", callback_data="topup_stub")
    builder.button(text="🏳️ СБП #2", callback_data="topup_stub")
    builder.button(text="💳 Карты РФ #1", callback_data="topup_stub")
    builder.button(text="🐦 CryptoBot", callback_data="topup_stub")
    builder.button(text="🚀 xRocket", callback_data="topup_stub")
    builder.button(text="🪙 Криптовалюта", callback_data="topup_stub")
    builder.button(text="💎 Прямой перевод", callback_data="topup_stub")
    builder.button(text="« Назад", callback_data="back_to_menu")
    builder.adjust(1, 1, 1, 1, 1, 1, 1, 1)
    return builder.as_markup()

def get_profile_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 История покупок", callback_data="stub")
    builder.button(text="🎫 Активировать промокод", callback_data="stub")
    builder.button(text="👥 Реферальная система", callback_data="stub")
    builder.button(text="🧮 Калькулятор", callback_data="stub")
    builder.button(text="ℹ️ Информация", callback_data="stub")
    builder.button(text="🔌 API", callback_data="stub")
    builder.button(text="💸 Вывести реф. баланс", callback_data="stub")
    builder.button(text="« В меню", callback_data="back_to_menu")
    builder.adjust(1, 1, 1, 1, 1, 1, 1, 1)
    return builder.as_markup()

def get_support_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать тикет", callback_data="create_ticket")
    builder.button(text="« В меню", callback_data="back_to_menu")
    builder.adjust(1, 1)
    return builder.as_markup()

# ================= ОБРАБОТЧИКИ =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "👋 <b>Добро пожаловать в KryptonStars!</b>\n\n"
        "Мы поможем Вам приобрести Telegram звёзды по минимальной цене.\n\n"
        "Заказы отправляются автоматически и, как правило, приходят в течение 15 секунд.\n\n"
        "Приятных покупок ✌️"
    )
    send_photo_or_text(message, "menu.jpg", text, get_main_menu())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    send_photo_or_text(call, "menu.jpg", "👋 <b>Главное меню</b>", get_main_menu())
    await call.answer()

@dp.callback_query(F.data == "catalog")
async def open_catalog(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🌟 <b>Покупка Telegram Stars</b>\n\n"
        "• Цена Telegram Stars: 1.5₽/шт.\n\n"
        "Нажмите кнопку ниже для покупки\n👇"
    )
    send_photo_or_text(call, "buy.jpg", text, get_catalog_menu())
    await call.answer()

@dp.callback_query(F.data == "sell_stars")
async def prompt_sell_stars(call: CallbackQuery, state: FSMContext):
    text = (
        "💳 <b>Продажа звёзд</b>\n\n"
        f"• Цена за 1 звезду: {RATE_USD}$.\n\n"
        "🔍 Введите количество звёзд для продажи (минимум 100 звёзд):"
    )
    send_photo_or_text(call, "sell.jpg", text, get_sell_menu())
    await state.set_state(UserFlow.sell_stars_input)
    await call.answer()

@dp.message(UserFlow.sell_stars_input)
async def process_sell_stars(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (например, 100).")
        return
    amount = int(message.text)
    if amount < 100:
        await message.answer("Минимальное количество для продажи — 100 звёзд.")
        return

    total_usd = round(amount * RATE_USD, 2)
    await state.clear()
    
    text = (
        f"✅ <b>Заявка на продажу {amount} ⭐ создана!</b>\n\n"
        f"К выплате: <b>{total_usd}$</b>\n\n"
        f"Отправьте <b>{amount} звёзд</b> нашему боту и нажмите кнопку ниже."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я отправил(а) звёзды", callback_data="confirm_sell")
    builder.button(text="« Назад", callback_data="catalog")
    builder.adjust(1, 1)
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "confirm_sell")
async def confirm_sell(call: CallbackQuery):
    await call.message.edit_text("⏳ Проверяем транзакцию...", reply_markup=get_sell_menu())
    await call.answer()

@dp.callback_query(F.data == "sell_history")
async def sell_history(call: CallbackQuery):
    await call.answer("История продаж пуста.", show_alert=True)

@dp.callback_query(F.data == "buy_stars")
async def prompt_buy_stars(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🌟 <b>Покупка звезд</b>\n\nВведите количество звезд (мин. 50):",
        reply_markup=get_back_to_catalog()
    )
    await state.set_state(UserFlow.buy_stars_input)
    await call.answer()

@dp.message(UserFlow.buy_stars_input)
async def process_buy_stars(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 50:
        await message.answer("Введите число от 50.")
        return
    amount = int(message.text)
    await state.clear()
    
    await message.answer_invoice(
        title=f"Покупка {amount} Stars",
        description=f"Покупка {amount} звезд.",
        payload=f"buy_{amount}_{message.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} Stars", amount=amount)],
        provider_token=""
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: Message):
    await message.answer(
        f"✅ Оплата получена!\nКуплено: {message.successful_payment.total_amount} ⭐",
        reply_markup=get_catalog_menu()
    )

@dp.callback_query(F.data == "topup")
async def open_topup(call: CallbackQuery):
    text = "💳 <b>Пополнение баланса</b>\n\nВыберите удобный способ пополнения:"
    send_photo_or_text(call, "topup.jpg", text, get_topup_menu())
    await call.answer()

@dp.callback_query(F.data == "topup_stub")
async def topup_stub(call: CallbackQuery):
    await call.answer("Этот способ оплаты временно недоступен.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def open_profile(call: CallbackQuery):
    user = call.from_user
    username = f"@{user.username}" if user.username else "Нет"
    reg_date = datetime.datetime.now().strftime("%d.%m.%Y\n%H:%M")
    
    text = (
        "👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>;\n"
        f"📝 Username: {username}.\n\n"
        "💰 Баланс: 0₽;\n└ Общий депозит: 0₽.\n\n"
        "📦 Заказы:\n├ Всего заказов: 0;\n├ Выполнено: 0;\n├ В обработке: 0;\n"
        "├ Арендовано NFT-подарков: 0 шт. (~0₽);\n├ Арендовано NFT-username: 0 шт. (~0₽);\n"
        "├ Куплено подарков: 0 шт. (~0₽);\n└ Всего куплено звёзд: 0 шт. (~0₽).\n\n"
        f"📅 Регистрация: {reg_date}."
    )
    send_photo_or_text(call, "profile.jpg", text, get_profile_menu())
    await call.answer()

@dp.callback_query(F.data == "support")
async def open_support(call: CallbackQuery):
    text = (
        "📞 <b>Техническая поддержка</b>\n\n"
        "В этом разделе Вы можете создать тикет для связи с поддержкой.\n\n"
        "📊 <b>Статистика:</b>\n• Активных тикетов: 0\n\n"
        "✅ Вы можете создать новый тикет для обращения в поддержку."
    )
    send_photo_or_text(call, "support.jpg", text, get_support_menu())
    await call.answer()

@dp.callback_query(F.data == "create_ticket")
async def create_ticket(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Напишите ваш вопрос одним сообщением:")
    await state.set_state(UserFlow.support_ticket)
    await call.answer()

@dp.message(UserFlow.support_ticket)
async def process_ticket(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✅ <b>Тикет создан!</b>\nВаше обращение зарегистрировано.",
        reply_markup=get_support_menu()
    )

@dp.callback_query(F.data.in_({
    "buy_premium", "buy_gift", "nft_menu", "ton_menu", "games", 
    "top_clients", "create_bot", "reviews", "sell_nft", "stub"
}))
async def stub_menu(call: CallbackQuery):
    await call.answer("Раздел в разработке 🛠", show_alert=True)

# ================= ЗАПУСК WEBHOOK =================
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    print(f"Webhook установлен: {WEBHOOK_URL}")

async def main():
    dp.startup.register(on_startup)
    
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()
    
    print("Сервер запущен на порту", os.getenv("PORT", 8080))
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
