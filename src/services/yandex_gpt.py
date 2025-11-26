import requests
import logging
from src.config import YANDEX_API_KEY, YANDEX_MODEL_URI  # <--- Импортируем готовый URI

logger = logging.getLogger(__name__)


class YandexGPTService:
    def __init__(self):
        self.api_key = YANDEX_API_KEY
        self.model_uri = YANDEX_MODEL_URI
        # Эндпоинт для chat-режима (foundationModels/v1/completion)
        self.url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def generate_response(self, system_prompt: str, user_text: str, context_text: str = "") -> str:
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        final_user_message = f"Контекст:\n{context_text}\n\nВопрос:\n{user_text}"

        data = {
            "modelUri": self.model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": 1000  # Передаем числом, это стандарт
            },
            "messages": [
                {
                    "role": "system",
                    "text": system_prompt
                },
                {
                    "role": "user",
                    "text": final_user_message
                }
            ]
        }

        # ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ
        # Мы увидим в консоли, какой именно URI мы отправляем.
        # Если там будет gpt://None/..., значит ошибка в загрузке .env
        logger.info(f"Отправка запроса к YandexGPT. Model URI: {self.model_uri}")

        try:
            response = requests.post(self.url, headers=headers, json=data)

            if response.status_code != 200:
                logger.error(f"YandexGPT Error {response.status_code}: {response.text}")
                return "Произошла ошибка при обращении к нейросети."

            result = response.json()
            return result['result']['alternatives'][0]['message']['text']

        except Exception as e:
            logger.error(f"Критическая ошибка YandexGPT: {e}")
            return "Извините, сервис временно недоступен."