from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.core.states import DialogStates
from src.keyboards.builders import create_settings_keyboard

router = Router()

@router.message(F.text == "⚙️ Параметры")
async def settings_handler(message: Message, state: FSMContext):
    await state.set_state(DialogStates.settings)
    fsm_data = await state.get_data()
    current_settings = fsm_data.get("settings", {"voice_mode": "text_to_text"})
    await message.answer("Настройте параметры работы бота:", reply_markup=create_settings_keyboard(current_settings))

@router.callback_query(F.data.startswith("set_voice_mode:"))
async def set_v_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    data = await state.get_data()
    sets = data.get("settings", {})
    sets["voice_mode"] = mode
    await state.update_data(settings=sets)
    await callback.message.edit_reply_markup(reply_markup=create_settings_keyboard(sets))
    await callback.answer("Режим изменен")

@router.callback_query(F.data == "close_settings")
async def close_sets(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DialogStates.main)
    await callback.message.delete()
    await callback.answer("Сохранено")