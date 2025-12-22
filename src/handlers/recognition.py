import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

# Импорты из ядра и утилит
from src.core.states import DialogStates
from src.core.prompts import VLM_COMPLEX_PROMPT, VLM_DESCRIBE_PROMPT, OCR_CLEANUP_PROMPT, MAX_AUDIO_SIZE
from src.keyboards.builders import create_recognition_keyboard, get_main_menu_keyboard
from src.utils.media_tools import encode_image_to_base64, decode_qr_code, create_formatted_docx, generate_qr_image
from src.utils.text_tools import send_split_message

# Импорты сервисов
from src.services.ocr_service import YandexOCRService
from src.services.yandex_gpt import YandexGPTService
from src.services.speech_service import YandexSpeechKitService

logger = logging.getLogger(__name__)
router = Router()

# Инициализация сервисов
ocr_service = YandexOCRService()
gpt_service = YandexGPTService()
speech_service = YandexSpeechKitService()


# --- Вход в меню распознавания ---
@router.callback_query(F.data == "enter_recognition_menu")
async def recognition_menu_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DialogStates.recognition_mode)
    fsm_data = await state.get_data()
    current_type = fsm_data.get("recognition_type", "simple")
    await callback.message.edit_text(
        "<b>Режим распознавания активен.</b>\nВыберите инструмент:",
        reply_markup=create_recognition_keyboard(current_type),
        parse_mode="HTML"
    )
    await callback.answer()


# --- Генерация QR (вход из настроек) ---
@router.callback_query(F.data == "generate_qr_start")
async def qr_gen_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DialogStates.qr_gen_mode)
    await callback.message.answer("✍️ Введите текст или ссылку для зашифровки в QR-код:")
    await callback.answer()


