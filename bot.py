import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, ReplyKeyboardMarkup,
    FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from flask import Flask
from threading import Thread

# ============================================================
# ==================== НАСТРОЙКИ БОТА =========================
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ Ошибка: Переменная окружения BOT_TOKEN не найдена!")

SELLER = "@oweli"
REVIEWS_URL = "https://t.me/oweliotz"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ============================================================
# ==================== ЛОКАЛЬНЫЕ КАРТИНКИ =====================
# ============================================================
IMAGES = {
    "start": "start.jpg", 
    "menu": "menu.jpg", 
    "reviews": "reviews.jpg",
    "bp": "bp.jpg",
    "pro": "pro.jpg",
    "gems": "gems.jpg",
    "royale": "royale.jpg",
    "cart": "cart.jpg",
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
            ("БП+ х8", "1600₽"),
        ],
    ),
    "pro": (
        "👑 <b>PRO PASS</b>\n\n"
        "💎 Максимальная выгода и эксклюзивные награды!\n"
        "Выбери вариант 👇",
        [
            ("Про пасс", "650₽"),
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
            ("Корзина 50$", "1050₽"),
            ("Корзина 100$", "1500₽"),
        ],
    ),
}

# ============================================================
# ==================== КЛАВИАТУРЫ =============================
# ============================================================

# --- Нижнее (Reply) меню ---
def bottom_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="📖 Все категории 📖")
    kb.button(text="📄 Наличие товаров 📄")
    kb.button(text="⭐ Отзывы ⭐")          # Заменили "Что за магазин" на Отзывы
    kb.button(text="👤 Профиль 👤")
    kb.adjust(2, 2) # По 2 кнопки в ряд
    return kb.as_markup(resize_keyboard=True, input_field_placeholder="Выбери действие...")

# --- Инлайн-меню ---
def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍 Меню", callback_data="menu")
    kb.button(text="⭐ Отзывы", callback_data="reviews")
    kb.adjust(1)
    return kb.as_markup()

def menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎟 Brawl Pass", callback_data="cat:bp")
    kb.button(text="👑 Pro Pass", callback_data="cat:pro")
    kb.button(text="💎 Гемы", callback_data="cat:gems")
    kb.button(text="👑 Рояль Пассы", callback_data="cat:royale")
    kb.button(text="🛒 Корзина Supercell", callback_data="cat:cart")
    kb.button(text="⬅️ Назад", callback_data="start")
    kb.adjust(2, 2, 1, 1)
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
# ==================== ОТПРАВКА СООБЩЕНИЙ =====================
# ============================================================

