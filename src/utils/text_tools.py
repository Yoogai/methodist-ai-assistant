import re
import textwrap
from html import escape
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest


def clean_html_for_telegram(text: str) -> str:
    """Очищает HTML от запрещенных тегов."""
    text = re.sub(r'<!DOCTYPE.*?>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?(table|tr|div|p|body|html|head).*?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<td.*?>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'</td>', ' | ', text, flags=re.IGNORECASE)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    return text.strip()


def format_web_search_result(text: str, sources: list) -> str:
    """Форматирует ответ веб-поиска."""
    text = re.sub(r'(?m)^[\*\-]\s+(.+)$', r'• \1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\[\d+\]', '', text)

    if sources:
        text += "\n\n📚 <b>Источники:</b>\n"
        counter = 1
        for source in sources:
            if source.get("used"):
                title = escape(source.get('title', 'Источник'))
                url = source.get('url', '#')
                text += f"{counter}. <a href='{url}'>{title}</a>\n"
                counter += 1
    return text


async def send_split_message(message: Message, text: str, reply_markup=None, disable_web_preview=False):
    """Разбивает длинные сообщения."""
    text = clean_html_for_telegram(text)
    if len(text) <= 4096:
        try:
            await message.answer(text, reply_markup=reply_markup, parse_mode="HTML",
                                 disable_web_page_preview=disable_web_preview)
        except TelegramBadRequest:
            await message.answer(escape(text), reply_markup=reply_markup)
    else:
        chunks = textwrap.wrap(text, width=4000, replace_whitespace=False, drop_whitespace=False)
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            try:
                await message.answer(chunk, reply_markup=reply_markup if is_last else None, parse_mode="HTML",
                                     disable_web_page_preview=disable_web_preview)
            except:
                await message.answer(escape(chunk), reply_markup=reply_markup if is_last else None)