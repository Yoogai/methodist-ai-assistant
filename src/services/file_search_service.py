import json
import logging
from pathlib import Path
from src.config import BASE_DIR

logger = logging.getLogger(__name__)


class FileSearchService:
    def __init__(self):
        self.index_path = BASE_DIR / "data" / "file_index.json"
        self.docs_dir = BASE_DIR / "data" / "documents"
        self.file_index = self._load_index()

    def _load_index(self):
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки индекса файлов: {e}")
            return []

    def find_file(self, query: str) -> dict | None:
        """
        Ищет файл по совпадению ключевых слов.
        Возвращает словарь с данными файла или None.
        """
        query_lower = query.lower()
        best_match = None
        max_hits = 0

        for item in self.file_index:
            hits = 0
            for keyword in item["keywords"]:
                if keyword in query_lower:
                    hits += 1

            if hits > max_hits:
                max_hits = hits
                best_match = item

        # Условие: должно совпасть хотя бы 1-2 ключевых слова
        return best_match if max_hits >= 1 else None

    def get_full_path(self, filename: str) -> Path:
        return self.docs_dir / filename