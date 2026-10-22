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
BOT_TOKEN = "8800276454:AAF0QTpC9CcvbchTY_bE01BAm1uKvIyPyCQ" # Замени на свой токен

logging.basicConfig(level=logging.INFO)

# В aiogram 3.7+ parse_mode задается так:
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ================= СОСТОЯНИЯ (FSM) =================
class UserFlow(StatesGroup):
    sell_nft_input = State()
    topup_input = State()

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
    # Сетка: 1, 1, 1, 2, 2, 1, 1
    builder.adjust(1, 1, 1, 2, 2, 1, 1)
    return builder.as_markup()

def get_catalog_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Купить 50 Stars (50 ⭐)", callback_data="buy_50_stars")
    builder.button(text="⭐ Купить 100 Stars (100 ⭐)", callback_data="buy_100_stars")
    builder.button(text="💎 Telegram Premium", callback_data="buy_premium")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()

def get_back_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    return builder.as_markup()

# ================= СТАРТ И ГЛАВНОЕ МЕНЮ =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "👋 <b>Добро пожаловать в KryptonStars!</b>\n\n"
        "У нас вы можете купить:\n"
        "⭐ Telegram Stars\n"
        "💎 Telegram Premium\n"
        "И много чего другого дешевле чем в приложении и без верификации!\n\n"
        "🔥 <b>Куплено звезд: 1,143,994</b>"
    )
    await message.answer(text, reply_markup=get_main_menu())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "👋 <b>Главное меню</b>\n\n"
        "🔥 <b>Куплено звезд: 1,143,994</b>"
    )
    # Редактируем текущее сообщение, чтобы не засорять чат
    await call.message.edit_text(text, reply_markup=get_main_menu())
    await call.answer()

# ================= РАЗДЕЛ "ТОВАРЫ TELEGRAM" (ЗВЕЗДЫ) =================
@dp.callback_query(F.data == "catalog")
async def open_catalog(call: CallbackQuery):
    await call.message.edit_text(
        "🕶 <b>Товары Telegram</b>\n\nВыбери, что хочешь приобрести:",
        reply_markup=get_catalog_menu()
    )
    await call.answer()

# --- ОПЛАТА ЗВЕЗДАМИ (XTR) ---
@dp.callback_query(F.data.in_({"buy_50_stars", "buy_100_stars"}))
async def send_stars_invoice(call: CallbackQuery):
    # Определяем цену и количество
    amount = 50 if call.data == "buy_50_stars" else 100
    
    # ВАЖНО: currency="XTR" - это код Telegram Stars.
    # provider_token="" - для цифровых товаров оставляем пустым.
    prices = [LabeledPrice(label=f"{amount} Stars", amount=amount)]
    
    await call.message.answer_invoice(
        title=f"Покупка {amount} Stars",
        description=f"Покупка {amount} звезд для вашего аккаунта Telegram.",
        payload=f"stars_order_{amount}_{call.from_user.id}",
        currency="XTR", 
        prices=prices,
        provider_token="" 
    )
    await call.answer()

# Обязательный обработчик: Telegram спрашивает "Все ок?"
@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    # Здесь можно проверить наличие товара, лимиты и т.д.
    # Если всё ок - разрешаем оплату
    await query.answer(ok=True)

# Обработчик успешной оплаты
@dp.message(F.successful_payment)
async def success_payment(message: Message):
    payment: SuccessfulPayment = message.successful_payment
    
    # ID платежа нужен для возврата средств, если что-то пойдет не так
    charge_id = payment.telegram_payment_charge_id
    
    await message.answer(
        f"✅ <b>Оплата успешно получена!</b>\n\n"
        f"Вы приобрели {payment.total_amount} ⭐\n"
        f"ID транзакции: <code>{charge_id}</code>\n\n"
        f"<i>(В реальном боте здесь должна быть логика зачисления звезд на аккаунт через Fragment API)</i>",
        reply_markup=get_back_menu()
    )


# ================= ЗАГЛУШКИ ДЛЯ ОСТАЛЬНЫХ КНОПОК =================
@dp.callback_query(F.data.in_({
    "games", "profile", "support", 
    "top_clients", "create_bot", "reviews", "buy_premium"
}))
async def stub_menu(call: CallbackQuery):
    texts = {
        "games": "🕹 <b>Игры</b>\n\nРаздел находится в разработке.",
        "profile": f"👺 <b>Профиль</b>\n\nID: <code>{call.from_user.id}</code>\nБаланс: 0 ⭐\nЗаказов: 0",
        "support": "👨‍💻 <b>Поддержка</b>\n\nНапишите нашему менеджеру: @support_username",
        "top_clients": "👤 <b>Топ клиентов</b>\n\n1. Скрыт\n2. Скрыт\n3. Скрыт",
        "create_bot": "🧑‍💻 <b>Создать своего бота</b>\n\nФункция появится позже.",
        "reviews": "🧐 <b>Отзывы</b>\n\nОтзывы появятся после первых реальных покупок.",
        "buy_premium": "💎 <b>Telegram Premium</b>\n\nОплата Premium временно недоступна."
    }
    await call.message.edit_text(
        texts.get(call.data, "В разработке..."), 
        reply_markup=get_back_menu()
    )
    await call.answer()


# ================= СЦЕНАРИЙ "ПРОДАТЬ NFT" (ДЛЯ ВИДА) =================
@dp.callback_query(F.data == "sell_nft")
async def start_sell_nft(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🤝 <b>Продажа NFT</b>\n\n"
        "Отправь ссылку на свой NFT (например, подарок или username):",
        reply_markup=get_back_menu()
    )
    await state.set_state(UserFlow.sell_nft_input)
    await call.answer()

@dp.message(UserFlow.sell_nft_input)
async def process_sell_nft(message: Message, state: FSMContext):
    # Имитация успешной обработки
    await state.clear()
    await message.answer(
        f"✅ <b>Заявка принята!</b>\n\n"
        f"Ваш NFT <code>{message.text[:50]}</code> отправлен на оценку.\n"
        f"Результат придет в течение 24 часов.",
        reply_markup=get_back_menu()
    )


# ================= СЦЕНАРИЙ "ПОПОЛНИТЬ БАЛАНС" (ДЛЯ ВИДА) =================
@dp.callback_query(F.data == "topup")
async def start_topup(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🧢 <b>Пополнение баланса</b>\n\n"
        "Введите сумму в рублях, на которую хотите пополнить баланс (только число):",
        reply_markup=get_back_menu()
    )
    await state.set_state(UserFlow.topup_input)
    await call.answer()

@dp.message(UserFlow.topup_input)
async def process_topup(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число.")
        return
        
    await state.clear()
    await message.answer(
        f"✅ <b>Заявка на пополнение на {message.text} ₽ создана!</b>\n\n"
        f"<i>(Здесь должна быть интеграция с платежной системой CryptoBot или СБП для получения ссылки на оплату)</i>",
        reply_markup=get_back_menu()
    )


# ================= ЗАПУСК БОТА =================
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
