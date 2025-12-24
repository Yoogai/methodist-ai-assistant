import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from src.core.states import DialogStates
from src.core.prompts import (
    POST_PROMPT,
    PRESS_RELEASE_PROMPT,
    ANNOUNCEMENT_PROMPT,
    CUSTOM_CREATIVE_PROMPT
)
from src.keyboards.builders import create_creative_keyboard
from src.utils.text_tools import send_split_message
from src.services.yandex_gpt import YandexGPTService

logger = logging.getLogger(__name__)
router = Router()
gpt_service = YandexGPTService()

@router.callback_query(F.data == "enter_creative_from_settings")
async def enter_creative(callback: CallbackQuery, state: FSMContext):
    """Вход в креативный режим."""
    await state.set_state(DialogStates.creative_mode)
    await callback.message.edit_text(
        "✨ <b>Креативный режим активен.</b>\n"
        "Выберите жанр текста, который необходимо подготовить:",
        reply_markup=create_creative_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(StateFilter(DialogStates.creative_mode), F.data.startswith("creative:"))
async def select_genre(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретного жанра."""
    genre = callback.data.split(":")[1]

    if genre == "exit":
        await state.set_state(DialogStates.main)
        await state.update_data(creative_history=[])
        await callback.message.edit_text("Вы вышли из креативного режима. Чем я могу помочь?")
        await callback.answer()
        return

    # Очищаем историю при смене жанра для чистоты новой задачи
    await state.update_data(creative_history=[])

    mapping = {
        "post": (POST_PROMPT, "📝 Опишите тему <b>поста для соцсетей</b>. Я подготовлю подробный вариант с эмодзи."),
        "release": (PRESS_RELEASE_PROMPT, "📰 Пришлите информацию для <b>пресс-релиза</b>. Я оформлю её в деловом стиле."),
        "announcement": (ANNOUNCEMENT_PROMPT, "📢 Опишите ваше мероприятие. Я составлю яркий <b>анонс</b>."),
        "custom": (CUSTOM_CREATIVE_PROMPT, "❓ Опишите, какой текст вам нужен, и я помогу его составить.")
    }

    prompt, instruction_text = mapping.get(genre, (CUSTOM_CREATIVE_PROMPT, "Опишите вашу задачу:"))

    # Сохраняем выбранный промпт в данные состояния
    await state.update_data(current_creative_prompt=prompt)

    await callback.message.edit_text(instruction_text, parse_mode="HTML")
    await callback.answer()

@router.message(StateFilter(DialogStates.creative_mode))
async def handle_creative_text(message: Message, state: FSMContext):
    """
    Основной обработчик текста в креативном режиме.
    Подхватывает сохраненный промпт и использует историю.
    """
    # Игнорируем системные команды, если они просочились
    if message.text and message.text.startswith('/'):
        return

    fsm_data = await state.get_data()
    prompt = fsm_data.get("current_creative_prompt", CUSTOM_CREATIVE_PROMPT)
    creative_history = fsm_data.get("creative_history", [])

    status_msg = await message.answer("🖋️ <b>Генерирую текст, пожалуйста, подождите...</b>", parse_mode="HTML")

    try:
        # Запрос к GPT с учетом истории этого сеанса
        res = gpt_service.generate_response(prompt, message.text, history=creative_history)
        ans = res.get("text", "К сожалению, не удалось сгенерировать текст. Попробуйте еще раз.")

        # Обновляем историю (храним последние 3 пары для контекста уточнений)
        new_history = creative_history + [
            {"role": "user", "text": message.text},
            {"role": "assistant", "text": ans}
        ]
        await state.update_data(creative_history=new_history[-6:])

        await status_msg.delete()

        # Отправляем результат
        await send_split_message(message, f"<b>Ваш черновик:</b>\n\n{ans}")

        # Предлагаем продолжить или сменить жанр
        await message.answer(
            "Вы можете написать уточнения (например, 'сделай короче') или выбрать другой жанр:",
            reply_markup=create_creative_keyboard()
        )
    except Exception as e:
        logger.error(f"Creative Mode Error: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при генерации. Попробуйте позже.")
