import sqlite3
import logging
from src.config import BASE_DIR

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name="bot_users.db"):
        """
        Инициализация подключения к базе данных.
        Файл базы данных будет создан в корневой директории проекта.
        """
        self.db_path = BASE_DIR / db_name
        # Используем check_same_thread=False для корректной работы в асинхронной среде aiogram
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def _execute(self, query: str, params: tuple = ()):
        """
        Вспомогательный метод для выполнения SQL-запросов с автоматическим коммитом.
        """
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
        except Exception as e:
            logger.error(f"Критическая ошибка базы данных при выполнении запроса: {e}")
            self.conn.rollback()
            return None

    def init_db(self):
        """
        Создание необходимых таблиц, если они отсутствуют.
        """
        self._execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                full_name TEXT,
                position TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
        logger.info(f"База данных успешно инициализирована по пути: {self.db_path}")

    def add_user(self, user_id: int, username: str, first_name: str):
        """
        Добавление нового пользователя при первом запуске бота (/start).
        """
        self._execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )

    def update_user_profile(self, user_id: int, full_name: str, position: str):
        """
        Обновление расширенных данных пользователя (ФИО и должность).
        """
        self._execute(
            "UPDATE users SET full_name = ?, position = ? WHERE user_id = ?",
            (full_name, position, user_id)
        )

    def get_all_users(self) -> list[int]:
        """
        Возвращает список ID всех зарегистрированных пользователей (для рассылок).
        """
        try:
            self.cursor.execute("SELECT user_id FROM users")
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return []

    def get_user(self, user_id: int) -> dict | None:
        """
        Получение полной информации о пользователе по его Telegram ID.
        """
        try:
            self.cursor.execute(
                "SELECT user_id, username, first_name, full_name, position FROM users WHERE user_id = ?",
                (user_id,)
            )
            user_data = self.cursor.fetchone()
            if user_data:
                return {
                    "user_id": user_data[0],
                    "username": user_data[1],
                    "first_name": user_data[2],
                    "full_name": user_data[3],
                    "position": user_data[4]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя {user_id}: {e}")
            return None

# --- ВАЖНО: Создание экземпляра класса для экспорта ---
# Именно эта строка позволяет делать 'from src.services.database import db'
db = Database()