async def send_or_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup, image_key: str = None):
    await cb.message.delete()
    
    image_path = IMAGES.get(image_key)
    
    if image_path and os.path.exists(image_path):
        photo = FSInputFile(image_path)
        await cb.message.answer_photo(photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")

# ============================================================
# ==================== ТЕКСТЫ =================================
# ============================================================

START_TEXT = (
    "👋 <b>Добро пожаловать в магазин доната Brawl Stars!</b>\n\n"
    "🔥 Здесь ты найдёшь:\n"
    "🎟 Brawl Pass и Pro Pass\n"
    "💎 Гемы по лучшим ценам\n"
    "👑 Рояль Пассы для Clash Royale\n"
    "🛒 Пополнение корзины Supercell\n\n"
    "⚡ Быстрая выдача • 🛡 Безопасно • 💯 Проверено\n\n"
    "Используй кнопки ниже или нажми «🛍 Меню» 👇"
)

MENU_TEXT = (
    "🛍 <b>МЕНЮ МАГАЗИНА</b>\n\n"
    "🔊 <b>NEW DONATION PRICES</b> — актуальные цены!\n\n"
    "Выбери категорию товара 👇\n\n"
    f"💬 По всем вопросам: {SELLER}"
)

REVIEWS_TEXT = (
    "⭐ <b>ОТЗЫВЫ НАШИХ КЛИЕНТОВ</b>\n\n"
    "Мы дорожим своей репутацией и всегда рады обратной связи! 🤝\n\n"
    "📂 <b>Все реальные отзывы и доказательства сделок опубликованы в нашем канале.</b>\n\n"
    "👇 Нажми на кнопку ниже, чтобы перейти и убедиться в качестве нашего сервиса:\n\n"
    f"📩 Хочешь оставить свой отзыв? Пиши — {SELLER}"
)

# ============================================================
# ==================== ХЕНДЛЕРЫ ===============================
# ============================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    image_path = IMAGES.get("start")
    if image_path and os.path.exists(image_path):
        photo = FSInputFile(image_path)
        await message.answer_photo(
            photo=photo, 
            caption=START_TEXT, 
            reply_markup=main_menu_kb(), 
            parse_mode="HTML"
        )
    else:
        await message.answer(START_TEXT, reply_markup=main_menu_kb(), parse_mode="HTML")
    
    # Отправляем нижнее меню отдельным сообщением, чтобы оно появилось
    await message.answer("Используй нижнее меню для быстрой навигации 👇", reply_markup=bottom_menu_kb())

# --- Обработчики нижнего (Reply) меню ---

@dp.message(F.text == "📖 Все категории 📖")
async def btn_all_categories(message: Message):
    image_path = IMAGES.get("menu")
    if image_path and os.path.exists(image_path):
        photo = FSInputFile(image_path)
        await message.answer_photo(photo=photo, caption=MENU_TEXT, reply_markup=menu_kb(), parse_mode="HTML")
    else:
        await message.answer(MENU_TEXT, reply_markup=menu_kb(), parse_mode="HTML")

@dp.message(F.text == "⭐ Отзывы ⭐")
async def btn_reviews(message: Message):
    image_path = IMAGES.get("reviews")
    if image_path and os.path.exists(image_path):
        photo = FSInputFile(image_path)
        await message.answer_photo(photo=photo, caption=REVIEWS_TEXT, reply_markup=reviews_kb(), parse_mode="HTML")
    else:
        await message.answer(REVIEWS_TEXT, reply_markup=reviews_kb(), parse_mode="HTML")

@dp.message(F.text == "👤 Профиль 👤")
async def btn_profile(message: Message):
    await message.answer(
        f"👤 <b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📛 Имя: {message.from_user.full_name}\n"
        f"🔗 Юзернейм: @{message.from_user.username if message.from_user.username else 'нет'}\n\n"
        f"📩 По вопросам покупок: {SELLER}",
        parse_mode="HTML"
    )

@dp.message(F.text == "📄 Наличие товаров 📄")
async def btn_stock(message: Message):
    # Автоматически собираем список всего, что есть в CATEGORIES
    text = "📄 <b>НАЛИЧИЕ ТОВАРОВ В МАГАЗИНЕ:</b>\n\n"
    for key, (title, items) in CATEGORIES.items():
        # Берем только первую строчку заголовка (например, "🎟 BRAWL PASS")
        short_title = title.split('\n')[0]
        text += f"{short_title}:\n"
        for name, price in items:
            text += f"  • {name} — {price}\n"
        text += "\n"
    
    text += f"📩 За покупкой — {SELLER}"
    
    await message.answer(text, parse_mode="HTML")


# --- Обработчики Инлайн-кнопок ---

@dp.callback_query(F.data == "start")
async def back_to_start(cb: CallbackQuery):
    await send_or_edit(cb, START_TEXT, main_menu_kb(), image_key="start")
    await cb.answer()

@dp.callback_query(F.data == "menu")
async def show_menu(cb: CallbackQuery):
    await send_or_edit(cb, MENU_TEXT, menu_kb(), image_key="menu")
    await cb.answer()

@dp.callback_query(F.data == "reviews")
async def show_reviews(cb: CallbackQuery):
    await send_or_edit(cb, REVIEWS_TEXT, reviews_kb(), image_key="reviews")
    await cb.answer()

@dp.callback_query(F.data.startswith("cat:"))
async def show_category(cb: CallbackQuery):
    cat_key = cb.data.split(":")[1]
    header, _ = CATEGORIES[cat_key]
    await send_or_edit(cb, header, category_kb(cat_key), image_key=cat_key)
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
    await send_or_edit(cb, text, item_kb(cat_key), image_key=cat_key)
    await cb.answer()

# ============================================================
# ==================== FLASK (ДЛЯ RENDER) =====================
# ============================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# ============================================================
# ==================== ЗАПУСК =================================
# ============================================================

async def main():
    keep_alive()
    print("✅ Бот запущен с новым нижним меню!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
