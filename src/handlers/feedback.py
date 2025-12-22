import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from html import escape

# Импорты из ядра системы
from src.core.states import DialogStates
from src.core.prompts import IDEA_PROMPT
from src.config import ADMIN_ID
from src.keyboards.builders import get_main_menu_keyboard

# Импорты утилит и сервисов
from src.utils.text_tools import clean_html_for_telegram, format_web_search_result, send_split_message
from src.services.yandex_gpt import YandexGPTService
from src.services.web_search_service import YandexWebSearchService

logger = logging.getLogger(__name__)

# Инициализация роутера — критически важная строка для устранения ImportError
router = Router()

gpt_service = YandexGPTService()
web_search_service = YandexWebSearchService()


# --- Блок функционала "💡 Есть идея" (Связь с разработчиком) ---

@router.message(F.text == "💡 Есть идея")
async def idea_start(message: Message, state: FSMContext):
    """Инициализация режима сбора предложений и баг-репортов."""
    await state.set_state(DialogStates.idea_mode)
    await message.answer(
        "Опишите вашу идею или замение по работе бота. "
        "Я структурирую ваше сообщение и передам его разработчику."
    )


@router.message(StateFilter(DialogStates.idea_mode))
async def process_idea(message: Message, state: FSMContext, bot: Bot):
    """Обработка присланной идеи и отправка администратору."""
    status_msg = await message.answer("📤 Обрабатываю и отправляю ваше сообщение...")

    # Генерация структурированного текста идеи через GPT
    res = gpt_service.generate_response(IDEA_PROMPT, message.text)
    formatted_text = res.get("text", message.text)

    # Формирование отчета для администратора (разработчика)
    report = (
        f"💡 <b>ИДЕЯ / БАГ-РЕПОРТ</b>\n"
        f"👤 От: {escape(message.from_user.full_name)}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"--- \n"
        f"{clean_html_for_telegram(formatted_text)}"
    )

    try:
        await bot.send_message(ADMIN_ID, report, parse_mode="HTML")
        await status_msg.edit_text(
            "✅ Спасибо! Ваше сообщение успешно передано разработчику.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error sending idea to admin: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при отправке. Попробуйте позже.")

    await state.set_state(DialogStates.main)


# --- Блок функционала "✍️ Написать нам" (Связь с методистами) ---

@router.message(F.text == "✍️ Написать нам")
async def feedback_start(message: Message, state: FSMContext):
    """Инициализация режима обратной связи с методическим отделом."""
    await state.set_state(DialogStates.feedback)
    await message.answer("Напишите ваше сообщение методисту. Оно будет передано в научно-методический отдел.")


@router.message(StateFilter(DialogStates.feedback))
async def process_feedback(message: Message, bot: Bot, state: FSMContext):
    """Пересылка сообщения пользователя администратору (методисту)."""
    admin_msg = (
        f"✉️ <b>НОВОЕ СООБЩЕНИЕ МЕТОДИСТУ</b>\n"
        f"👤 От: {escape(message.from_user.full_name)}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"--- \n"
        f"{escape(message.text)}"
    )

    try:
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
        await message.answer(
            "✅ Ваше сообщение доставлено. Вам ответят в ближайшее время.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error sending feedback to admin: {e}")
        await message.answer("❌ Не удалось отправить сообщение.")

    await state.set_state(DialogStates.main)


# --- Блок функционала Web Search (Поиск в интернете) ---

@router.message(F.text == "🌐 Поиск в сети")
async def web_search_handler(message: Message, state: FSMContext):
    """Инициализация режима внешнего поиска."""
    await state.set_state(DialogStates.web_search)
    await message.answer("Введите ваш запрос для поиска актуальной информации в интернете:")


@router.message(StateFilter(DialogStates.web_search))
async def process_web_search(message: Message, state: FSMContext):
    """Выполнение поиска через Yandex Search API и возврат форматированного результата."""
    status_msg = await message.answer("🌐 Выполняю поиск в сети, пожалуйста, подождите...")

    try:
        # Запрос к сервису веб-поиска
        res = web_search_service.generate_web_response(message.text)

        if res and isinstance(res, list) and res[0].get("message"):
            raw_text = res[0]["message"]["content"]
            sources = res[0].get("sources", [])

            # Форматирование результата с учетом списков и источников
            formatted_answer = format_web_search_result(raw_text, sources)

            await status_msg.delete()
            await send_split_message(message, formatted_answer, disable_web_preview=True)
        else:
            await status_msg.edit_text("😕 К сожалению, поиск не дал результатов. Попробуйте изменить запрос.")

    except Exception as e:
        logger.error(f"WebSearch Error in feedback handler: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при выполнении веб-поиска.")

    finally:
        await state.set_state(DialogStates.main)