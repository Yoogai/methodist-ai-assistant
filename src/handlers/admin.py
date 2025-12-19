import logging
import re
from aiogram import Router, F, Bot
from aiogram.filters import Filter, Command
from aiogram.types import Message
from html import escape

from src.config import ADMIN_ID
from src.services.database import db

router = Router()


class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return str(message.from_user.id) == ADMIN_ID


@router.message(Command("broadcast"), IsAdmin())
async def broadcast_handler(message: Message, bot: Bot):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Использование: /broadcast Текст сообщения")
        return

    users = db.get_all_users()
    count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 <b>Объявление:</b>\n\n{text}", parse_mode="HTML")
            count += 1
        except:
            continue
    await message.answer(f"✅ Рассылка завершена. Получателей: {count}")


@router.message(IsAdmin(), F.reply_to_message)
async def admin_reply_handler(message: Message, bot: Bot):
    """
    Позволяет админу отвечать пользователю, делая 'Reply' на сообщение бота.
    Решает проблему Forward Privacy, извлекая ID из текста сообщения.
    """
    original_text = message.reply_to_message.text or message.reply_to_message.caption
    if not original_text:
        return

    # Ищем ID пользователя в тексте сообщения (формат ID: 12345678)
    match = re.search(r"ID: (\d+)", original_text)
    if not match:
        await message.answer("❌ Не удалось определить ID пользователя для ответа.")
        return

    user_id = int(match.group(1))

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"📩 <b>Ответ методиста:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")