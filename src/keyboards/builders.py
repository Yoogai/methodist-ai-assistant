from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру главного меню."""
    button_ask = KeyboardButton(text="✍️ Задать вопрос")

    # Создаем клавиатуру
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[button_ask]],
        resize_keyboard=True,
        input_field_placeholder="Задайте вопрос или выберите опцию..."
    )
    return keyboard


def create_pdf_keyboard(slug: str | None) -> InlineKeyboardMarkup | None:
    """
    Создает inline-кнопку "Скачать PDF", если slug передан.
    """
    if not slug:
        return None

    button = InlineKeyboardButton(
        text="📥 Скачать PDF",
        callback_data=f"get_pdf:{slug}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return keyboard