import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем наши конфиги, хендлеры и базу данных
from src.config import BOT_TOKEN
from src.handlers import user, admin
from src.services.database import db


async def main() -> None:
    # --- ВАЖНЕЙШИЙ ШАГ: ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
    # Эта строка создает таблицу 'users', если она еще не существует.
    # Она должна быть вызвана ДО запуска polling'а.
    db.init_db()
    # ----------------------------------------------------

    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)

    # Подключаем роутеры для админа и пользователя
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # Пропускаем старые апдейты, которые бот мог получить, пока был выключен
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем бота
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")