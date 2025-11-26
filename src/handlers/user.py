import os
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from html import escape

from src.services.rag_engine import RagEngine
from src.services.yandex_gpt import YandexGPTService
from src.services.database import db
from src.keyboards.builders import create_pdf_keyboard, get_main_menu_keyboard
from src.config import PDF_DIR, ADMIN_ID

# --- Инициализация ---
router = Router()
rag_service = RagEngine()
gpt_service = YandexGPTService()

# 1. ОСНОВНОЙ ПРОМПТ
SYSTEM_PROMPT = """Ты — «Цифровой помощник НМО НБ РА», ведущий методист-консультант. 
Твоя задача — отвечать на вопросы сотрудников библиотек, используя факты из предоставленного контекста.

ИНСТРУКЦИИ:
1. Основа — контекст: Весь твой ответ должен быть СТРОГО основан на фактах из контекста.
2. Стиль: официально-деловой, но доброжелательный.
3. Структурируй ответ (списки, абзацы).
"""

# 2. SMALL TALK
CHIT_CHAT_PROMPT = """Ты — «Цифровой помощник НМО НБ РА», вежливый, эмпатичный, интеллектуальный.
Пользователь написал сообщение, но прямой ответ в базе знаний не найден.

ТВОЯ ЗАДАЧА:
1. **Если это приветствие** -> Поздоровайся тепло, представься и предложи помощь.
2. **Если пользователь спрашивает "Что ты умеешь?", "О чем рассказать?", "Твои темы"** ->
   Ответь: "Я изучил методические материалы Национальной библиотеки и готов проконсультировать вас по следующим темам:"
   Затем перечисли список (используй красивые буллиты):
   * 📚 Комплектование и учёт библиотечных фондов (включая списание).
   * 📝 Оформление методических пособий и изданий (структура, ГОСТы).
   * 📊 Статистический учёт (форма 6-НК, основные показатели).
   * 🏛 Работа научно-методического отдела Национальной библиотеки РА.
   * 📰 Библиографические обзоры и списки литературы.

   Закончи фразой: "Просто задайте вопрос в свободной форме."

3. **Если это благодарность** -> Ответь: "Всегда пожалуйста! Рад быть полезным."
4. **Если вопрос не по теме** -> Вежливо скажи: "К сожалению, пока я не владею информацией по этому вопросу. Но я быстро учусь! Попробуйте спросить что-нибудь другое."

ВАЖНО: Будь живым собеседником, избегай канцелярщины.
"""


# ...

class QuestionStates(StatesGroup):
    waiting_for_question = State()


# --- Хендлеры ---

@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name
    )

    await message.answer(
        f"Здравствуйте, <b>{escape(message.from_user.full_name)}</b>!",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await message.answer(
        "Я — ваш цифровой помощник-методист. Задайте мне вопрос по библиотечному делу."
    )


@router.message(F.text == "✍️ Задать вопрос")
async def ask_question_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(QuestionStates.waiting_for_question)
    await message.answer(
        "Напишите ваш вопрос, и я перешлю его главному методисту. "
        "Пожалуйста, опишите ситуацию как можно подробнее."
    )


@router.message(StateFilter(QuestionStates.waiting_for_question), F.text)
async def forward_question_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    username = f"@{message.from_user.username}" if message.from_user.username else "нет"
    user_info = (
        f"❓ <b>Новый вопрос от пользователя:</b>\n"
        f"👤 <b>Имя:</b> {escape(message.from_user.full_name)}\n"
        f"🔗 <b>Link:</b> {username}\n"
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>"
    )

    try:
        await bot.send_message(ADMIN_ID, user_info, parse_mode="HTML")
        await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        await message.answer(
            "✅ Спасибо! Ваш вопрос отправлен. Вам ответят в ближайшее время.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

    await state.clear()


@router.message(F.text, StateFilter(None), F.reply_to_message == None)
async def handle_text_query(message: Message, bot: Bot) -> None:
    await bot.send_chat_action(chat_id=message.chat.id, action='typing')

    # 1. Поиск в базе
    context, metadata = rag_service.search(message.text)

    # --- ЕСЛИ НИЧЕГО НЕ НАШЛИ В БАЗЕ ---
    if not context or not metadata:
        chit_chat_response = gpt_service.generate_response(
            system_prompt=CHIT_CHAT_PROMPT,  # <-- Другая роль
            user_text=message.text,
            context_text=""  # Контекста нет
        )
        await message.answer(escape(chit_chat_response), parse_mode="HTML")
        return

    # --- ЕСЛИ НАШЛИ ДОКУМЕНТ ---
    ai_response = gpt_service.generate_response(
        system_prompt=SYSTEM_PROMPT,  # <-- Роль строгого эксперта
        user_text=message.text,
        context_text=context
    )

    # Обработка отказов
    if "Извините" in ai_response or "ошибка" in ai_response or "нет информации" in ai_response:
        # Если даже с контекстом модель отказалась отвечать, пробуем мягкий ответ
        await message.answer(escape(ai_response), parse_mode="HTML")
        return

    pdf_slug = metadata.get('slug')
    biblio_ref = metadata.get('biblio_ref', 'Источник не указан.')

    final_response_text = f"{escape(ai_response)}\n\n---\n<i>📚 Источник: {escape(biblio_ref)}</i>"
    keyboard = create_pdf_keyboard(pdf_slug)

    await message.answer(
        final_response_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("get_pdf:"))
async def send_pdf_handler(callback: CallbackQuery, bot: Bot) -> None:
    slug = callback.data.split(":")[1]
    filename = rag_service.get_filename_by_slug(slug)

    if not filename:
        await callback.message.answer("Ошибка: файл не найден.")
        await callback.answer()
        return

    file_path = PDF_DIR / filename

    if file_path.exists():
        await bot.send_chat_action(chat_id=callback.message.chat.id, action='upload_document')
        document = FSInputFile(file_path)
        try:
            await callback.message.answer_document(document, caption=f"Ваш документ: {escape(filename)}")
        except Exception as e:
            await callback.message.answer(f"Ошибка отправки: {e}")
    else:
        await callback.message.answer("Файл не найден.", parse_mode="HTML")

    await callback.answer()