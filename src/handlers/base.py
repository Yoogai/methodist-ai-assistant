import logging
from typing import Tuple, List, Optional, Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from html import escape
from aiogram.exceptions import TelegramBadRequest

from src.core.states import DialogStates
# ИСПРАВЛЕНО: Импорт из prompts
from src.core.prompts import SYSTEM_PROMPT, CHIT_CHAT_PROMPT, STARTUP_SUGGESTIONS, FILE_REQUEST_TRIGGERS, MAX_AUDIO_SIZE
from src.keyboards.builders import get_main_menu_keyboard, create_smart_keyboard, create_file_actions_keyboard
from src.utils.text_tools import clean_html_for_telegram, send_split_message

from src.services.database import db
from src.services.rag_engine import RagEngine
from src.services.yandex_gpt import YandexGPTService
from src.services.file_search_service import FileSearchService
from src.services.speech_service import YandexSpeechKitService
from src.services.ocr_service import YandexOCRService

logger = logging.getLogger(__name__)
router = Router()
rag_service = RagEngine()
gpt_service = YandexGPTService()
file_search_service = FileSearchService()
speech_service = YandexSpeechKitService()
ocr_service = YandexOCRService()


# --- Вспомогательные ---
def is_small_talk(text: str) -> bool:
    text_lower = text.lower().strip()
    triggers = ["привет", "здравствуй", "добрый день", "хай", "кто ты", "что ты", "что умеешь", "помощь", "спасибо",
                "благодарю"]
    if len(text_lower.split()) < 6:
        for trigger in triggers:
            if trigger in text_lower: return True
    return False


async def try_send_file(message: Message, bot: Bot) -> bool:
    if not message.text: return False
    user_text = message.text.lower()
    if any(trigger in user_text for trigger in FILE_REQUEST_TRIGGERS):
        file_data = file_search_service.find_file(user_text)
        if file_data:
            file_path = file_search_service.get_full_path(file_data["filename"])
            if file_path.exists():
                await bot.send_chat_action(message.chat.id, "upload_document")
                await message.reply_document(FSInputFile(file_path), caption=f"Вот файл: <b>{file_data['title']}</b>",
                                             parse_mode="HTML")
                return True
    return False


async def get_ai_response(state: FSMContext, user_id: int, user_text: str) -> Tuple[
    str, List[str], Optional[str], Optional[Dict[str, Any]]]:
    user_data = db.get_user(user_id)
    full_name = user_data.get("full_name") or user_data.get("first_name") or "Коллега"
    fsm_data = await state.get_data()
    history = fsm_data.get("history", [])
    recognized_context = fsm_data.get("last_recognized_text", "")

    context = ""
    metadata = None
    pdf_slug = None
    prompt = CHIT_CHAT_PROMPT

    if is_small_talk(user_text) and not recognized_context:
        context = ""
    else:
        context, metadata = rag_service.search(user_text)
        pdf_slug = metadata.get("slug") if metadata else None
        if context: prompt = SYSTEM_PROMPT

    full_context = f"КОНТЕКСТ ИЗ ФОТО:\n{recognized_context}\n\nБАЗА ЗНАНИЙ:\n{context}" if recognized_context else context
    res = gpt_service.generate_response(prompt, user_text, full_context, history, full_name)
    ai_text = res.get("text", "Ошибка.")
    suggestions = res.get("suggestions", [])
    new_history = history + [{"role": "user", "text": user_text}, {"role": "assistant", "text": ai_text}]
    await state.update_data(history=new_history[-6:], last_query=user_text, last_suggestions=suggestions)
    return ai_text, suggestions, pdf_slug, metadata


