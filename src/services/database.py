import sqlite3
import logging
from src.config import BASE_DIR

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_name="bot_users.db"):
        db_path = BASE_DIR / db_name
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def init_db(self):
        """Создает таблицу пользователей, если ее нет."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT
            )
        """)
        self.conn.commit()
        logger.info("База данных инициализирована.")

    def add_user(self, user_id: int, username: str, first_name: str):
        """Добавляет нового пользователя в базу (если его там еще нет)."""
        try:
            # INSERT OR IGNORE не будет вызывать ошибку, если user_id уже существует
            self.cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя в БД: {e}")

    def get_all_users(self) -> list[int]:
        """Возвращает список всех user_id из базы."""
        self.cursor.execute("SELECT user_id FROM users")
        return [row[0] for row in self.cursor.fetchall()]

# Создаем один экземпляр базы на весь бот
db = Database()