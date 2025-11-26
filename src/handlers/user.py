import os
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from html import escape

# Импортируем сервисы, клавиатуры и конфиги
from src.services.rag_engine import RagEngine
from src.services.yandex_gpt import YandexGPTService
from src.services.database import db
from src.keyboards.builders import create_pdf_keyboard, get_main_menu_keyboard
from src.config import PDF_DIR, ADMIN_ID

# --- Инициализация ---
router = Router()
rag_service = RagEngine()
gpt_service = YandexGPTService()

# Системный промпт
SYSTEM_PROMPT = """Ты — «Методист НБ РА», ведущий эксперт-консультант. Ты НЕ пересказываешь документы, а отвечаешь на вопрос пользователя по существу, используя факты из предоставленного контекста как основу для своего ответа.

ИНСТРУКЦИИ:
1.  **Говори от первого лица эксперта:** Используй фразы "Вам следует...", "Правила таковы:", "Рекомендуется...".
2.  **Забудь о документе:** НЕ упоминай фразы "в данном пособии говорится", "цель документа", "в тексте сказано". Просто давай ответ.
3.  **Будь конкретным:** Отвечай на вопрос пользователя, а не описывай, что есть в документе.
4.  **Основа — контекст:** Весь твой ответ должен быть СТРОГО основан на фактах из предоставленного контекста. Если в контексте нет ответа, напиши: "В моей базе знаний нет информации по этому вопросу".
5.  **Структурируй:** Используй списки и выделение для улучшения читаемости.
"""


# --- FSM Состояния (для режима "Задать вопрос") ---
class QuestionStates(StatesGroup):
    waiting_for_question = State()


# --- Хендлеры ---

@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    /start: Приветствие, сохранение пользователя в БД, выдача меню.
    """
    # Сохраняем пользователя для рассылок
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
        "Я — ваш цифровой помощник-методист. Задайте мне вопрос по библиотечному делу или выберите опцию в меню."
    )


@router.message(F.text == "✍️ Задать вопрос")
async def ask_question_handler(message: Message, state: FSMContext) -> None:
    """
    Вход в режим вопроса администратору.
    """
    await state.set_state(QuestionStates.waiting_for_question)
    await message.answer(
        "Напишите ваш вопрос, и я перешлю его главному методисту. "
        "Пожалуйста, опишите ситуацию как можно подробнее."
    )


@router.message(StateFilter(QuestionStates.waiting_for_question), F.text)
async def forward_question_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    """
    Обработка вопроса: пересылка администратору.
    """
    # Формируем карточку пользователя (ИСПРАВЛЕНО: теперь тут реальные данные)
    username = f"@{message.from_user.username}" if message.from_user.username else "нет"
    user_info = (
        f"❓ <b>Новый вопрос от пользователя:</b>\n"
        f"👤 <b>Имя:</b> {escape(message.from_user.full_name)}\n"
        f"🔗 <b>Link:</b> {username}\n"
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>"
    )

    try:
        # 1. Отправляем админу данные о пользователе
        await bot.send_message(ADMIN_ID, user_info, parse_mode="HTML")

        # 2. Пересылаем сообщение (чтобы админ мог сделать Reply)
        await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        # 3. Говорим пользователю, что все ок
        await message.answer(
            "✅ Спасибо! Ваш вопрос отправлен. Вам ответят в ближайшее время.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка при отправке вопроса: {e}. Попробуйте позже.")

    # Выходим из режима ожидания
    await state.clear()


@router.message(F.text, StateFilter(None), F.reply_to_message == None)
async def handle_text_query(message: Message, bot: Bot) -> None:
    """
    Основная логика RAG (Поиск по базе знаний).
    Срабатывает только если нет активного State и это не ответ на сообщение.
    """
    await bot.send_chat_action(chat_id=message.chat.id, action='typing')

    # 1. Поиск в базе
    context, metadata = rag_service.search(message.text)

    # Если ничего не нашли — сразу выходим
    if not context or not metadata:
        await message.answer(
            "😕 К сожалению, я не нашел точного ответа в загруженных документах.\n\n"
            "Попробуйте переформулировать вопрос или воспользуйтесь кнопкой '✍️ Задать вопрос', чтобы связаться с методистом."
        )
        return

    # 2. Генерация ответа через YandexGPT
    ai_response = gpt_service.generate_response(
        system_prompt=SYSTEM_PROMPT,
        user_text=message.text,
        context_text=context
    )

    # Если нейросеть вернула ошибку или отказ
    if "Извините" in ai_response or "ошибка" in ai_response or "нет информации" in ai_response:
        await message.answer(escape(ai_response), parse_mode="HTML")
        return

    # 3. Формирование ответа с источником
    pdf_slug = metadata.get('slug')
    biblio_ref = metadata.get('biblio_ref', 'Источник не указан.')

    safe_ai_response = escape(ai_response)
    safe_biblio_ref = escape(biblio_ref)

    final_response_text = f"{safe_ai_response}\n\n---\n<i>📚 Источник: {safe_biblio_ref}</i>"

    # Кнопка скачивания (по slug)
    keyboard = create_pdf_keyboard(pdf_slug)

    await message.answer(
        final_response_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("get_pdf:"))
async def send_pdf_handler(callback: CallbackQuery, bot: Bot) -> None:
    """
    Отправка PDF файла по нажатию кнопки.
    """
    slug = callback.data.split(":")[1]
    filename = rag_service.get_filename_by_slug(slug)

    if not filename:
        await callback.message.answer("Ошибка: файл не найден в индексе бота.")
        await callback.answer()
        return

    file_path = PDF_DIR / filename

    if file_path.exists():
        await bot.send_chat_action(chat_id=callback.message.chat.id, action='upload_document')
        document = FSInputFile(file_path)
        try:
            await callback.message.answer_document(
                document,
                caption=f"Ваш документ: {escape(filename)}"
            )
        except Exception as e:
            await callback.message.answer(f"Не удалось отправить файл: {e}")
    else:
        await callback.message.answer(
            f"Критическая ошибка: файл <code>{escape(filename)}</code> физически отсутствует на сервере.",
            parse_mode="HTML")

    await callback.answer()