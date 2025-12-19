import httpx
import logging
import json
import requests
from src.config import YANDEX_API_KEY, YANDEX_MODEL_URI, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)


class YandexGPTService:
    def __init__(self):
        self.api_key = YANDEX_API_KEY
        self.folder_id = YANDEX_FOLDER_ID
        # Основная текстовая модель (YandexGPT)
        self.model_uri = YANDEX_MODEL_URI
        # Мультимодальная модель Gemma 3 (обязательно с суффиксом -it)
        self.gemma_uri = f"gpt://{self.folder_id}/gemma-3-27b-it/latest"

        # Эндпоинты
        # Нативный эндпоинт для YandexGPT
        self.text_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        # OpenAI-совместимый эндпоинт для моделей Gallery (Gemma, Qwen и др.)
        self.vlm_url = "https://llm.api.cloud.yandex.net/v1/chat/completions"

    def generate_response(
            self,
            system_prompt: str,
            user_text: str,
            context_text: str = "",
            history: list = None,
            full_name: str = "Пользователь"
    ) -> dict:
        """
        Синхронная генерация текстового ответа.
        """
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        json_instruction = (
            "ВАЖНО: Твой ответ ДОЛЖЕН БЫТЬ СТРОГО в формате JSON.\n"
            "Используй HTML-теги <b></b> для жирного шрифта.\n"
            '{\n'
            '  "text": "Текст ответа...",\n'
            '  "suggestions": ["Подсказка 1", "Подсказка 2"]\n'
            '}\n'
        )

        final_system_prompt = f"{system_prompt}\n\nПользователь: {full_name}.\n\n{json_instruction}"

        messages = [{"role": "system", "text": final_system_prompt}]
        if history:
            messages.extend(history[-6:])

        messages.append({"role": "user", "text": f"Контекст:\n{context_text}\n\nВопрос:\n{user_text}"})

        data = {
            "modelUri": self.model_uri,
            "completionOptions": {"stream": False, "temperature": 0.3, "maxTokens": 2000},
            "messages": messages
        }

        try:
            response = requests.post(self.text_url, headers=headers, json=data, timeout=30)
            if response.status_code != 200:
                logger.error(f"GPT Error {response.status_code}: {response.text}")
                return {"text": "Ошибка нейросети.", "suggestions": []}

            raw_text = response.json()['result']['alternatives'][0]['message']['text']
            clean_json = raw_text.strip().replace("```json", "").replace("```", "")
            return json.loads(clean_json)
        except Exception as e:
            logger.error(f"GPT Parse Error: {e}")
            return {"text": "Ошибка обработки данных.", "suggestions": []}

    async def generate_vlm_response(self, prompt: str, image_base64: str) -> str:
        """
        Асинхронная генерация ответа на основе изображения (Gemma 3).
        Использует корректный OpenAI-совместимый эндпоинт llm.api.
        """
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        # Стандартная структура OpenAI Chat Completions для мультимодальных моделей
        data = {
            "model": self.gemma_uri,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.1
        }

        async with httpx.AsyncClient() as client:
            try:
                # ВАЖНО: запрос идет на llm.api.cloud.yandex.net/v1/chat/completions
                response = await client.post(self.vlm_url, headers=headers, json=data, timeout=90.0)

                if response.status_code != 200:
                    logger.error(f"VLM Error {response.status_code}: {response.text}")
                    return f"Ошибка анализа изображения (код {response.status_code}). Проверьте квоты на Gemma 3."

                result = response.json()
                # В OpenAI формате ответ лежит в choices[0].message.content
                return result['choices'][0]['message']['content']

            except Exception as e:
                logger.error(f"VLM Critical Error: {e}")
                return "Произошла ошибка при связи с визуальной моделью."