# --- Хендлеры ---

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext):
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await state.set_state(DialogStates.main)
    await state.update_data(history=[], settings={"voice_mode": "text_to_text"}, last_recognized_text="",
                            last_suggestions=STARTUP_SUGGESTIONS)
    await message.answer(f"Здравствуйте, <b>{escape(message.from_user.full_name)}</b>!",
                         reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    await message.answer("Я — ваш цифровой методист. Чем могу помочь?",
                         reply_markup=create_smart_keyboard(STARTUP_SUGGESTIONS, None), parse_mode="HTML")


@router.message(F.voice)
async def handle_voice_message(message: Message, bot: Bot, state: FSMContext):
    if not message.voice or message.voice.file_size > MAX_AUDIO_SIZE: return
    fsm_data = await state.get_data()
    settings = fsm_data.get("settings", {})
    voice_mode = settings.get("voice_mode", "text_to_text")
    status_msg = await message.reply("🎤 Слушаю...")
    try:
        voice_bytes_io = io.BytesIO()
        await bot.download(message.voice, destination=voice_bytes_io)
        recognized_text = await speech_service.speech_to_text(voice_bytes_io.getvalue())
        if not recognized_text:
            await status_msg.edit_text("😕 Не понял вас.")
            return
        if voice_mode == "voice_to_text":
            await status_msg.edit_text(f"<i>Вы сказали:</i>\n\n{escape(recognized_text)}", parse_mode="HTML")
        elif voice_mode == "voice_to_voice":
            ai_text, _, _, _ = await get_ai_response(state, message.from_user.id, recognized_text)
            voice_res = await speech_service.text_to_speech(ai_text)
            if voice_res:
                await status_msg.delete()
                await message.reply_voice(BufferedInputFile(voice_res, "ans.ogg"))
        else:
            ai_text, suggestions, pdf_slug, metadata = await get_ai_response(state, message.from_user.id,
                                                                             recognized_text)
            final = ai_text + (
                f"\n\n📚 <i>Источник: {escape(str(metadata.get('title')))}</i>" if metadata and metadata.get(
                    'title') else "")
            await status_msg.edit_text(clean_html_for_telegram(final),
                                       reply_markup=create_smart_keyboard(suggestions, pdf_slug), parse_mode="HTML")
    except Exception:
        await status_msg.edit_text("Ошибка голоса.")


@router.message(F.text, StateFilter(None, DialogStates.main, DialogStates.recognition_mode))
async def handle_text_query(message: Message, bot: Bot, state: FSMContext):
    if message.text in ["✍️ Написать нам", "🌐 Поиск в сети", "⚙️ Параметры", "💡 Есть идея",
                        "✨ Креативный режим"]: return
    if await try_send_file(message, bot): return
    fsm_data = await state.get_data()
    settings = fsm_data.get("settings", {})
    voice_mode = settings.get("voice_mode", "text_to_text")
    if voice_mode == "text_playback":
        voice_bytes = await speech_service.text_to_speech(message.text)
        if voice_bytes: await message.reply_voice(BufferedInputFile(voice_bytes, "play.ogg"))
        return
    if voice_mode == "text_to_voice":
        ai_text, _, _, _ = await get_ai_response(state, message.from_user.id, message.text)
        voice_bytes = await speech_service.text_to_speech(ai_text)
        if voice_bytes: await message.reply_voice(BufferedInputFile(voice_bytes, "ans.ogg"))
        return

    if not is_small_talk(message.text):
        status_msg = await message.answer("💭 Думаю...")
    else:
        status_msg = None

    ai_text, suggestions, pdf_slug, metadata = await get_ai_response(state, message.from_user.id, message.text)
    final_text = ai_text + (
        f"\n\n📚 <i>Источник: {escape(str(metadata.get('title')))}</i>" if metadata and metadata.get('title') else "")

    if status_msg: await status_msg.delete()
    await send_split_message(message, final_text, reply_markup=create_smart_keyboard(suggestions, pdf_slug))


@router.callback_query(F.data.startswith("ask_suggestion:"))
async def handle_suggestion(callback: CallbackQuery, bot: Bot, state: FSMContext):
    try:
        idx = int(callback.data.split(":")[1])
        data = await state.get_data()
        s_list = data.get("last_suggestions") or STARTUP_SUGGESTIONS
        if not (0 <= idx < len(s_list)):
            await callback.answer("Подсказка устарела.")
            return
        txt = s_list[idx]
        await callback.answer()
        status_msg = await callback.message.answer(f"💭 Готовлю ответ на вопрос: «{escape(txt)}»...")
        await bot.send_chat_action(callback.message.chat.id, "typing")
        ai_text, suggestions, pdf_slug, metadata = await get_ai_response(state, callback.from_user.id, txt)
        source_text = f"\n\n📚 <i>Источник: {escape(str(metadata.get('title')))}</i>" if metadata and metadata.get(
            'title') else ""
        final_text = ai_text + source_text
        await status_msg.edit_text(clean_html_for_telegram(final_text),
                                   reply_markup=create_smart_keyboard(suggestions, pdf_slug), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Suggestion Error: {e}")
        await callback.answer("Ошибка.", show_alert=True)


@router.callback_query(F.data == "regenerate")
async def handle_regen(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    last = data.get("last_query")
    if last:
        await callback.answ