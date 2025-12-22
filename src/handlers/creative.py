from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from html import escape

from src.core.states import DialogStates
# ИСПРАВЛЕНО: Импорт из prompts
from src.core.prompts import IDEA_PROMPT
from src.config import ADMIN_ID
from src.keyboards.builders import get_main_menu_keyboard
from src.utils.text_tools import clean_html_for_telegram, format_web_search_result, send_split_message
from src.services.yandex_gpt import YandexGPTService
from src.services.web_search_service import YandexWebSearchService

router = Router()
gpt_service = YandexGPTService()
web_search_service = YandexWebSearchService()

# --- Есть идея ---
@router.message(F.text == "💡 Есть идея")
async def idea_start(message: Message, state: FSMContext):
    await state.set_state(DialogStates.idea_mode)
    await message.answer("Опишите вашу идею или замечание.")

@router.message(StateFilter(DialogStates.idea_mode))
async def process_idea(message: Message, state: FSMContext, bot: Bot):
    res = gpt_service.generate_response(IDEA_PROMPT, message.text)
    formatted = res.get("text", message.text)
    report = f"💡 <b>ИДЕЯ/БАГ</b>\n👤 От: {escape(message.from_user.full_name)}\n🆔 ID: <code>{message.from_user.id}</code>\n---\n{clean_html_for_telegram(formatted)}"
    await bot.send_message(ADMIN_ID, report, parse_mode="HTML")
    await message.answer("✅ Спасибо! Передано.", reply_markup=get_main_menu_keyboard())
    await state.set_state(DialogStates.main)

# --- Написать нам ---
@router.message(F.text == "✍️ Написать нам")
async def feedback_start(message: Message, state: FSMContext):
    await state.set_state(DialogStates.feedback)
    await message.answer("Напишите сообщение методисту:")

@router.message(StateFilter(DialogStates.feedback))
async def process_feedback(message: Message, bot: Bot, state: FSMContext):
    admin_msg = f"✉️ <b>СООБЩЕНИЕ</b>\n👤 От: {escape(message.from_user.full_name)}\n🆔 ID: <code>{message.from_user.id}</code>\n---\n{escape(message.text)}"
    await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
    await message.answer("✅ Доставлено.", reply_markup=get_main_menu_keyboard())
    await state.set_state(DialogStates.main)

# --- Web Search ---
@router.message(F.text == "🌐 Поиск в сети")
async def web_search_handler(message: Message, state: FSMContext):
    await state.set_state(DialogStates.web_search)
    await message.answer("Введите запрос:")

@router.message(StateFilter(DialogStates.web_search))
async def process_web_search(message: Message, state: FSMContext):
    status_msg = await message.answer("🌐 Ищу...")
    try:
        res = web_search_service.generate_web_response(message.text)
        if res and isinstance(res, list) and res[0].get("message"):
            raw_text = res[0]["message"]["content"]
            sources = res[0].get("sources", [])
            formatted = format_web_search_result(raw_text, sources)
            await status_msg.delete()
            await send_split_message(message, formatted, disable_web_preview=True)
        else: await status_msg.edit_text("😕 Ничего не найдено.")
    except: await status_msg.edit_text("Ошибка поиска.")
    finally: await state.set_state(DialogStates.main)