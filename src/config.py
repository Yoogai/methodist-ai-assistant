import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные из .env
load_dotenv()

# --- ТОКЕНЫ И КЛЮЧИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

# --- ДОБАВИТЬ ЭТОТ БЛОК ---
ADMIN_ID = os.getenv("ADMIN_ID")
# -------------------------

# --- ПРОВЕРКИ ---
if not BOT_TOKEN:
    raise ValueError("ОШИБКА: В файле .env не найден BOT_TOKEN")
if not YANDEX_API_KEY:
    raise ValueError("ОШИБКА: В файле .env не найден YANDEX_API_KEY")
if not YANDEX_FOLDER_ID:
    raise ValueError("ОШИБКА: В файле .env не найден YANDEX_FOLDER_ID")
# --- ДОБАВИТЬ ЭТУ ПРОВЕРКУ ---
if not ADMIN_ID:
    raise ValueError("ОШИБКА: В файле .env не найден ADMIN_ID. Узнайте его у @userinfobot.")
# ------------------------------

# --- URI МОДЕЛИ ---
YANDEX_MODEL_URI = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite/latest"

# --- ПУТИ К ДАННЫМ ---
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MARKDOWN_DIR = DATA_DIR / "markdown"
PDF_DIR = DATA_DIR / "pdf"

# Вывод для отладки при старте
print(f"✅ Конфигурация загружена.")
print(f"🔑 Admin ID: {ADMIN_ID}")