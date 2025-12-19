import os
import yaml
import logging
import re
from pathlib import Path
from src.config import MARKDOWN_DIR

logger = logging.getLogger(__name__)


class Document:
    def __init__(self, content: str, metadata: dict, filename: str):
        self.content = content
        self.metadata = metadata
        self.filename = filename


class RagEngine:
    def __init__(self):
        self.documents = []
        self.slug_map = {}  # Словарь: "slug" -> "real_filename.pdf"
        self.load_documents()

    def load_documents(self):
        """Загружает MD файлы и строит карту слагов."""
        if not MARKDOWN_DIR.exists():
            logger.warning(f"Папка {MARKDOWN_DIR} не найдена!")
            return

        count = 0
        self.documents = []
        self.slug_map = {}  # Очищаем перед загрузкой

        for md_file in MARKDOWN_DIR.glob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8", errors='ignore') as f:
                    content = f.read()

                metadata = {}
                body_content = content

                # Разделяем по ---
                parts = list(filter(None, content.split('---')))

                if len(parts) >= 2:
                    yaml_text = parts[0].strip()
                    body_content = "---".join(parts[1:]).strip()

                    try:
                        metadata = yaml.safe_load(yaml_text)
                        if not isinstance(metadata, dict): metadata = {}
                    except Exception as e:
                        logger.error(f"YAML Error в {md_file.name}: {e}")
                        metadata = {}

                # --- НОВОЕ: Сохраняем связь Slug -> Filename ---
                slug = metadata.get('slug')
                pdf_file = metadata.get('file_name')

                if slug and pdf_file:
                    self.slug_map[slug] = pdf_file
                # -----------------------------------------------

                doc = Document(content=body_content, metadata=metadata, filename=md_file.name)
                self.documents.append(doc)
                count += 1

            except Exception as e:
                logger.error(f"Ошибка чтения {md_file}: {e}")

        logger.info(f"Загружено {count} документов. Карта слагов: {len(self.slug_map)} записей.")

    def search(self, query: str) -> tuple[str, dict]:
        # Тюнинг запроса (синонимы)
        query_normalized = query.lower()
        replacements = {
            "методичка": "методическое издание пособие",
            "методички": "методические издания пособия",
            "нмо": "научно-методический отдел",
            "бд": "база данных",
            "комплектование": "комплектование фондов"
        }
        for slang, official in replacements.items():
            query_normalized = query_normalized.replace(slang, official)

        query_words = set(query_normalized.split())
        best_doc = None
        max_score = 0

        for doc in self.documents:
            score = 0
            text_lower = doc.content.lower()
            title_lower = str(doc.metadata.get('title', '')).lower()

            for word in query_words:
                if len(word) < 4: continue
                if word in title_lower: score += 10
                count = text_lower.count(word)
                score += min(count, 5)

            if score > max_score:
                max_score = score
                best_doc = doc

        if best_doc and max_score > 0:
            logger.info(f"Найден документ: {best_doc.metadata.get('title', 'Без названия')} (Score: {max_score})")
            return best_doc.content[:3000], best_doc.metadata

        return "", {}

    def get_filename_by_slug(self, slug: str) -> str | None:
        """Возвращает имя файла PDF по слагу."""
        return self.slug_map.get(slug)