@router.message(StateFilter(DialogStates.qr_gen_mode))
async def process_qr_gen(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текст.")
        return

    # Генерируем QR через утилиту
    buf = generate_qr_image(message.text)

    await message.answer_photo(
        BufferedInputFile(buf.getvalue(), "qr.png"),
        caption="✅ Ваш QR-код",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(DialogStates.main)


# --- Навигация внутри режима распознавания ---
@router.callback_query(StateFilter(DialogStates.recognition_mode), F.data.startswith("set_recog:"))
async def set_recognition_type(callback: CallbackQuery, state: FSMContext):
    recog_type = callback.data.split(":")[1]
    await state.update_data(recognition_type=recog_type)
    try:
        await callback.message.edit_reply_markup(reply_markup=create_recognition_keyboard(recog_type))
    except:
        pass
    await callback.answer(f"Режим изменен")


@router.callback_query(StateFilter(DialogStates.recognition_mode), F.data == "recog_help")
async def recog_help_handler(callback: CallbackQuery):
    help_text = (
        "• <b>Простой текст:</b> Vision OCR (для документов)\n"
        "• <b>Сложный документ:</b> Gemma 3 (для таблиц)\n"
        "• <b>Описать:</b> Анализ содержания фото\n"
        "• <b>Аудио:</b> SpeechKit (голос в текст)\n"
        "• <b>QR:</b> Чтение кодов"
    )
    await callback.message.answer(help_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(StateFilter(DialogStates.recognition_mode), F.data == "recog_exit")
async def recog_exit_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DialogStates.main)
    await callback.message.edit_text("Вы вышли из режима распознавания.")
    await callback.answer()


# --- Обработка Фото (OCR, VLM, QR) ---
@router.message(F.photo, StateFilter(DialogStates.recognition_mode))
async def handle_photo_recognition(message: Message, bot: Bot, state: FSMContext):
    fsm_data = await state.get_data()
    recog_type = fsm_data.get("recognition_type", "simple")
    status_msg = await message.reply("⏳ Обрабатываю...")

    try:
        # Скачиваем фото в память
        photo_bytes = io.BytesIO()
        await bot.download(message.photo[-1], destination=photo_bytes)
        photo_data = photo_bytes.getvalue()

        # 1. Режим QR
        if recog_type == "qr":
            qr_text = await decode_qr_code(bot, message.photo[-1].file_id)
            if qr_text:
                await status_msg.delete()
                await message.reply(f"📱 <b>QR:</b> <code>{qr_text}</code>", parse_mode="HTML")
            else:
                await status_msg.edit_text("❌ QR не найден.")
            await message.answer("Жду следующий QR:", reply_markup=create_recognition_keyboard(recog_type))
            return

        result_text = None

        # 2. Режим Простой текст (OCR)
        if recog_type == "simple":
            raw_text = ocr_service.recognize_text(photo_data)
            if raw_text:
                await status_msg.edit_text("🧹 Чищу текст...")
                res = gpt_service.generate_response(OCR_CLEANUP_PROMPT, raw_text)
                result_text = res.get("text", raw_text)
            else:
                result_text = None

        # 3. Режим Сложный документ (VLM + DOCX)
        elif recog_type == "complex":
            img_base64 = await encode_image_to_base64(bot, message.photo[-1].file_id)
            result_text = await gpt_service.generate_vlm_response(VLM_COMPLEX_PROMPT, img_base64)

            if result_text:
                await status_msg.edit_text("📄 Создаю файл...")
                docx_buf = create_formatted_docx(result_text)
                await message.reply_document(
                    BufferedInputFile(docx_buf.getvalue(), "document.docx"),
                    caption="✅ Файл готов."
                )
                await state.update_data(last_recognized_text=result_text[:3500])
                await status_msg.delete()
                await message.answer("Готов к следующему:", reply_markup=create_recognition_keyboard(recog_type))
                return  # Выходим, чтобы не отправлять текст дублем

        # 4. Режим Описания (VLM)
        elif recog_type == "describe":
            img_base64 = await encode_image_to_base64(bot, message.photo[-1].file_id)
            result_text = await gpt_service.generate_vlm_response(VLM_DESCRIBE_PROMPT, img_base64)

        # Отправка текстового результата (для simple и describe)
        if result_text:
            await state.update_data(last_recognized_text=result_text[:3500])
            try:
                await status_msg.delete()
            except:
                pass

            await send_split_message(message, f"📄 <b>Результат:</b>\n\n{result_text}")
            await message.answer("Жду следующее:", reply_markup=create_recognition_keyboard(recog_type))
        else:
            await status_msg.edit_text("😕 Не удалось распознать.")

    except Exception as e:
        logger.error(f"Recog Error: {e}")
        await message.answer(f"⚠️ Ошибка: {e}")


# --- Обработка Аудио (в режиме распознавания) ---
@router.message(F.voice | F.audio, StateFilter(DialogStates.recognition_mode))
async def handle_audio_recognition(message: Message, bot: Bot, state: FSMContext):
    fsm_data = await state.get_data()
    if fsm_data.get("recognition_type") != "audio":
        await message.reply("Выберите режим 'Распознать аудио' в меню.")
        return

    audio_obj = message.voice or message.audio
    if audio_obj and audio_obj.file_size > MAX_AUDIO_SIZE:
        await message.reply("⚠️ Файл > 1 МБ (лимит Telegram API v1).")
        return

    status_msg = await message.reply("⏳ Слушаю...")
    try:
        audio_bytes = io.BytesIO()
        await bot.download(audio_obj, destination=audio_bytes)

        # Используем speech_service (v1 или v3 в зависимости от вашей реализации в services)
        text = await speech_service.speech_to_text(audio_bytes.getvalue())

        if text:
            await state.update_data(last_recognized_text=text[:3500])
            await status_msg.delete()
            await send_split_message(message, f"🎙️ <b>Текст:</b>\n\n{text}")
            await message.answer("Готов к следующему:", reply_markup=create_recognition_keyboard("audio"))
        else:
            await status_msg.edit_text("😕 Тишина или ошибка распознавания.")

    except Exception as e:
        await status_msg.edit_text(f"Ошибка аудио: {e}")