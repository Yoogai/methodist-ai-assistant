import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Filter, Command
from aiogram.types import Message
from html import escape

from src.config import ADMIN_ID
from src.services.database import db

router = Router()


# --- Админ-фильтр ---
class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return str(message.from_user.id) == ADMIN_ID


# --- Хендлер для рассылки (оставляем как был) ---
@router.message(Command("broadcast"), IsAdmin())
async def broadcast_handler(message: Message, bot: Bot):
    text_to_send = message.text.replace("/broadcast", "").strip()
    if not text_to_send:
        await message.answer("Введите текст рассылки.")
        return

    users = db.get_all_users()
    await message.answer(f"Рассылка для {len(users)} пользователей...")

    count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text_to_send)
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await message.answer(f"Разослано: {count}")


# --- НОВЫЙ ХЕНДЛЕР: ОТВЕТ ПОЛЬЗОВАТЕЛЮ ---
@router.message(IsAdmin(), F.reply_to_message)
async def reply_to_user_handler(message: Message, bot: Bot):
    """
    Срабатывает, когда админ отвечает (Reply) на пересланное сообщение.
    """
    # 1. Пытаемся узнать, кто автор оригинального сообщения
    original_user = message.reply_to_message.forward_from

    # Если пользователь скрыл аккаунт в настройках приватности, forward_from будет None
    if not original_user:
        await message.answer(
            "❌ Не могу ответить автоматически: у пользователя скрыт профиль (Forward Privacy).\n"
            "Попробуйте написать ему лично по Username (если он есть в инфо-сообщении выше)."
        )
        return

    # 2. Отправляем ответ пользователю
    try:
        await bot.send_message(
            chat_id=original_user.id,
            text=f"📩 <b>Ответ от методиста:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer("✅ Ответ отправлен.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить ответ: {e}")