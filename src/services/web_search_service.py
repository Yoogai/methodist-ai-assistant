import requests
import logging
from src.config import YANDEX_API_KEY, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)

class YandexWebSearchService:
    def __init__(self):
        self.api_key = YANDEX_API_KEY
        self.folder_id = YANDEX_FOLDER_ID
        self.url = "https://searchapi.api.cloud.yandex.net/v2/gen/search"
        self.headers = {
            "Authorization": f"Api-Key {self.api_key}",
        }

    def generate_web_response(self, query: str) -> dict | None:
        """
        Отправляет запрос к генеративному поиску.
        Добавляет инструкцию для приоритета официальных источников.
        """
        # Уточняем запрос для улучшения качества источников
        refined_query = f"{query} (отвечай, используя официальные источники, СМИ и нормативно-правовые акты РФ; по возможности избегай ссылок на соцсети)"

        data = {
            "folderId": self.folder_id,
            "messages": [{"role": "ROLE_USER", "content": refined_query}],
        }

        try:
            # Увеличиваем таймаут, так как поиск может занимать время
            response = requests.post(self.url, headers=self.headers, json=data, timeout=60)

            if response.status_code != 200:
                logger.error(f"Yandex Search API Error {response.status_code}: {response.text}")
                return None

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Критическая ошибка сети при запросе к Yandex Search API: {e}")
            return None
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в web_search_service: {e}")
            return None