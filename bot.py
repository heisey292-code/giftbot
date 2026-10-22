import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, 
    PreCheckoutQuery, SuccessfulPayment
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER" # Замени на свой токен!
RATE_USD = 0.0106 # Курс за 1 звезду при продаже боту

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ================= СОСТОЯНИЯ =================
class UserFlow(StatesGroup):
    buy_stars_input = State()
    sell_stars_input = State()

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

# Кнопки для раздела "Продажа звезд"
def get_sell_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 История", callback_data="sell_history")
    builder.button(text="« Назад", callback_data="catalog")
    builder.adjust(1, 1)
    return builder.as_markup()

# ================= СТАРТ =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "👋 <b>Добро пожаловать в KryptonStars!</b>\n\n"
        "У нас вы можете купить:\n"
        "⭐ Telegram Stars\n"
        "💎 Telegram Premium\n"
        "И много чего другого дешевле чем в приложении и без верификации!"
    )
    await message.answer(text, reply_markup=get_main_menu())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("👋 <b>Главное меню</b>", reply_markup=get_main_menu())
    await call.answer()

# ================= ТОВАРЫ TELEGRAM =================
@dp.callback_query(F.data == "catalog")
async def open_catalog(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🌟 <b>Покупка Telegram Stars</b>\n\n"
        "• Цена Telegram Stars: 1.5₽/шт.\n\n"
        "Нажмите кнопку ниже для покупки\n👇"
    )
    await call.message.edit_text(text, reply_markup=get_catalog_menu())
    await call.answer()

# --- ПРОДАЖА ЗВЕЗД (КАК НА СКРИНШОТЕ) ---
@dp.callback_query(F.data == "sell_stars")
async def prompt_sell_stars(call: CallbackQuery, state: FSMContext):
    text = (
        "💳 <b>Продажа звёзд</b>\n\n"
        f"• Цена за 1 звезду: {RATE_USD}$.\n\n"
        "🔍 Введите количество звёзд для продажи (минимум 100 звёзд):"
    )
    
    # Пытаемся отправить картинку с мишкой. 
    # ВАЖНО: Положи картинку bear.jpg в папку с ботом (или удали этот блок, если картинки нет)
    try:
        from aiogram.types import FSInputFile
        photo = FSInputFile("bear.jpg") # Имя твоего файла с картинкой
        await call.message.answer_photo(photo=photo, caption=text, reply_markup=get_sell_menu())
        await call.message.delete() # Удаляем старое сообщение с меню
    except Exception:
        # Если картинки нет, просто отправляем текст
        await call.message.edit_text(text, reply_markup=get_sell_menu())
        
    await state.set_state(UserFlow.sell_stars_input)
    await call.answer()

@dp.message(UserFlow.sell_stars_input)
async def process_sell_stars(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (например, 100).")
        return
    
    amount = int(message.text)
    if amount < 100:
        await message.answer("Минимальное количество для продажи — 100 звёзд. Введите сумму больше.")
        return

    # Считаем сумму к выплате
    total_usd = round(amount * RATE_USD, 2)
    
    await state.clear()
    
    text = (
        f"✅ <b>Заявка на продажу {amount} ⭐ создана!</b>\n\n"
        f"К выплате: <b>{total_usd}$</b>\n\n"
        f"<b>Что делать дальше:</b>\n"
        f"1. Отправьте <b>{amount} звёзд</b> нашему боту через кнопку 'Подарить звёзды' в нашем профиле.\n"
        f"2. После отправки нажмите кнопку ниже, чтобы подтвердить перевод.\n\n"
        f"<i>(В этот момент в реальном боте Fragment API проверяет перевод и зачисляет деньги на баланс)</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я отправил(а) звёзды", callback_data="confirm_sell")
    builder.button(text="« Назад", callback_data="catalog")
    builder.adjust(1, 1)

    await message.answer(text, reply_markup=builder.as_markup())

# Заглушка для кнопки "История"
@dp.callback_query(F.data == "sell_history")
async def sell_history(call: CallbackQuery):
    await call.answer("История продаж пуста.", show_alert=True)

# Заглушка для кнопки "Я отправил"
@dp.callback_query(F.data == "confirm_sell")
async def confirm_sell(call: CallbackQuery):
    await call.message.edit_text(
        "⏳ <b>Проверяем транзакцию...</b>\n\n"
        "Пожалуйста, подождите. Если звёзды не зачислятся в течение 10 минут, напишите в поддержку.",
        reply_markup=get_sell_menu()
    )
    await call.answer()


# --- ПОКУПКА ЗВЕЗД (РЕАЛЬНАЯ ОПЛАТА) ---
@dp.callback_query(F.data == "buy_stars")
async def prompt_buy_stars(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🌟 <b>Покупка звезд</b>\n\n"
        "Введите количество звезд, которое хотите купить (например: 100):\n"
        "Минимальный пакет: 50 звезд.",
        reply_markup=get_sell_menu() # Используем ту же кнопку назад
    )
    await state.set_state(UserFlow.buy_stars_input)
    await call.answer()

@dp.message(UserFlow.buy_stars_input)
async def process_buy_stars(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (например, 100).")
        return
    
    amount = int(message.text)
    if amount < 50:
        await message.answer("Минимальный пакет — 50 звезд.")
        return

    await state.clear()
    prices = [LabeledPrice(label=f"{amount} Stars", amount=amount)]
    
    await message.answer_invoice(
        title=f"Покупка {amount} Stars",
        description=f"Покупка {amount} звезд для вашего аккаунта Telegram.",
        payload=f"buy_stars_{amount}_{message.from_user.id}",
        currency="XTR",
        prices=prices,
        provider_token=""
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: Message):
    payment = message.successful_payment
    await message.answer(
        f"✅ <b>Оплата получена!</b>\n\n"
        f"Куплено: {payment.total_amount} ⭐\n"
        f"Чек: <code>{payment.telegram_payment_charge_id}</code>",
        reply_markup=get_catalog_menu()
    )


# ================= ЗАГЛУШКИ =================
@dp.callback_query(F.data.in_({
    "buy_premium", "buy_gift", "nft_menu", "ton_menu", 
    "games", "profile", "support", "top_clients", "create_bot", "reviews", "sell_nft", "topup"
}))
async def stub_menu(call: CallbackQuery):
    await call.answer("Этот раздел пока в разработке 🛠", show_alert=True)


# ================= ЗАПУСК =================
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
