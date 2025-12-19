from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Написать нам"), KeyboardButton(text="🌐 Поиск в сети")],
            [KeyboardButton(text="💡 Есть идея"), KeyboardButton(text="⚙️ Параметры")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Задайте вопрос...",
    )
    return keyboard


def create_smart_keyboard(suggestions: list[str], pdf_slug: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, suggestion in enumerate(suggestions):
        button_text = suggestion if len(suggestion) < 50 else suggestion[:47] + "..."
        builder.button(text=button_text, callback_data=f"ask_suggestion:{i}")

    if suggestions:
        builder.adjust(1)

    bottom_row = []
    if pdf_slug:
        bottom_row.append(InlineKeyboardButton(text="📥 Скачать PDF", callback_data=f"get_pdf:{pdf_slug}"))
    bottom_row.append(InlineKeyboardButton(text="🔄 Ещё вариант", callback_data="regenerate"))

    if bottom_row:
        builder.row(*bottom_row)
    return builder.as_markup()


def create_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    voice_mode = settings.get("voice_mode", "text_to_text")

    modes = {
        "text_to_text": "📄 -> 📄 Текст в Текст",
        "voice_to_text": "🎤 -> 📄 Голос в Текст",
        "voice_to_voice": "🎤 -> 🗣️ Голос в Голос",
        "text_to_voice": "📄 -> 🗣️ Текст в Голос",
        "text_playback": "🔊 Озвучить мой текст"
    }

    for mode_id, mode_text in modes.items():
        text = f"✅ {mode_text}" if voice_mode == mode_id else mode_text
        builder.button(text=text, callback_data=f"set_voice_mode:{mode_id}")

    builder.adjust(1)
    # Новые кнопки
    builder.row(InlineKeyboardButton(text="📱 Создать QR-код", callback_data="generate_qr_start"))
    builder.row(InlineKeyboardButton(text="🔍 Распознать...", callback_data="enter_recognition_menu"))
    builder.row(InlineKeyboardButton(text="✨ Креативный режим", callback_data="enter_creative_from_settings"))
    builder.row(InlineKeyboardButton(text="ГОТОВО", callback_data="close_settings"))
    return builder.as_markup()


def create_recognition_keyboard(current_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    types = {
        "simple": "📄 Простой текст",
        "complex": "📊 Сложный документ",
        "describe": "🖼️ Описать изображение",
        "audio": "🎙️ Распознать аудио",
        "qr": "📱 Сканировать QR"
    }
    for t_id, t_text in types.items():
        text = f"✅ {t_text}" if current_type == t_id else t_text
        builder.button(text=text, callback_data=f"set_recog:{t_id}")

    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="❓ Помощь", callback_data="recog_help"),
        InlineKeyboardButton(text="🚪 Выйти", callback_data="recog_exit")
    )
    return builder.as_markup()


def create_creative_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Пост для соцсетей", callback_data="creative:post")
    builder.button(text="📰 Пресс-релиз", callback_data="creative:release")
    builder.button(text="📢 Анонс мероприятия", callback_data="creative:announcement")
    builder.button(text="❓ Другое (с помощью AI)", callback_data="creative:custom")
    builder.button(text="🚪 Выйти из режима", callback_data="creative:exit")
    builder.adjust(1)
    return builder.as_markup()


def create_file_actions_keyboard() -> InlineKeyboardMarkup:
    """Меню действий для присланного файла."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Сделать выжимку", callback_data="file_action:summarize")
    builder.button(text="🧠 Объяснить суть", callback_data="file_action:explain")
    builder.button(text="📄 Извлечь текст", callback_data="file_action:extract")
    builder.adjust(1)
    return builder.as_markup()