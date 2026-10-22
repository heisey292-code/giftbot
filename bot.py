import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InputMediaPhoto
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ============================================================
# ==================== НАСТРОЙКИ БОТА =========================
# ============================================================
BOT_TOKEN = "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER"
SELLER = "@oweli"
REVIEWS_URL = "https://t.me/oweliotz"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ============================================================
# ==================== ССЫЛКИ НА КАРТИНКИ =====================
# ============================================================
# Сюда вставь прямые ссылки на твои картинки (например, из твоего ТГ-канала)
# Пока здесь стоят заглушки. Если ссылка не работает - бот отправит просто текст.
IMAGES = {
    "gems": "https://i.ibb.co/6P0Z8Z9/gems.jpg",  # <-- ЗАМЕНИ НА СВОЮ ССЫЛКУ
    "bp": "https://i.ibb.co/3s7yKq1/bp.jpg",      # <-- ЗАМЕНИ НА СВОЮ ССЫЛКУ
    "cart": "https://i.ibb.co/1J2mXyZ/cart.jpg",  # <-- ЗАМЕНИ НА СВОЮ ССЫЛКУ
    "royale": None,
    "menu": None,
}

# ============================================================
# ==================== ДАННЫЕ О ТОВАРАХ =======================
# ============================================================
CATEGORIES = {
    "bp": (
        "🎟 <b>BRAWL PASS</b>\n\n"
        "🔥 Лучшие боевые пропуска по выгодным ценам!\n"
        "Выбери нужный вариант ниже 👇",
        [
            ("БП", "350₽"),
            ("БП+", "400₽"),
            ("БП+ Gift", "450₽"),
            ("Про пасс", "650₽"),
            ("БП+ х8", "1600₽"),
        ],
    ),
    "gems": (
        "💎 <b>ГЕМЫ</b>\n\n"
        "💠 Мгновенная выдача гемов на аккаунт!\n"
        "Выбери количество 👇",
        [
            ("80 💎", "200₽"),
            ("170 💎", "300₽"),
            ("360 💎", "500₽"),
            ("950 💎", "1000₽"),
            ("2000 💎", "1500₽"),
            ("4000 💎", "2500₽"),
            ("6000 💎", "3000₽"),
            ("12000 💎", "4700₽"),
        ],
    ),
    "royale": (
        "👑 <b>РОЯЛЬ ПАССЫ</b>\n\n"
        "🏆 Пропуска для Clash Royale по лучшей цене!\n"
        "Выбери вариант 👇",
        [
            ("Рояль пасс", "370₽"),
            ("Рояль пасс х8", "1600₽"),
        ],
    ),
    "cart": (
        "🛒 <b>КОРЗИНА SUPERCELL</b>\n\n"
        "💵 Пополнение корзины в Supercell Store!\n"
        "Выбери сумму 👇",
        [
            ("Корзина 10$", "300₽"),
            ("Корзина 30$", "750₽"),
            ("Корзина 50$", "950₽"),
            ("Корзина 100$", "1400₽"),
        ],
    ),
}


# ============================================================
# ==================== КЛАВИАТУРЫ =============================
# ============================================================

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍 Меню", callback_data="menu")
    kb.button(text="⭐ Отзывы", callback_data="reviews")
    kb.adjust(1)
    return kb.as_markup()


def menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎟 Brawl Pass", callback_data="cat:bp")
    kb.button(text="💎 Гемы", callback_data="cat:gems")
    kb.button(text="👑 Рояль Пассы", callback_data="cat:royale")
    kb.button(text="🛒 Корзина Supercell", callback_data="cat:cart")
    kb.button(text="⬅️ Назад", callback_data="start")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def category_kb(cat_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    items = CATEGORIES[cat_key][1]
    for i, (name, _) in enumerate(items):
        kb.button(text=name, callback_data=f"item:{cat_key}:{i}")
    kb.button(text="⬅️ Назад", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def item_kb(cat_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data=f"cat:{cat_key}")
    kb.adjust(1)
    return kb.as_markup()


def reviews_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📂 Открыть отзывы", url=REVIEWS_URL)
    kb.button(text="⬅️ Назад", callback_data="start")
    kb.adjust(1)
    return kb.as_markup()


# ============================================================
# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ================
# ============================================================

async def send_or_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup, image_url: str = None):
    """
    Универсальная функция: 
    Если передана ссылка на картинку - отправляет/редактирует фото с подписью.
    Если ссылки нет - отправляет/редактирует просто текст.
    """
    if image_url:
        media = InputMediaPhoto(media=image_url, caption=text, parse_mode="HTML")
        try:
            await cb.message.edit_media(media=media, reply_markup=kb)
        except Exception:
            # Если предыдущее сообщение было текстом, удаляем его и шлем новое с фото
            await cb.message.delete()
            await cb.message.answer_photo(photo=image_url, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        # Если картинки нет, работаем как обычно с текстом
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await cb.message.delete()
            await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")


# ============================================================
# ==================== ТЕКСТЫ СООБЩЕНИЙ =======================
# ============================================================

START_TEXT = (
    "👋 <b>Добро пожаловать в магазин доната Brawl Stars!</b>\n\n"
    "🔥 Здесь ты найдёшь:\n"
    "🎟 Brawl Pass и Про Пасс\n"
    "💎 Гемы по лучшим ценам\n"
    "👑 Рояль Пассы для Clash Royale\n"
    "🛒 Пополнение корзины Supercell\n\n"
    "⚡ Быстрая выдача • 🛡 Безопасно • 💯 Проверено\n\n"
    "Выбирай нужный раздел 👇"
)

MENU_TEXT = (
    "🛍 <b>МЕНЮ МАГАЗИНА</b>\n\n"
    "🔊 <b>NEW DONATION PRICES</b> — актуальные цены!\n\n"
    "Выбери категорию товара 👇\n\n"
    f"💬 По всем вопросам: {SELLER}"
)

REVIEWS_TEXT = (
    "⭐ <b>ОТЗЫВЫ НАШИХ КЛИЕНТОВ</b>\n\n"
    "💬 <i>«Всё пришло за 5 минут, продавец топ!»</i> — @user1\n"
    "💬 <i>«Брал БП+ — всё честно, рекомендую»</i> — @user2\n"
    "💬 <i>«Уже 3-я покупка, всегда быстро и без проблем»</i> — @user3\n"
    "💬 <i>«Гемы пришли моментально, спасибо!»</i> — @user4\n\n"
    "📂 <b>Больше отзывов в нашем канале:</b>\n"
    f"👉 {REVIEWS_URL}\n\n"
    f"📩 Хочешь оставить отзыв? Пиши — {SELLER}\n\n"
    "👇 Возвращайся в меню"
)


# ============================================================
# ==================== ХЕНДЛЕРЫ ===============================
# ============================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(START_TEXT, reply_markup=main_menu_kb(), parse_mode="HTML")


@dp.callback_query(F.data == "start")
async def back_to_start(cb: CallbackQuery):
    await send_or_edit(cb, START_TEXT, main_menu_kb(), image_url=None)
    await cb.answer()


@dp.callback_query(F.data == "menu")
async def show_menu(cb: CallbackQuery):
    await send_or_edit(cb, MENU_TEXT, menu_kb(), image_url=IMAGES.get("menu"))
    await cb.answer()


@dp.callback_query(F.data == "reviews")
async def show_reviews(cb: CallbackQuery):
    await send_or_edit(cb, REVIEWS_TEXT, reviews_kb(), image_url=None)
    await cb.answer()


@dp.callback_query(F.data.startswith("cat:"))
async def show_category(cb: CallbackQuery):
    cat_key = cb.data.split(":")[1]
    header, _ = CATEGORIES[cat_key]
    await send_or_edit(cb, header, category_kb(cat_key), image_url=IMAGES.get(cat_key))
    await cb.answer()


@dp.callback_query(F.data.startswith("item:"))
async def show_item(cb: CallbackQuery):
    _, cat_key, idx = cb.data.split(":")
    idx = int(idx)
    name, price = CATEGORIES[cat_key][1][idx]

    text = (
        f"📦 <b>{name}</b>\n\n"
        f"💰 Цена: <b>{price}</b>\n\n"
        f"✅ Товар в наличии\n"
        f"⚡ Быстрая выдача\n"
        f"🛡 Безопасная сделка\n\n"
        f"📩 <b>За покупкой — {SELLER}</b>"
    )
    # Оставляем картинку категории на фоне карточки товара
    await send_or_edit(cb, text, item_kb(cat_key), image_url=IMAGES.get(cat_key))
    await cb.answer()


# ============================================================
# ==================== ЗАПУСК БОТА ============================
# ============================================================

async def main():
    print("✅ Бот запущен! Нажми /start в Telegram.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
